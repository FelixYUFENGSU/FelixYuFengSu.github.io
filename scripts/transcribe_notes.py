"""
Transcribe scanned handwritten notes into blog-ready Markdown + LaTeX.

Drop scans into notes-inbox/:

    notes-inbox/<name>/page1.jpg, page2.jpg ...   -> one note per folder
    notes-inbox/scan.pdf                           -> one note per PDF
    notes-inbox/photo.jpg                          -> loose photos together become one note

Each note is sent to Claude (all its pages in one request, in filename order) and
written to content/notes/YYYY-MM-DD-<slug>.md. Compressed copies of the
pages go to static/notes/<slug>/ so readers can compare with the
original, every equation is test-rendered with KaTeX, and the scans are removed
from the inbox. A summary for the pull request is written to $PR_BODY_FILE.

Env:
    ANTHROPIC_API_KEY   required (unless NOTES_FAKE=1)
    NOTES_MODEL         default claude-sonnet-5-5
    NOTES_FAKE=1        skip the API and write placeholder text (for testing)
    KATEX_DIR           path to the katex npm package (enables equation checks)
    PR_BODY_FILE        where to write the pull-request description
    GITHUB_OUTPUT       set by GitHub Actions; receives created=true/false
"""

import base64
import io
import json
import os
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

from PIL import Image, ImageOps

try:  # iPhone photos are HEIC by default
    from pillow_heif import register_heif_opener

    register_heif_opener()
except ImportError:
    pass

ROOT = Path(__file__).resolve().parent.parent
INBOX = ROOT / "notes-inbox"
NOTES = ROOT / "content" / "notes"
SCANS = ROOT / "static" / "notes"

MODEL = os.environ.get("NOTES_MODEL", "claude-sonnet-5-5")
MAX_EDGE = int(os.environ.get("NOTES_MAX_EDGE", "1568"))   # what the model sees
KEEP_EDGE = 1400                                            # copies kept on the site
MAX_PAGES_PER_REQUEST = 20
# USD per million tokens, for the cost estimate in the PR (Sonnet 5.5 list price).
PRICE_IN, PRICE_OUT = 2.0, 10.0

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"}

SYSTEM_PROMPT = r"""You transcribe photographed handwritten notes (usually mathematics) into Markdown for a blog that renders math with KaTeX.

Faithfulness comes first:
- Transcribe exactly what is written. Do not correct, complete, simplify, or "improve" the mathematics. If the notes contain an error, keep it.
- Do not add explanations, examples, or steps that are not on the page.
- Omit crossed-out material.

Math:
- Inline math in $...$; display math in $$...$$ on its own lines.
- Use only commands KaTeX supports. For multi-line derivations use $$\begin{aligned} ... \end{aligned}$$.
- Never use \[ \], \( \), equation/align environments, \label, \ref, or TikZ. Never put math inside backticks.
- Use \mathbb{R}, \mathbb{N}, \mathbb{Z}, \mathbb{Q}, \mathbb{C} and \varepsilon (not shorthand macros).

Structure:
- Use "## " for headings that appear in the notes (do not add a top-level "# " title).
- Definitions, theorems, lemmas, propositions, corollaries, and remarks go in a blockquote, with every line prefixed by "> ", starting like: > **Theorem 2.3** (Bolzano–Weierstrass). ...
- Proofs are normal paragraphs that start with *Proof.* and end with $\blacksquare$.
- Use Markdown lists for lists.

When unsure:
- If a word or symbol is illegible, write <span class="unclear">[??]</span>. If you have a best guess, write it inside the span followed by a question mark, e.g. <span class="unclear">$\sup$?</span>.
- For drawings or diagrams that can't be typeset, write: *[Figure: short description — see original page N]*

Reply in exactly this format and nothing else:
TITLE: <short descriptive title for these notes>
SUMMARY: <one sentence describing what the notes cover>
---
<the Markdown body>"""


# ------------------------------------------------------------------ helpers
def slugify(text: str) -> str:
    text = re.sub(r"^\d{4}-\d{2}-\d{2}[-_ ]*", "", text.lower())
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")[:60] or "notes"


def leading_date(text: str) -> str | None:
    m = re.match(r"(\d{4}-\d{2}-\d{2})", text)
    return m.group(1) if m else None


def natural_key(path: Path):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", path.name)]


def load_pages(path: Path) -> list[Image.Image]:
    """One file -> list of page images (PDFs can have many pages)."""
    if path.suffix.lower() == ".pdf":
        import pypdfium2 as pdfium

        pdf = pdfium.PdfDocument(str(path))
        return [pdf[i].render(scale=2.5).to_pil().convert("RGB") for i in range(len(pdf))]
    img = Image.open(path)
    return [ImageOps.exif_transpose(img).convert("RGB")]


def shrink(img: Image.Image, edge: int) -> Image.Image:
    img = img.copy()
    img.thumbnail((edge, edge), Image.LANCZOS)
    return img


def jpeg_bytes(img: Image.Image, quality: int) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality, optimize=True)
    return buf.getvalue()


def find_jobs() -> list[dict]:
    """Group inbox files into notes: each folder, each PDF, and all loose photos."""
    jobs, loose = [], []
    if not INBOX.exists():
        return jobs
    for entry in sorted(INBOX.iterdir(), key=natural_key):
        if entry.is_dir():
            files = sorted(
                (f for f in entry.rglob("*") if f.is_file() and f.suffix.lower() in IMAGE_EXT | {".pdf"}),
                key=natural_key,
            )
            if files:
                jobs.append({"name": entry.name, "files": files, "remove": [entry]})
        elif entry.suffix.lower() == ".pdf":
            jobs.append({"name": entry.stem, "files": [entry], "remove": [entry]})
        elif entry.suffix.lower() in IMAGE_EXT:
            loose.append(entry)
    if loose:
        jobs.append({"name": None, "files": loose, "remove": loose})
    return jobs


# --------------------------------------------------------------- the model
def transcribe(pages: list[Image.Image]) -> tuple[str, str, str, dict]:
    if os.environ.get("NOTES_FAKE") == "1":
        body = (
            "## Placeholder\n\n> **Definition 1.1** (Test). A sequence $(a_n)$ converges to $L$ if for every "
            "$\\varepsilon > 0$ there is $N$ with $|a_n - L| < \\varepsilon$ for all $n \\geq N$.\n\n"
            "*Proof.* Trivial. $\\blacksquare$\n\nAn unclear symbol: <span class=\"unclear\">[??]</span>\n\n"
            "$$\\begin{aligned} f(x) &= x^2 \\\\ f'(x) &= 2x \\end{aligned}$$\n"
        )
        return "Test transcription", "A placeholder note produced without calling the API.", body, {"in": 0, "out": 0}

    import anthropic

    client = anthropic.Anthropic()
    content = []
    for i, page in enumerate(pages, 1):
        data = base64.standard_b64encode(jpeg_bytes(shrink(page, MAX_EDGE), 88)).decode()
        content.append({"type": "text", "text": f"Page {i}:"})
        content.append({"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": data}})
    content.append({
        "type": "text",
        "text": f"These are pages 1–{len(pages)} of one set of notes, in order. "
                "Transcribe them following the instructions.",
    })
    msg = client.messages.create(
        model=MODEL,
        max_tokens=16000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": content}],
    )
    text = "".join(b.text for b in msg.content if b.type == "text")
    usage = {"in": msg.usage.input_tokens, "out": msg.usage.output_tokens}

    m = re.match(r"\s*TITLE:\s*(.+?)\s*\n\s*SUMMARY:\s*(.+?)\s*\n\s*---\s*\n(.*)", text, re.S)
    if not m:  # model ignored the format: keep everything, flag it
        return "Untitled notes", "", text.strip(), usage
    return m.group(1).strip(), m.group(2).strip(), m.group(3).strip(), usage


# ------------------------------------------------------- equation checking
MATH_RE = re.compile(r"\$\$(.+?)\$\$|(?<![\\$])\$(?!\s)([^$\n]+?)(?<!\s)\$", re.S)


def check_math(body: str) -> list[str]:
    """Render every equation with KaTeX; return the ones that fail."""
    katex_dir = os.environ.get("KATEX_DIR")
    if not katex_dir:
        return []
    exprs = [(m.group(1) is not None, (m.group(1) or m.group(2)).strip()) for m in MATH_RE.finditer(body)]
    if not exprs:
        return []
    script = (
        "const katex=require(process.argv[1]);const items=JSON.parse(require('fs').readFileSync(0,'utf8'));"
        "const macros={'\\\\R':'\\\\mathbb{R}','\\\\N':'\\\\mathbb{N}','\\\\Z':'\\\\mathbb{Z}','\\\\Q':'\\\\mathbb{Q}',"
        "'\\\\C':'\\\\mathbb{C}','\\\\eps':'\\\\varepsilon'};const bad=[];"
        "for(const [display,tex] of items){try{katex.renderToString(tex,{displayMode:display,throwOnError:true,macros})}"
        "catch(e){bad.push(tex.slice(0,120)+'  →  '+String(e.message).slice(0,160))}}"
        "process.stdout.write(JSON.stringify(bad))"
    )
    out = subprocess.run(["node", "-e", script, katex_dir], input=json.dumps(exprs),
                         capture_output=True, text=True, check=False)
    if out.returncode != 0:
        return [f"(equation check failed to run: {out.stderr.strip()[:200]})"]
    return json.loads(out.stdout or "[]")


# --------------------------------------------------------------------- main
def main() -> int:
    jobs = find_jobs()
    if jobs and not os.environ.get("ANTHROPIC_API_KEY") and os.environ.get("NOTES_FAKE") != "1":
        print("::error::Add your Claude API key as a repository secret named ANTHROPIC_API_KEY "
              "(Settings → Secrets and variables → Actions → New repository secret).")
        return 1
    created = []
    total_in = total_out = 0

    for job in jobs:
        pages = [p for f in job["files"] for p in load_pages(f)]
        print(f"→ {job['name'] or 'loose photos'} ({len(pages)} page(s))")
        parts = [pages[i:i + MAX_PAGES_PER_REQUEST] for i in range(0, len(pages), MAX_PAGES_PER_REQUEST)]
        title = summary = None
        bodies = []
        for chunk in parts:
            t, s, body, usage = transcribe(chunk)
            title, summary = title or t, summary or s
            bodies.append(body)
            total_in += usage["in"]
            total_out += usage["out"]
        body = "\n\n".join(bodies)

        when = leading_date(job["name"] or "") or date.today().isoformat()
        slug = slugify(job["name"]) if job["name"] else slugify(title)
        out_dir = NOTES
        out_dir.mkdir(parents=True, exist_ok=True)
        out = out_dir / f"{when}-{slug}.md"
        n = 2
        while out.exists():  # never overwrite an existing note
            out = out_dir / f"{when}-{slug}-{n}.md"
            n += 1
        slug = out.stem[11:]

        out.write_text(
            "---\n"
            f"title: {title.replace(chr(10), ' ')}\n"
            f"date: {when}\n"
            f"summary: {summary.replace(chr(10), ' ')}\n"
            f"pages: {len(pages)}\n"
            "---\n" + body + "\n",
            encoding="utf-8",
        )

        scan_dir = SCANS / slug
        scan_dir.mkdir(parents=True, exist_ok=True)
        for i, page in enumerate(pages, 1):
            (scan_dir / f"page-{i}.jpg").write_bytes(jpeg_bytes(shrink(page, KEEP_EDGE), 72))

        for path in job["remove"]:
            if path.is_dir():
                for f in path.rglob("*"):
                    if f.is_file():
                        f.unlink()
                for d in sorted((p for p in path.rglob("*") if p.is_dir()), reverse=True):
                    d.rmdir()
                path.rmdir()
            else:
                path.unlink()

        created.append({
            "path": out.relative_to(ROOT).as_posix(),
            "title": title,
            "pages": len(pages),
            "unclear": body.count('class="unclear"'),
            "math_errors": check_math(body),
        })

    # Empty folders left behind in the inbox.
    if INBOX.exists():
        for d in sorted((p for p in INBOX.rglob("*") if p.is_dir()), reverse=True):
            if not any(d.iterdir()):
                d.rmdir()

    write_outputs(created, total_in, total_out)
    return 0


def write_outputs(created: list[dict], tokens_in: int, tokens_out: int) -> None:
    gh_out = os.environ.get("GITHUB_OUTPUT")
    if gh_out:
        with open(gh_out, "a") as fh:
            fh.write(f"created={'true' if created else 'false'}\n")
            titles = ", ".join(c["title"] for c in created)[:200]
            fh.write(f"title=Notes: {titles}\n")

    if not created:
        print("Nothing to transcribe.")
        return

    cost = tokens_in / 1e6 * PRICE_IN + tokens_out / 1e6 * PRICE_OUT
    lines = ["## Transcribed notes", ""]
    for c in created:
        flags = []
        if c["unclear"]:
            flags.append(f"⚠️ {c['unclear']} unclear spot(s) marked [??]")
        if c["math_errors"]:
            flags.append(f"❌ {len(c['math_errors'])} equation(s) don't render")
        lines.append(f"- **{c['title']}**: `{c['path']}` · {c['pages']} page(s)"
                     + (f" · {' · '.join(flags)}" if flags else " · ✅ all equations render"))
        for err in c["math_errors"]:
            lines.append(f"  - `{err}`")
    lines += [
        "",
        "### Before merging",
        "- Open each note under **Files changed** and compare it with the original pages "
        "(saved next to it under `static/notes/`).",
        "- Search for `[??]` and fix anything marked unclear.",
        "- Fix any equations listed above as not rendering.",
        "- Edit right here in the pull request (⋯ → Edit file), then **Merge** to publish.",
        "",
        f"<sub>Model: {MODEL} · {tokens_in:,} input + {tokens_out:,} output tokens · "
        f"≈ ${cost:.3f}</sub>",
    ]
    body = "\n".join(lines)
    print(body)
    if os.environ.get("PR_BODY_FILE"):
        Path(os.environ["PR_BODY_FILE"]).write_text(body, encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
