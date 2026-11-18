---
title: Writing my name with 260 spinning circles
date: 2026-11-18
summary: How the banner on this site works: one closed curve, a discrete Fourier transform, and a chain of epicycles.
---
The signature at the top of my home page isn't a font or a video. It's a sum of circles. Each one spins at a constant speed, and when you chain them tip to tail, the last one traces out "Felix Su." Here's the math, and the code behind it.

## 1. A name is a closed curve

First, write the name as a **single closed curve**. I used a single-stroke cursive font (one of the old Hershey plotter fonts), so each letter is already a pen path rather than an outline. The jumps between strokes, like moving the pen from the "x" to the "S", become straight "pen-up" segments that are part of the curve but never get inked.

Put the curve in the complex plane: a point $(x, y)$ becomes $z = x + iy$. If we sample $N$ points evenly by arc length, the name turns into a list of complex numbers

$$z_0, z_1, \dots, z_{N-1}.$$

## 2. Take its Fourier transform

The discrete Fourier transform rewrites those samples as a sum of rotations:

$$c_k = \frac{1}{N} \sum_{n=0}^{N-1} z_n \, e^{-2\pi i k n / N}, \qquad z(t) = \sum_k c_k \, e^{2\pi i k t}.$$

Each term $c_k e^{2\pi i k t}$ is a point moving around a circle:

- the **radius** is $|c_k|$,
- the **starting angle** is $\arg c_k$,
- the **speed** is $k$ full turns per drawing. Negative $k$ spins the other way.

Adding the terms means stacking the circles: each one is centered on the tip of the one before it. That's an epicycle, the same idea Ptolemy used for planetary orbits.

## 3. Keep the big terms

With $N = 4096$ samples there are 4096 coefficients, but most are tiny. I sort by $|c_k|$ and keep the 260 largest. With fewer terms the letters go soft and wobbly (corners get Gibbs ringing); with more, the file gets larger with little visible gain.

```python
coeffs = np.fft.fft(z) / N
freqs = np.fft.fftfreq(N, d=1 / N).astype(int)
order = np.argsort(-np.abs(coeffs))[:260]    # biggest circles first
terms = [(freqs[i], abs(coeffs[i]), np.angle(coeffs[i]))
         for i in order]
```

## 4. Animate it without JavaScript

The output is a plain SVG, so it also plays inside a GitHub README, where scripts aren't allowed. The trick is **nested rotating groups**. Circle $j$ lives inside circle $j-1$'s group, so it inherits the parent's rotation. To make arm $j$'s *absolute* speed equal $f_j$, its group only has to rotate at the *difference* $f_j - f_{j-1}$. The rotations add up as you go down the nesting.

The gold ink is the curve reconstructed from those same 260 terms. Each stroke is revealed with a dash animation timed to the moment the pen passes over it.

## What I learned

The idea fits in two equations, but making it look right came down to small details: resampling by arc length so the pen moves at a steady pace, hiding the pen-up jumps, and choosing how many terms to keep.
