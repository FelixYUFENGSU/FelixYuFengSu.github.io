---
title: The Fourier Transform
date: 2026-11-19
category: Signal Processing
summary: Building the Fourier transform from the idea of winding a signal around the origin and tracking its center of mass, and why it loses all information about time.
pages: 2
---
- A soundwave can be written as some oscillation over an equilibrium.

<figure class="sketch"><img src="/notes/fourier-transform/fig-1.png" alt="Hand-drawn sketch: Pressure (intensity) vs. time graph showing a wavy oscillation about the time axis" loading="lazy"><figcaption><span class="fig-num">Figure 1.</span> Pressure (intensity) vs. time graph showing a wavy oscillation about the time axis</figcaption></figure>

Picture a harmony of sounds, the new combined pressure v time graph isn't a clean oscillation anymore (you add each individual pressure). How can we decompose base frequencies from something complex?

Take a simple, 3 beat / sec frequency. Take that wave and wrap it around the origin.

<figure class="sketch"><img src="/notes/fourier-transform/fig-2.png" alt="Hand-drawn sketch: A wave with vectors drawn along it, and a wrapped-up plot around the origin" loading="lazy"><figcaption><span class="fig-num">Figure 2.</span> A wave with vectors drawn along it, and a wrapped-up plot around the origin</figcaption></figure>

The vector lined up with the wave draws the "circle" on the plane. This introduces a second frequency, the cycles / second we wrap around the center. (can adjust)

When our winding freq = original freq, the center of mass of the circle is to the right.

Take only the x-coord of the center of mass. As we slowly increase cycles / sec to match the original 3 Hz, we can see that it peaks at 3 Hz.

<figure class="sketch"><img src="/notes/fourier-transform/fig-3.png" alt="Hand-drawn sketch: Graph of x-coord for c.o.m. against winding freq, with a large peak near 0, a small bump near 3, and tick marks at 3, 4, 5; vertical axis marked 0, 0.5, 1.0" loading="lazy"><figcaption><span class="fig-num">Figure 3.</span> Graph of x-coord for c.o.m. against winding freq, with a large peak near 0, a small bump near 3, and tick marks at 3, 4, 5; vertical axis marked 0, 0.5, 1.0</figcaption></figure>

"Almost Fourier Transform"

Take 2 diff signals w diff frequencies. If you take the almost fourier transform of both, then sum the waves, you get the same as summing original waves, then applying almost Fourier transform.

Then

<figure class="sketch"><img src="/notes/fourier-transform/fig-4.png" alt="Hand-drawn sketch: A 2 Hz wave and a 3 Hz wave, each mapped by the almost Fourier transform ('aft.') to a bump at 2 and a bump at 3 respectively; their sum, a more complex wave, maps to a graph with bumps at both 2 and 3" loading="lazy"><figcaption><span class="fig-num">Figure 4.</span> A 2 Hz wave and a 3 Hz wave, each mapped by the almost Fourier transform ("aft.") to a bump at 2 and a bump at 3 respectively; their sum, a more complex wave, maps to a graph with bumps at both 2 and 3</figcaption></figure>

the bumps describe the original frequency that went into the signal.

## Actual Fourier

Take some signal (say the 3 Hz sine wave) and call it $g(t)$.

$e^{-2\pi i f t}$, where $f$ = winding frequency and $t$ = time (rotation).

then $g(t)e^{-2\pi i f t}$ draws up the wound up wrap graph. The point of this is to track the center of mass, which leads us to $\frac{1}{N}\sum_{k=1}^{N} g(t_k)e^{-2\pi i f t_k}$ to take a bunch of samples, then instead of the limit, we have

$$\frac{1}{t_2 - t_1}\int_{t_1}^{t_2} g(t)e^{-2\pi i f t}\,dt$$

the actual Fourier transform

Then the longer the correct (right freq.) signal persists, the larger the value of the Fourier transform at that freq. For other freqs, longer times ≠ larger value since the graph balances itself out via the windings.

$$\hat{g}(f) = \int_{t_1}^{t_2} g(t)e^{-2\pi i f t}\,dt$$

<figure class="sketch"><img src="/notes/fourier-transform/fig-5.png" alt="Hand-drawn sketch: Time domain (a jagged signal) —Fourier Trans.→ Freq. domain: individual freq's and how much they contribute" loading="lazy"><figcaption><span class="fig-num">Figure 5.</span> Time domain (a jagged signal) —Fourier Trans.→ Freq. domain: individual freq's and how much they contribute</figcaption></figure>

Limitations: is only a fn of freq so loses all info in the time domain. i.e. don't know when freqs begin or end.
