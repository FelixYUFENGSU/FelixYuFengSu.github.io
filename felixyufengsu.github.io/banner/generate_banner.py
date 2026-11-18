"""
Fourier epicycle banner: my name written by rotating circles.

"Felix Su" (a single-stroke cursive Hershey font) is joined into one closed
curve z(t). Its discrete Fourier transform gives coefficients c_k, and

    z(t) ~ sum_k c_k * exp(2*pi*i*k*t),   t in [0, 1)

Each term is a circle of radius |c_k| spinning at frequency k; chained tip
to tail, the last circle's tip traces the name. Jumps between pen strokes
are part of the curve but are not inked.

Output is a self-contained animated SVG (SMIL), so GitHub plays it directly
in a README.

    pip install numpy Hershey-Fonts
    python generate_banner.py          ->  banner.svg        (dark, GitHub profile)
    python generate_banner.py light    ->  banner-light.svg  (light, blog home page)
"""

import numpy as np
from HersheyFonts import HersheyFonts

# ---------------------------------------------------------------- settings
NAME = "Felix Su"
FONT = "cursive"
N_SAMPLES = 4096      # samples along the curve before the DFT
N_TERMS = 260         # epicycles kept (more = sharper letters)
PERIOD = 24           # seconds per full drawing
WIDTH, HEIGHT = 1000, 340

# "dark": GitHub profile card.  "light": transparent, for the blog home page.
import sys
THEME = sys.argv[1] if len(sys.argv) > 1 else "dark"
OUT = "banner.svg" if THEME == "dark" else "banner-light.svg"
if THEME == "dark":
    BG, CIRCLE, ARM, INK, MUTED, ACCENT = "#0d1117", "#58a6ff", "#c9d1d9", "#f0b429", "#8b949e", "#58a6ff"
else:
    BG, CIRCLE, ARM, INK, MUTED, ACCENT = "none", "#6b7280", "#374151", "#111111", "#6b7280", "#2563eb"
    HEIGHT = 250


# ----------------------------------------------------- curve from the font
def chaikin(pts, rounds=2):
    """Corner-cutting smoothing so the polyline font looks hand-drawn."""
    pts = np.asarray(pts, float)
    for _ in range(rounds):
        if len(pts) < 3:
            break
        q = 0.75 * pts[:-1] + 0.25 * pts[1:]
        r = 0.25 * pts[:-1] + 0.75 * pts[1:]
        mid = np.empty((2 * len(q), 2))
        mid[0::2], mid[1::2] = q, r
        pts = np.vstack([pts[0], mid, pts[-1]])
    return pts


def name_strokes():
    f = HersheyFonts()
    f.load_default_font(FONT)
    f.normalize_rendering(100)
    strokes = [chaikin(s) for s in f.strokes_for_text(NAME)]
    # merge strokes that continue exactly where the previous one ended
    merged = [strokes[0]]
    for s in strokes[1:]:
        if np.allclose(merged[-1][-1], s[0]):
            merged[-1] = np.vstack([merged[-1], s[1:]])
        else:
            merged.append(s)
    return merged


def closed_curve(strokes, n):
    """Join strokes with hidden 'pen-up' bridges, resample by arc length."""
    pts, vis = [], []
    for i, s in enumerate(strokes):
        pts.append(s)
        vis += [True] * len(s)
        nxt = strokes[(i + 1) % len(strokes)][0]
        bridge = np.linspace(s[-1], nxt, 12)[1:-1]
        pts.append(bridge)
        vis += [False] * len(bridge)
    p = np.vstack(pts)
    z = p[:, 0] + 1j * p[:, 1]
    vis = np.array(vis)

    zc = np.append(z, z[0])
    s = np.concatenate([[0], np.cumsum(np.abs(np.diff(zc)))])
    s_new = np.linspace(0, s[-1], n, endpoint=False)
    z_new = np.interp(s_new, s, zc.real) + 1j * np.interp(s_new, s, zc.imag)
    idx = np.clip(np.searchsorted(s, s_new, side="right") - 1, 0, len(vis) - 1)
    # a sample is inked only if the segment it lies on joins two inked points
    nxt = np.clip(idx + 1, 0, len(vis) - 1)
    return z_new, vis[idx] & vis[nxt]


z, visible = closed_curve(name_strokes(), N_SAMPLES)

# fit into the banner (SVG y points down)
z = z.real - 1j * z.imag
box_w, box_h, top = 860, 190, 30
w, h = np.ptp(z.real), np.ptp(z.imag)
k = min(box_w / w, box_h / h)
z = (z - complex(z.real.min(), z.imag.min())) * k
z += complex((WIDTH - w * k) / 2, top + (box_h - h * k) / 2)

# ------------------------------------------------------------ Fourier
N = len(z)
coeffs = np.fft.fft(z) / N
freqs = np.fft.fftfreq(N, d=1 / N).astype(int)
c0 = coeffs[0]
order = [i for i in np.argsort(-np.abs(coeffs)) if freqs[i] != 0][:N_TERMS]
terms = [(int(freqs[i]), abs(coeffs[i]), np.degrees(np.angle(coeffs[i]))) for i in order]


def reconstruct(t):
    out = np.full(t.shape, c0, dtype=complex)
    for f, r, ph in terms:
        out += r * np.exp(1j * (np.radians(ph) + 2 * np.pi * f * t))
    return out


# ------------------------------------------------------------ SVG pieces
def fmt(x):
    return f"{x:.2f}".rstrip("0").rstrip(".")


def epicycles():
    """Nested groups, each rotating relative to its parent, so arm k's
    absolute angle is phase_k + 360 * f_k * time / PERIOD."""
    parts, prev_f, prev_ph = [], 0, 0.0
    for j, (f, r, ph) in enumerate(terms):
        # fade small circles so the big ones read clearly
        op = max(0.12, min(0.55, r / terms[0][1] * 0.9))
        parts.append(
            f'<g transform="rotate({fmt(ph - prev_ph)})"><g>'
            f'<animateTransform attributeName="transform" type="rotate" from="0" '
            f'to="{360 * (f - prev_f)}" dur="{PERIOD}s" repeatCount="indefinite"/>'
            + (f'<circle r="{fmt(r)}" class="c" stroke-opacity="{op:.2f}"/>' if r > 0.6 else "")
            + f'<line x2="{fmt(r)}" class="a"/><g transform="translate({fmt(r)},0)">'
        )
        prev_f, prev_ph = f, ph
    tip = f'<circle r="4" fill="{INK}"/><circle r="9" fill="{INK}" opacity=".25"/>'
    return (f'<g transform="translate({fmt(c0.real)},{fmt(c0.imag)})">'
            + "".join(parts) + tip + "</g></g></g>" * len(terms) + "</g>")


def trace():
    """Inked strokes, each revealed (dash animation) exactly while the pen
    passes over it; the whole name fades out just before the loop restarts."""
    M = 6000
    t = np.arange(M) / M
    pts = reconstruct(t)
    vis = visible[(t * N).astype(int)]
    out, start = [], None
    for i in range(M + 1):
        v = i < M and vis[i]
        if v and start is None:
            start = i
        elif not v and start is not None:
            a, b = start, i
            seg = pts[a:min(b + 1, M)]
            L = float(np.sum(np.abs(np.diff(seg)))) + 2
            d = "M" + "L".join(f"{fmt(p.real)},{fmt(p.imag)}" for p in seg)
            out.append(
                f'<path d="{d}" class="ink" stroke-dasharray="{fmt(L)}" stroke-dashoffset="{fmt(L)}">'
                f'<animate attributeName="stroke-dashoffset" dur="{PERIOD}s" repeatCount="indefinite" '
                f'values="{fmt(L)};{fmt(L)};0;0" keyTimes="0;{a / M:.4f};{b / M:.4f};1"/></path>')
            start = None
    fade = (f'<animate attributeName="opacity" dur="{PERIOD}s" repeatCount="indefinite" '
            f'values="1;1;0;0" keyTimes="0;0.95;0.99;1"/>')
    return f'<g>{fade}{"".join(out)}</g>'


caption = "" if THEME != "dark" else (
    f'<text x="{WIDTH / 2}" y="{HEIGHT - 52}" text-anchor="middle" class="eq">z(t) = Σ c<tspan baseline-shift="sub" font-size="12">k</tspan> e<tspan baseline-shift="super" font-size="12">2πikt</tspan>  ·  {N_TERMS} spinning circles</text>'
    f'<text x="{WIDTH / 2}" y="{HEIGHT - 24}" text-anchor="middle" class="sub">M.S. Mathematical Sciences · NYU Tandon   |   B.S. Mathematics of Computation · UCLA</text>')

svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {HEIGHT}" width="{WIDTH}" height="{HEIGHT}">
<style>
  .c {{ fill: none; stroke: {CIRCLE}; stroke-width: 1; }}
  .a {{ stroke: {ARM}; stroke-width: .8; stroke-opacity: .45; }}
  .ink {{ fill: none; stroke: {INK}; stroke-width: 3.5; stroke-linecap: round; stroke-linejoin: round; }}
  .sub {{ font: 15px -apple-system, 'Segoe UI', Helvetica, Arial, sans-serif; fill: {MUTED}; letter-spacing: .5px; }}
  .eq {{ font: italic 18px 'Cambria Math', Cambria, Georgia, serif; fill: {ACCENT}; }}
</style>
<rect width="{WIDTH}" height="{HEIGHT}" rx="14" fill="{BG}"/>
{trace()}
{epicycles()}
{caption}
</svg>
"""

with open(OUT, "w") as fh:
    fh.write(svg)
print(f"{OUT} written ({len(svg) / 1024:.0f} KB, {N_TERMS} terms)")
