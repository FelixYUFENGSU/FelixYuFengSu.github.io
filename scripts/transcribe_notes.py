"""
Transcribe scanned handwritten notes into blog-ready Markdown + LaTeX.

Drop scans into notes-inbox/:

    notes-inbox/<name>/page1.jpg, page2.jpg ...   -> one note per folder
    notes-inbox/scan.pdf                           -> one note per PDF
    notes-inbox/photo.jpg                          -> loose photos together become one note

Each note is sent to Claude (all its pages in one request, in filename order) and
written to content/notes/YYYY-MM-DD-<slug>.md. If the pages hold more than one
topic, Claude splits them into separate notes and suggests a category for each
(reusing existing categories when they fit). Compressed copies of the
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

Splitting and categories:
- If the pages contain more than one separate set of notes (for example, a new title starts a different topic), output one block per set, in order. Otherwise output a single block.
- Give each block a CATEGORY: a short subject area (1–3 words, Title Case). Reuse one of the existing categories the user lists when it fits; otherwise make a new one.
- In figure references, number pages relative to the first page of that block (its first page is "page 1").

Reply in exactly this format and nothing else:
=== NOTE ===
TITLE: <short descriptive title>
SUMMARY: <one sentence describing what these notes cover>
CATEGORY: <category>
PAGES: <first>-<last>
---
<the Markdown body>
"""


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
def existing_categories() -> list[str]:
    cats = set()
    for path in NOTES.glob("*.md"):
        m = re.search(r"^category:\s*(.+)$", path.read_text(encoding="utf-8"), re.M)
        if m:
            cats.add(m.group(1).strip())
    return sorted(cats)


def parse_notes(text: str, n_pages: int) -> list[dict]:
    """Split the model's reply into note blocks."""
    blocks = [b for b in re.split(r"^\s*=== NOTE ===\s*$", text, flags=re.M) if b.strip()]
    notes = []
    for block in blocks:
        m = re.match(r"\s*TITLE:\s*(.+?)\s*\n\s*SUMMARY:\s*(.+?)\s*\n\s*CATEGORY:\s*(.+?)\s*\n"
                     r"\s*PAGES:\s*(\d+)\s*(?:[-–]\s*(\d+))?\s*\n\s*---\s*\n(.*)", block, re.S)
        if not m:
            continue
        first = int(m.group(4))
        last = int(m.group(5) or first)
        notes.append({"title": m.group(1).strip(), "summary": m.group(2).strip(),
                      "category": m.group(3).strip(), "pages": (first, last), "body": m.group(6).strip()})
    if not notes:  # model ignored the format: keep everything as one note
        notes = [{"title": "Untitled notes", "summary": "", "category": "", "pages": (1, n_pages),
                  "body": text.strip()}]
    # Clamp page ranges to what was sent and make them cover every page.
    for i, note in enumerate(notes):
        lo, hi = note["pages"]
        lo = max(1, min(lo, n_pages))
        hi = max(lo, min(hi, n_pages))
        if i == 0:
            lo = 1
        if i == len(notes) - 1:
            hi = n_pages
        note["pages"] = (lo, hi)
    return notes


def transcribe(pages: list[Image.Image], categories: list[str]) -> tuple[list[dict], dict]:
    if os.environ.get("NOTES_FAKE") == "1":
        half = max(1, len(pages) // 2)
        fake = (
            f"=== NOTE ===\nTITLE: Fake topic one\nSUMMARY: First placeholder note.\nCATEGORY: Testing\nPAGES: 1-{half}\n---\n"
            "## Part one\n\n> **Definition 1.1** (Test). $(a_n)$ converges to $L$ if $|a_n - L| < \\varepsilon$.\n\n"
            "*[Figure: a sketch — see original page 1]*\n"
        )
        if len(pages) > 1:
            fake += (
                f"=== NOTE ===\nTITLE: Fake topic two\nSUMMARY: Second placeholder note.\nCATEGORY: Testing\n"
                f"PAGES: {half + 1}-{len(pages)}\n---\n## Part two\n\n$$\\int_0^1 x\\,dx = \\tfrac12$$\n"
            )
        return parse_notes(fake, len(pages)), {"in": 0, "out": 0}

    import anthropic

    client = anthropic.Anthropic()
    content = []
    for i, page in enumerate(pages, 1):
        data = base64.standard_b64encode(jpeg_bytes(shrink(page, MAX_EDGE), 88)).decode()
        content.append({"type": "text", "text": f"Page {i}:"})
        content.append({"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": data}})
    cats = ", ".join(categories) if categories else "(none yet)"
    content.append({
        "type": "text",
        "text": f"These are pages 1–{len(pages)}, in order. Existing categories: {cats}. "
                "Transcribe them following the instructions.",
    })
    msg = client.messages.create(
        model=MODEL,
        max_tokens=16000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": content}],
    )
    text = "".join(b.text for b in msg.content if b.type == "text")
    return parse_notes(text, len(pages)), {"in": msg.usage.input_tokens, "out": msg.usage.output_tokens}


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
    categories = existing_categories()

    for job in jobs:
        pages = [p for f in job["files"] for p in load_pages(f)]
        print(f"→ {job['name'] or 'loose photos'} ({len(pages)} page(s))")
        notes = []
        for start in range(0, len(pages), MAX_PAGES_PER_REQUEST):
            chunk = pages[start:start + MAX_PAGES_PER_REQUEST]
            chunk_notes, usage = transcribe(chunk, categories)
            for note in chunk_notes:
                lo, hi = note["pages"]
                note["images"] = chunk[lo - 1:hi]
                notes.append(note)
                if note["category"] and note["category"] not in categories:
                    categories.append(note["category"])
            total_in += usage["in"]
            total_out += usage["out"]

        when = leading_date(job["name"] or "") or date.today().isoformat()
        for note in notes:
            # A folder name becomes the address only when the folder is a single note.
            base = job["name"] if job["name"] and len(notes) == 1 else note["title"]
            # Each note's address (/notes/<slug>/) must be unique across all dates.
            NOTES.mkdir(parents=True, exist_ok=True)
            root_slug = slug = slugify(base)
            n = 2
            while any(NOTES.glob(f"????-??-??-{slug}.md")) or (SCANS / slug).exists():
                slug = f"{root_slug}-{n}"
                n += 1
            out = NOTES / f"{when}-{slug}.md"

            front = [
                "---",
                f"title: {note['title'].replace(chr(10), ' ')}",
                f"date: {when}",
            ]
            if note["category"]:
                front.append(f"category: {note['category'].replace(chr(10), ' ')}")
            front += [
                f"summary: {note['summary'].replace(chr(10), ' ')}",
                f"pages: {len(note['images'])}",
                "---",
            ]
            out.write_text("\n".join(front) + "\n" + note["body"] + "\n", encoding="utf-8")

            scan_dir = SCANS / slug
            scan_dir.mkdir(parents=True, exist_ok=True)
            for i, page in enumerate(note["images"], 1):
                (scan_dir / f"page-{i}.jpg").write_bytes(jpeg_bytes(shrink(page, KEEP_EDGE), 72))

            created.append({
                "path": out.relative_to(ROOT).as_posix(),
                "title": note["title"],
                "category": note["category"],
                "pages": len(note["images"]),
                "unclear": note["body"].count('class="unclear"'),
                "math_errors": check_math(note["body"]),
            })

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
        cat = f" · category: *{c['category']}*" if c.get("category") else ""
        lines.append(f"- **{c['title']}**: `{c['path']}` · {c['pages']} page(s){cat}"
                     + (f" · {' · '.join(flags)}" if flags else " · ✅ all equations render"))
        for err in c["math_errors"]:
            lines.append(f"  - `{err}`")
    lines += [
        "",
        "### Before merging",
        "- Open each note under **Files changed** and compare it with the original pages "
        "(saved next to it under `static/notes/`).",
        "- Search for `[??]` and fix anything marked unclear.",
        "- Check how the pages were split into notes and the `category:` each got "
        "(edit the front matter to change it).",
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
