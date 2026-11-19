# felixyufengsu.github.io

My personal site and blog, built by a small Python script (`build.py`) and published with GitHub Pages.

## Write a post

1. Add a file to `content/posts/` named `YYYY-MM-DD-short-slug.md`:

   ```markdown
   ---
   title: My post title
   date: 2026-12-01
   summary: One line shown in the post list.
   ---
   Write in Markdown. Math works too: $e^{i\pi} + 1 = 0$, or display math with $$...$$.
   ```

   Add `draft: true` to the front matter to keep a post unpublished.

2. Commit and push. The GitHub Action builds and deploys the site in about a minute.

## Projects

Every public repo on my GitHub gets its own page at `/projects/<repo>/`, built from its README with setup and install sections removed. To write a project's page yourself, add `content/projects/<repo-name>.md` with a `title:` and `summary:` in the front matter. The list refreshes daily.

## Notes (scanned handwriting → LaTeX)

Upload scans to `notes-inbox/` (JPG, PNG, HEIC or PDF; a folder of photos is one
note). The **Transcribe scanned notes** workflow sends them to Claude, writes drafts to
`content/notes/` (splitting different topics into separate notes and suggesting a
`category:` for each, which groups them on /notes/), keeps compressed copies of the
pages in `static/notes/`, crops each drawing into the note as a numbered figure
(`static/notes/<note>/fig-N.png`; the **Redraw a figure** workflow turns one into a
clean SVG on request),
test-renders every equation with KaTeX, and opens a pull request on the
`notes/review` branch. Check the draft against the originals, fix anything marked
`[??]`, and merge to publish under `/notes/`. Details in `notes-inbox/README.md`.

Needs a repository secret `ANTHROPIC_API_KEY`. Model and image size can be changed
with `NOTES_MODEL` / `NOTES_MAX_EDGE` (see `scripts/transcribe_notes.py`).

## Preview locally

```bash
pip install -r requirements.txt
python build.py
cd _site && python -m http.server 8000     # open http://localhost:8000
```

## Layout

| Path | What it is |
|---|---|
| `content/_home.md` | intro text on the home page |
| `content/_blog.md` | the Blog page's title, intro text, and `empty:` message shown when there are no posts |
| `content/about.md`, `content/projects.md` | standalone pages |
| `content/projects/<repo>.md` | optional hand-written page for a repo (otherwise its README is used) |
| `content/projects/<slug>.md` with `link:` + `date:` | a project that isn't its own repo (e.g. the Fourier banner), listed by date with the rest |
| `content/posts/` | blog posts |
| `templates/base.html` | page shell (nav, footer) |
| `static/` | CSS, KaTeX, the banner SVG |
| `banner/generate_banner.py` | regenerates the Fourier banner (`python generate_banner.py light`) |

Social links (LinkedIn, email) are set in the `SITE` dictionary at the top of `build.py`.
