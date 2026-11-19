"""
Redraw one cropped hand-drawn figure as a clean SVG.

    python scripts/redraw_figure.py <note> <figure-number>

<note> is the note's address name (the part after /notes/, e.g. "wavelets") and
<figure-number> is N in static/notes/<note>/fig-N.png. The SVG is saved next to
the PNG as fig-N.svg and the note is switched to use it. The original crop is
kept, so to go back, change "fig-N.svg" to "fig-N.png" in the note.

Env: ANTHROPIC_API_KEY (or NOTES_FAKE=1 for a test SVG), NOTES_MODEL.
"""

import base64
import os
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODEL = os.environ.get("NOTES_MODEL", "claude-sonnet-5-5")

PROMPT = """Recreate this hand-drawn sketch from someone's math notes as a clean SVG figure.

Be faithful: keep exactly what is drawn — the same curves and their shapes, axes, tick marks, labels, arrows, and their relative positions. Do not add axes, values, labels, grid lines, or details that are not in the sketch, and do not "correct" it. If something is ambiguous, draw your best reading of it as drawn.

Style:
- Black strokes (#111), stroke-width 2, round line caps and joins, no fill except where the sketch is filled in.
- Labels as <text> in font-family "Georgia, serif", around 15px; use Unicode for math (ŷ, Ψ, ε, ∫, subscripts as ₁ ₂ or <tspan baseline-shift="sub">).
- Transparent background, a viewBox that fits the content with a small margin, and width up to 760.
- No scripts, external images, or fonts.

Reply with only the SVG markup, starting with <svg and ending with </svg>."""

FAKE_SVG = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 160" width="400">'
            '<path d="M20 130 H380 M40 140 V20" stroke="#111" stroke-width="2" fill="none"/>'
            '<path d="M40 90 C80 40 120 140 160 90 S240 40 280 90" stroke="#111" stroke-width="2" fill="none"/>'
            '<text x="330" y="150" font-family="Georgia, serif" font-size="15">time</text></svg>')


def sanitize(svg: str) -> str:
    """Keep only the <svg> element; drop scripts, event handlers and external references."""
    m = re.search(r"<svg\b.*?</svg>", svg, re.S)
    if not m:
        raise ValueError("The reply did not contain an <svg> element.")
    svg = m.group(0)
    svg = re.sub(r"<script\b.*?</script>", "", svg, flags=re.S | re.I)
    svg = re.sub(r"\son\w+\s*=\s*(\"[^\"]*\"|'[^']*')", "", svg, flags=re.I)
    svg = re.sub(r"\s(?:xlink:)?href\s*=\s*(\"(?!#)[^\"]*\"|'(?!#)[^']*')", "", svg, flags=re.I)
    if 'xmlns="http://www.w3.org/2000/svg"' not in svg:
        svg = svg.replace("<svg", '<svg xmlns="http://www.w3.org/2000/svg"', 1)
    ET.fromstring(svg)  # must be well-formed XML
    return svg


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__)
        return 2
    note, number = sys.argv[1].strip().strip("/").split("/")[-1], int(sys.argv[2])
    png = ROOT / "static" / "notes" / note / f"fig-{number}.png"
    if not png.exists():
        print(f"::error::No figure at static/notes/{note}/fig-{number}.png. Check the note name and number.")
        return 1
    md = next((p for p in (ROOT / "content" / "notes").glob(f"????-??-??-{note}.md")), None)
    if md is None:
        print(f"::error::No note file found for '{note}' in content/notes/.")
        return 1

    if os.environ.get("NOTES_FAKE") == "1":
        reply = FAKE_SVG
    else:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            print("::error::Add your Claude API key as a repository secret named ANTHROPIC_API_KEY.")
            return 1
        import anthropic

        data = base64.standard_b64encode(png.read_bytes()).decode()
        msg = anthropic.Anthropic().messages.create(
            model=MODEL,
            max_tokens=8000,
            messages=[{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": data}},
                {"type": "text", "text": PROMPT},
            ]}],
        )
        reply = "".join(b.text for b in msg.content if b.type == "text")

    svg = sanitize(reply)
    out = png.with_suffix(".svg")
    out.write_text(svg, encoding="utf-8")

    text = md.read_text(encoding="utf-8")
    old_src = f"/notes/{note}/fig-{number}.png"
    if old_src not in text:
        print(f"::warning::The note doesn't reference {old_src}; saved the SVG but left the note unchanged.")
    else:
        text = text.replace(old_src, f"/notes/{note}/fig-{number}.svg")
        md.write_text(text, encoding="utf-8")
    print(f"Redrew figure {number} of '{note}' → {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
