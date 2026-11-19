# Notes inbox

Upload scans of handwritten notes here and they're transcribed to Markdown + LaTeX
automatically. A pull request opens with the draft so you can check it before it's published
on the Notes page.

```
notes-inbox/
  2026-11-20 Cauchy sequences/   ← a folder of photos = one note (pages in filename order)
    page1.jpg
    page2.jpg
  fourier-ideas.pdf              ← a PDF = one note
  IMG_0412.HEIC                  ← loose photos uploaded together = one note
```

- If one upload covers more than one topic, Claude splits it into separate notes and gives
  each a **category** (reusing ones you already have when they fit). Notes are grouped by
  category on the Notes page. To change a category, edit the `category:` line at the top of
  the note in the pull request.
- Accepted: JPG, PNG, HEIC (iPhone photos), WEBP, and PDF.
- Start a folder's name with a date (`2026-11-20 ...`) to date the note; otherwise it uses
  the upload date. The folder name also becomes the note's web address.
- **To upload:** open this `notes-inbox` folder on GitHub, click **Add file → Upload files**,
  drag in your photos, a PDF, or a whole folder, then **Commit changes**.
