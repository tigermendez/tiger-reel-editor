# Reviewing before you show a version

`review` and `face` are measurements. They cannot tell whether the reel is good.

## Technical (review.py)
- 1080x1920, 30 fps average, H.264 yuv420p, AAC; decodes end to end; length within the platform limit.
- Loudness is measured on the **final mix** (voice + music + effects): -14 LUFS ±1, true peak ≤ -1 dBTP.
  A clean voice at -14 with music added on top ends louder; measure after mixing, not before.

## Face (face.py)
- Run it on the export with `--texts` (the captions `.srt`, or a JSON of every on-screen text with its box).
  `--band` is the vertical strip, in pixels, where the captions are drawn.
- It finds frontal faces above 0.8 confidence. In profile, covered or far away it may miss one: look anyway.

## Safe zones (the app's own buttons and text cover these)
- Reels: top ~8 %, bottom ~20 %, right ~12 %. TikTok: top ~10 %, bottom ~22 %, right ~14 %.
  Shorts: top ~6 %, bottom ~18 %, right ~12 %. Keep text and faces out of them.

## By eye and ear (always)
- Look at the contact sheet and at the frames around every cut. Listen to every cut at full volume.
- Captions in sync with the voice, spelled right, proper names right.
- The first second: does it say what the reel is about without sound?

## How to report
Say what passed with numbers, what failed, what you could not check, and the "still yours to check" list.
Never call a version final; the person does.
