---
title: Respiratory Neurophysiology (IBL)
summary: Creating a machine learning model to fuse thermistor, airflow, and LFP recordings to track a mouse's breathing rhythm with IBL data.  
---

A mouse's breathing was recorded by three sensors at once: a **thermistor** (temperature of the air in the nose), an **airflow sensor**, and the **LFP** (local field potential, from an epidural array on the surface of the brain). Alongside them came **EMG** (muscle activity) and **video** of the animal. Every sensor sees breathing a little differently, and every sensor fails in its own way.

In the process of applying a machine learning model to the respiratory processes of mice. I worked on two questions, using four recording sessions from mouse M1 (about 8 hours at 1000 Hz) as part of a respiration + video project in the Cavelli Lab:

1. How do the three breathing sensors relate to each other, and when do they disagree?
2. When all three lose the breathing rhythm at the same time, is that a real **pause in breathing**, or something else, like movement?

## 1. Exploring one session: what does each sensor see?

I started with a single 6.6-minute session to build a pipeline I could then run on the rest.

**Each sensor has its own strengths and weaknesses:**

- **Thermistor:** the cleanest rhythm, but slow.
- **Airflow:** the noisiest. Its timing locks tightly to the thermistor's, but its amplitude swings much more. Its strongest frequency is around 7 Hz, which the LFP does *not* share, so it's probably not sniffing. That difference might later help tell sniffing apart from movement or noise.
- **LFP:** carries slightly more fast activity than the thermistor. Of the 10 channels, 0–3 track breathing best and 7–9 show it inverted.

To compare them I used two measures. **Coherence** asks whether two signals share a frequency, consistently, in both timing and amplitude. Cut both signals into ~4 s chunks, take each chunk's Fourier coefficient $X_k, Y_k$ at frequency $f$, and compute

$$C_{xy}(f) = \frac{\left|\frac{1}{K}\sum_k X_k \overline{Y_k}\right|^2}{\left(\frac{1}{K}\sum_k |X_k|^2\right)\left(\frac{1}{K}\sum_k |Y_k|^2\right)}$$

which is 1 when every chunk has the same phase difference and 0 when there's no consistent relationship. To get a chance level, I shifted one signal by 60 s so that "happening at the same time" can't be a factor.

![Coherence between each pair of sensors by frequency band](/projects/ibl/coherence.svg)

Thermistor and LFP share a strong breathing rhythm up to about 6–7 Hz. Above that, the shared rhythm fades for every pair.

The **phase-locking value (PLV)** measures timing only. After band-passing each signal to 1–15 Hz and taking its phase $\varphi(t)$ with the Hilbert transform (so all three sensors are in the same units), the PLV over a 5 s window is the length of the average phase-difference vector:

$$\text{PLV} = \left|\frac{1}{N}\sum_{n=1}^{N} e^{\,i(\varphi_x(t_n) - \varphi_y(t_n))}\right|$$

Median PLV was **0.72** for thermistor–airflow, **0.62** for thermistor–LFP and **0.38** for airflow–LFP. So thermistor and airflow agree most on *timing*, even though their *coherence* is low: their rhythms line up but their amplitudes don't.

**What I learned from this session:**

- In clean stretches, all three sensors cycle together with a stable phase difference. In messy stretches, the phase difference jumps around, because when a signal's amplitude drops its phase becomes unreliable.
- Disagreement comes in episodes, and not every one is a sensor failure. Some coincide with EMG bursts (movement). Others don't: around **88 s** and **92.5–93 s**, all three signals lose strength together with no muscle activity, each right after an unusually large airflow signal. That could be a sigh followed by a pause, or drinking followed by a swallow.

## 2. Detecting breathing pauses across all sessions

The idea: a **real pause in breathing** should make all three sensors lose their rhythm *together*, while a **sensor problem** should affect only one or two.

**The pipeline**, the same for every sensor:

1. Band-pass 1–15 Hz (3rd-order Butterworth, zero-phase) to isolate breathing.
2. Take the Hilbert amplitude (how strong the oscillation is right now), smoothed over 0.25 s.
3. Divide by its own 60 s rolling median, so sensors with different units, and drift within a session, become comparable. A ratio of 1 means "typical right now".
4. A **drop** is a stretch where the ratio stays below **0.35** for at least **0.3 s**, with gaps shorter than 0.2 s merged, since amplitude briefly bounces back between breaths.
5. Drops from different sensors that overlap by at least half of the shorter one form a single **event**, labeled by how many sensors dropped: all three, two, or one.

I tuned the threshold and minimum duration on the first session with a grid search. At 0.35, the count of all-three events was stable (5) for every minimum duration from 0.3 to 0.5 s. Looser thresholds added many extra events, and tighter ones lost the known pauses. The two pauses I'd found by eye (88 s and 92.5–93 s) are both detected as all-three events with normal EMG.

![Events per hour in each session, split by how many sensors dropped](/projects/ibl/events.svg)

Over the four sessions the pipeline found **4,652 events**. Single-sensor drops are the most common and the shortest (median about 0.4 s). All-three events are the longest (median about 1 s), which fits them being real pauses rather than noise.

## 3. Fixing the EMG: removing mains hum

Each event is also checked for movement: if the EMG's RMS (muscle "loudness", 30–300 Hz) rises above 2.5× its session median within ±1 s, the event is flagged. In one 3-hour session this flag **never fired**, 0 of 2,189 events.

The cause was **50 Hz mains hum** (electrical interference from the power lines) and its harmonics in the EMG. Because hum is steady, it adds a large constant to the RMS, so real bursts barely stand out against the median. In the July 21 session, the hum was about $10^5$ times the muscle signal and made up essentially *all* of the 30–300 Hz power.

I compared three ways to remove it (a cascade of notch filters, a comb filter, and spectral interpolation) on how much hum they leave, how much real signal they keep, and whether a synthetic burst survives. The notch cascade worked best. I then set a criterion *before* looking at the results: at most 2.5% hum left over the whole session, with no more than 5% of one-minute windows above 5%. Q = 30 is the narrowest setting that passes in every session.

![Hum left after filtering at different notch widths](/projects/ibl/notch.svg)

With notches at 50, 100, …, 350 Hz (Q = 30), the drop events themselves don't change at all, but the movement flag now works: flagged events in the July 21 session went from **0 to 315**.

To check that the newly detected bursts are real movement, I compared them with the video. Video motion during EMG bursts is much higher than in matched quiet windows (Jul 9: AUC 0.90, p = 0.0002; Jul 21: AUC 0.79, p = 0.005):

![Video motion during EMG bursts compared with quiet windows](/projects/ibl/motion.svg)

One finding stood out. All-three events are flagged with an EMG burst **2–4× more often than chance** (17% vs. 4% in the second June 18 session, 12% vs. 6% on July 9), while one- and two-sensor events are flagged at chance level. So some of the candidate breathing pauses may be movement-related, like a swallow or a head movement, and are worth inspecting before being interpreted.

## 4. Lining up video with the signals

To inspect events, each one needed an exact position in the video:

- Every event is mapped to a video frame through the camera's frame timestamps, and the number of frames in each video file is checked against the timestamps (they match exactly in all three sessions with video).
- The camera ran at 60.0047 Hz, but the MP4 files play on an exact 60 fps timeline, which is what a video player seeks on. Using the measured rate would put the position about 0.8 s early by the end of a 3-hour session, so the pipeline uses the file's own rate.
- I checked the sync by correlating whole-frame video motion with EMG at different time shifts. The best match is at 0 to +0.2 s (movement slightly after muscle activity, which is the physiological order), with r = 0.56.

I also built two tools for looking at events: a **browser viewer** that plays the video in sync with all four traces (with filters for event type, EMG flag and session), and a **clip exporter** that renders an MP4 of the video plus traces around any event. The viewer loads small precomputed windows around each event rather than hours of 1000 Hz data, with peak-preserving downsampling so short EMG spikes aren't lost.

## Open questions

- **Movement and pauses:** some all-three events co-occur with movement more than chance would predict. Separating real breathing pauses from movement-related ones is the next step.
- **Grounding:** the hum in the July 21 session is far larger than in the others. The cause (electrode, ground, cable, or room) can't be seen in the data and is worth raising with the lab.
- **A validation case that doesn't fit:** a sharp EMG burst at 95.5 s in the first session has no matching drop, because the breathing signals don't fall below the threshold there. I left this open instead of tuning the pipeline until the check passed.
- **What more is in the LFP?** The shared breathing rhythm fades around 7 Hz. More sessions might show whether there's structure at higher frequencies.

## Tools

Python (NumPy, SciPy), marimo notebooks, ffmpeg, a small JavaScript viewer with a Range-capable Python server, uv, and pytest (8 unit tests, including one that checks the notch removes hum while keeping a synthetic burst). Every parameter choice and its evidence is logged in the repository's decision log and methods document.
