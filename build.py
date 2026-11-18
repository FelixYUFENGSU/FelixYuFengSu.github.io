"""
Tiny static site generator for my blog.

    content/posts/*.md   ->  blog posts (front matter: title, date, summary)
    content/*.md         ->  standalone pages (about, projects)
    static/              ->  copied as-is (css, banner)
    templates/base.html  ->  page shell

Run `python build.py` and open _site/index.html. On GitHub, the workflow in
.github/workflows/pages.yml runs this on every push and publishes _site/.

Math: write LaTeX between $...$ (inline) or $$...$$ (display); KaTeX renders
it in the browser. It is shielded from Markdown so underscores survive.
"""

import re
import shutil
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
        html = f'<h1>{meta["title"]}</h1><div class="prose">{render_md(body)}</div>'
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
