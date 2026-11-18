"""
Tiny static site generator for my blog.

    content/posts/*.md   ->  blog posts (front matter: title, date, summary)
    content/*.md         ->  standalone pages (about, projects)
    static/              ->  copied as-is (css, banner)
    templates/base.html  ->  page shell

Run `python build.py` and open _site/index.html. The Projects page lists my
public GitHub repos automatically (wherever content/projects.md has the
<!-- REPOS --> marker). On GitHub, the workflow in
.github/workflows/pages.yml runs this on every push and publishes _site/.

Math: write LaTeX between $...$ (inline) or $$...$$ (display); KaTeX renders
it in the browser. It is shielded from Markdown so underscores survive.
"""

import json
import os
import re
import shutil
import urllib.request
from datetime import date
from pathlib import Path

import markdown

ROOT = Path(__file__).parent
OUT = ROOT / "_site"
SITE = {
    "name": "Felix Su",
    "url": "https://felixyufengsu.github.io",
    "github": "https://github.com/FelixYUFENGSU",
    "linkedin": "",            # e.g. "https://www.linkedin.com/in/your-handle"
    "email": "",               # e.g. "you@nyu.edu"
}
GITHUB_USER = "FelixYUFENGSU"
SKIP_REPOS = {"felixyufengsu.github.io"}   # repos never listed (lowercase)
NAV = [("Home", "/"), ("Blog", "/blog/"), ("About", "/about/"), ("Projects", "/projects/")]


# ------------------------------------------------------------ helpers
def parse(path):
    """Split '---' front matter (key: value lines) from the Markdown body."""
    text = path.read_text(encoding="utf-8")
    meta = {}
    if text.startswith("---"):
        _, head, text = text.split("---", 2)
        for line in head.strip().splitlines():
            key, _, value = line.partition(":")
            meta[key.strip()] = value.strip().strip('"')
    return meta, text


def render_md(text):
    """Markdown -> HTML, keeping $...$ / $$...$$ math untouched for KaTeX."""
    stash = []

    def hide(m):
        stash.append(m.group(0))
        return f"\x00MATH{len(stash) - 1}\x00"

    text = re.sub(r"\$\$.+?\$\$", hide, text, flags=re.S)
    text = re.sub(r"(?<![\\$])\$(?!\s)[^$\n]+?(?<!\s)\$", hide, text)
    html = markdown.markdown(text, extensions=["fenced_code", "tables", "footnotes", "smarty"])
    return re.sub(r"\x00MATH(\d+)\x00", lambda m: stash[int(m.group(1))], html)


def nice_date(iso):
    d = date.fromisoformat(iso)
    return f"{d:%b} {d.day}, {d.year}"


def page(template, title, body, active):
    on = ' class="on"'
    nav = "".join(
        f'<a href="{href}"{on if label == active else ""}>{label}</a>'
        for label, href in NAV
    )
    social = [f'<a href="{SITE["github"]}">GitHub</a>']
    if SITE["linkedin"]:
        social.append(f'<a href="{SITE["linkedin"]}">LinkedIn</a>')
    if SITE["email"]:
        social.append(f'<a href="mailto:{SITE["email"]}">Email</a>')
    full_title = SITE["name"] if title == SITE["name"] else f'{title} · {SITE["name"]}'
    return (template.replace("{{title}}", full_title)
                    .replace("{{nav}}", nav)
                    .replace("{{social}}", " ".join(social))
                    .replace("{{year}}", str(date.today().year))
                    .replace("{{name}}", SITE["name"])
                    .replace("{{body}}", body))


def write(rel, html):
    path = OUT / rel / "index.html"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")


def post_list(posts):
    return "".join(
        f'<article class="item"><time>{nice_date(p["date"])}</time>'
        f'<h2><a href="{p["href"]}">{p["title"]}</a></h2>'
        f'<p>{p.get("summary", "")}</p></article>'
        for p in posts
    )


# ------------------------------------------------------------ GitHub repos
def gh_get(url, raw=False):
    headers = {"Accept": "application/vnd.github.raw" if raw else "application/vnd.github+json",
               "User-Agent": "site-builder"}
    if os.environ.get("GITHUB_TOKEN"):
        headers["Authorization"] = f"Bearer {os.environ['GITHUB_TOKEN']}"
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=20) as r:
        body = r.read().decode("utf-8", "replace")
    return body if raw else json.loads(body)


def readme_summary(text, limit=320):
    """First real paragraph of a README: skips headings, badges, images,
    HTML and code blocks, and flattens Markdown links to their text."""
    text = re.sub(r"```.*?```", "", text, flags=re.S)
    for para in re.split(r"\n\s*\n", text):
        p = para.strip()
        if not p or p.startswith(("#", "<", "!", "|", ">", "-", "*", "[![")):
            continue
        p = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", p)
        p = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", p)
        p = re.sub(r"[`*_]", "", " ".join(p.split()))
        if len(p) < 25:
            continue
        return p if len(p) <= limit else p[:limit].rsplit(" ", 1)[0] + "…"
    return ""


def fetch_repos():
    """Public, non-fork repos, most recently pushed first. Set REPOS_JSON to a
    file path to build offline from a saved list instead of the API."""
    if os.environ.get("REPOS_JSON"):
        return json.loads(Path(os.environ["REPOS_JSON"]).read_text())
    api = f"https://api.github.com/users/{GITHUB_USER}/repos?per_page=100&sort=pushed"
    repos = []
    for r in gh_get(api):
        if r["fork"] or r["private"] or r["name"].lower() in SKIP_REPOS or r["name"] == GITHUB_USER:
            continue
        summary = r["description"] or ""
        if not summary:
            try:
                summary = readme_summary(gh_get(f"https://api.github.com/repos/{GITHUB_USER}/{r['name']}/readme", raw=True))
            except Exception:
                pass
        repos.append({"name": r["name"], "url": r["html_url"], "summary": summary,
                      "language": r["language"], "topics": r.get("topics", []),
                      "stars": r["stargazers_count"], "homepage": r.get("homepage") or "",
                      "pushed": r["pushed_at"][:10]})
    return repos


LANG_COLORS = {"Python": "#3572A5", "TypeScript": "#3178c6", "JavaScript": "#f1e05a", "C": "#555555",
               "C++": "#f34b7d", "Jupyter Notebook": "#DA5B0B", "R": "#198CE7", "HTML": "#e34c26"}


def repo_cards():
    try:
        repos = fetch_repos()
    except Exception as exc:                      # never fail the whole build over this
        print(f"warning: could not load GitHub repos ({exc})")
        return f'<p class="muted">See all my repositories on <a href="{SITE["github"]}?tab=repositories">GitHub</a>.</p>'
    cards = []
    for r in repos:
        d = date.fromisoformat(r["pushed"])
        bits = []
        if r["language"]:
            color = LANG_COLORS.get(r["language"], "#999")
            bits.append(f'<span><i class="dot" style="background:{color}"></i>{r["language"]}</span>')
        if r["stars"]:
            bits.append(f'<span>★ {r["stars"]}</span>')
        bits.append(f'<span>Updated {d:%b} {d.year}</span>')
        links = f'<a href="{r["url"]}">code</a>' + (f' · <a href="{r["homepage"]}">demo</a>' if r["homepage"] else "")
        topics = "".join(f'<span class="topic">{t}</span>' for t in r["topics"])
        summary = r["summary"] or '<span class="muted">No description yet.</span>'
        cards.append(
            f'<div class="repo"><h3><a href="{r["url"]}">{r["name"]}</a></h3>'
            f'<p>{summary}</p>'
            + (f'<div class="topics">{topics}</div>' if topics else "")
            + f'<div class="repo-meta">{"".join(bits)}<span class="links">{links}</span></div></div>'
        )
    return "".join(cards)


# ------------------------------------------------------------ build
def build():
    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(ROOT / "static", OUT)
    template = (ROOT / "templates" / "base.html").read_text(encoding="utf-8")

    # posts
    posts = []
    for path in sorted((ROOT / "content" / "posts").glob("*.md")):
        meta, body = parse(path)
        if meta.get("draft", "").lower() == "true":
            continue
        slug = path.stem[11:] if re.match(r"\d{4}-\d{2}-\d{2}-", path.stem) else path.stem
        meta["href"] = f"/blog/{slug}/"
        posts.append(meta)
        html = (f'<article class="post"><time>{nice_date(meta["date"])}</time>'
                f'<h1>{meta["title"]}</h1>{render_md(body)}</article>'
                f'<p class="back"><a href="/blog/">← All posts</a></p>')
        write(f"blog/{slug}", page(template, meta["title"], html, "Blog"))
    posts.sort(key=lambda p: p["date"], reverse=True)

    # blog index
    n = len(posts)
    intro = (f'<h1>Blog</h1><p class="lead">✍️ Notes on math, code, and the places they meet. '
             f'{n} article{"s" if n != 1 else ""} so far.</p><hr>')
    write("blog", page(template, "Blog", intro + post_list(posts), "Blog"))

    # standalone pages
    for path in (ROOT / "content").glob("*.md"):
        if path.name.startswith("_"):
            continue
        meta, body = parse(path)
        content = render_md(body)
        if "<!-- REPOS -->" in content:
            content = content.replace("<!-- REPOS -->", repo_cards())
        html = f'<h1>{meta["title"]}</h1><div class="prose">{content}</div>'
        write(path.stem, page(template, meta["title"], html, meta["title"]))

    # home
    _, body = parse(ROOT / "content" / "_home.md")
    home = (
        '<figure class="banner"><img src="/banner-light.svg" '
        'alt="My name, Felix Su, written by a chain of spinning Fourier circles"></figure>'
        f'<div class="prose home">{render_md(body)}</div>'
        '<h3 class="section">Recent writing</h3>'
        + post_list(posts[:5])
    )
    write("", page(template, SITE["name"], home, "Home"))
    (OUT / ".nojekyll").touch()
    print(f"built {n} post(s) into {OUT}")


if __name__ == "__main__":
    build()
