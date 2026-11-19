---
title: Fourier Transform and Wavelet Transform
date: 2026-11-19
summary: Notes motivating the Fourier transform through wrapping a signal around the origin, then discussing time–frequency duality, wavelets, and the wavelet transform (convolution, Morlet wavelet, scalogram).
pages: 4
---
## Fourier Transform

- A soundwave can be written as some oscillation over an equilibrium.

*[Figure: pressure (intensity) vs. time graph showing a wavy oscillation about the time axis — see original page 1]*

Picture a harmony of sounds, the new combined pressure v time graph isn't a clean oscillation anymore (you add each individual pressure). How can we decompose base frequencies from something complex?

Take a simple, 3 beat / sec frequency. Take that wave and wrap it around the origin.

*[Figure: a wave with vectors drawn along it, and a wrapped-up plot around the origin — see original page 1]*

The vector lined up with the wave draws the "circle" on the plane. This introduces a second frequency, the cycles / second we wrap around the center. (can adjust)

When our winding freq = original freq, the center of mass of the circle is to the right.

Take only the x-coord of the center of mass. As we slowly increase cycles / sec to match the original 3 Hz, we can see that it peaks at 3 Hz.

*[Figure: graph of x-coord for c.o.m. against winding freq, with a large peak near 0, a small bump near 3, and tick marks at 3, 4, 5; vertical axis marked 0, 0.5, 1.0 — see original page 1]*

"Almost Fourier Transform"

Take 2 diff signals w diff frequencies. If you take the almost fourier transform of both, then sum the waves, you get the same as summing original waves, then applying almost Fourier transform.

Then

*[Figure: a 2 Hz wave and a 3 Hz wave, each mapped by the almost Fourier transform ("aft.") to a bump at 2 and a bump at 3 respectively; their sum, a more complex wave, maps to a graph with bumps at both 2 and 3 — see original page 2]*

the bumps describe the original frequency that went into the signal.

## Actual Fourier

Take some signal (say the 3 Hz sine wave) and call it $g(t)$.

$e^{-2\pi i f t}$, where $f$ = winding frequency and $t$ = time (rotation).

then $g(t)e^{-2\pi i f t}$ draws up the wound up wrap graph. The point of this is to track the center of mass, which leads us to $\frac{1}{N}\sum_{k=1}^{N} g(t_k)e^{-2\pi i f t_k}$ to take a bunch of samples, then instead of the limit, we have

$$\frac{1}{t_2 - t_1}\int_{t_1}^{t_2} g(t)e^{-2\pi i f t}\,dt$$

the actual Fourier transform

Then the longer the correct (right freq.) signal persists, the larger the value of the Fourier transform at that freq. For other freqs, longer times ≠ larger value since the graph balances itself out via the windings.

$$\hat{g}(f) = \int_{t_1}^{t_2} g(t)e^{-2\pi i f t}\,dt$$

*[Figure: Time domain (a jagged signal) —Fourier Trans.→ Freq. domain: individual freq's and how much they contribute — see original page 2]*

Limitations: is only a fn of freq so loses all info in the time domain. i.e. don't know when freqs begin or end.

## Time freq duality

- Let $x_1$ and $x_2$ be 2 arbitrary points of a signal.

*[Figure: two points $x_1$ and $x_2$ on a graph, with $Y_1$ marking a level between them and $Y_2$ the difference between them — see original page 3]*

$Y_1$ = Low freq. component: $Y_1 = \frac{x_1 + x_2}{2}$

$Y_2$ = High freq component: $Y_2 = x_2 - x_1$

- It's impossible to have both time and frequency resolution at the same time, there's a trade off.
  - Ex: Fourier transform is only a fn of freq and loses all info on time.

This is manifestation of Uncertainty principle: $\Delta f \Delta t \geq 1$

## Wavelet

wavelet = short lived oscillation localized in time (French: ondelette - little wave)

It's a family of functions that satisfies certain properties. Wavelets are each tuned for different occasions (could design one)

1. Zero mean (Admissibility condition)

$$\int_{-\infty}^{+\infty} \Psi(t)\,dt = 0.$$

$\Psi(t)$ being the wavelet.

2. Finite energy

$$\int_{-\infty}^{+\infty} |\Psi(t)|^2\,dt < \infty,$$

area under curve of squared wavelet fn should be finite.

## Wavelet Transform

- Fourier takes $y(t) \to \hat{y}(f)$

*[Figure: signal $y(t)$ plotted against time, mapped to a graph $\hat{y}(f)$ against Hz showing a peak — see original page 3]*

A wavelet transform has $y(t) \to T(t,f)$, $T(t,f)$ = contribution of freq $f$ at time $t$.

We can tune both time and frequency to manipulate $\Psi(t)$ - "mother wavelet." Suppose we fix time at $b$, then "daughter wavelet" $= \Psi_b = \Psi(t-b)$

Tuning frequency lets us scale mother wavelet on the time axis. If scale $= a$, then "daughter wavelet" is $\Psi_a = \Psi\left(\frac{t}{a}\right)$

Ex. $f_0 = 1$ Hz

scale by $a = 2$, then $f_a = 0.5$ (inverse relation).

Then scaled and transformed wavelet

$$\Psi_{a,b} = \Psi\left(\frac{t-b}{a}\right)$$

The value of we $T(a,b)$ at a scale $a$, time $b$ = contribution of $\Psi_{a,b}$ to our signal.

We can interpret "contribution" as goodness of fit (likelihood).

Step 1: Find where wavelet & signal have same and opposite signs. then $y(t)\cdot\Psi_{a,b}(t)$

Find total signed area: $T(a,b) = \int_{-\infty}^{+\infty} y(t)\Psi_{a,b}(t)\,dt$ = contribution.

Recall: Dot products give us an intuitive understanding on how much the vectors agree. The $\cos\theta$ doesn't matter in higher dimensions.

Let $\vec{a} = [a_1, \ldots, a_N]$, $\vec{b} = [b_1, \ldots, b_N]$, $\vec{a}\cdot\vec{b} = a_1 b_1 + \cdots + a_N b_N$.

Imagine a function as a vector in an infinite amt of dimensions.

then $(f,g) = \int_{-\infty}^{+\infty} f(t)\cdot g(t)\,dt$ so $T(a,b)$ was dot product of the two fns.

So we fix the freq, change time $b$ to slide this chunked signal $(a,b)$ across our og signal and compute this every time. This is called convolution.

Sliding wavelet across og signal gives dot product which gives another signal for us.

Morlet wavelet: $\Psi(t) = K \cdot e^{i\omega_0 t} \cdot e^{-\frac{t^2}{2}}$

We introduce complex number here for rotation. ($e^{i\omega}$ = rotation around circle at freq $\omega$)

So you get a real + imaginary =

*[Figure: sketches of real and imaginary oscillating waves, and a rosette-like tangled plot — see original page 4]*

We calculate the real and imaginary convolution.

*[Figure: complex plane with Real and Imag axes, a point at time $b$ and a vector $\vec{v}$; note: $\vec{v}$ length can scale as well based on convolution — see original page 4]*

Then our freq. contribution is given by distance of pt from origin. Then scaling $a$ at every $b$ gives us a surface of time v freq. called the wavelet scalogram.

Wavelet transforms find a good balance in Heisenberg boxes (low resolution)

- low freq have wide & short uncertainty boxes
- high freq have narrow & tall boxes
