# Sound effects and music

## What you get
No music or sample libraries are shipped: most free libraries allow use in your videos but not redistribution in
a repository. Instead, setup **makes a starter set from scratch** with FFmpeg's generators (no samples, so it is
free to use anywhere): `whoosh`, `pop`, `click`, `ding`, `riser`, `impact`, all peaking at -3 dBFS, in
`~/.tiger-reel-editor/sounds`. Remake it anywhere with `reel.py sfx --starter <folder>`; list what can be called
by name with `reel.py sfx --list`.

## Better sounds
Download your own and keep them in `sounds/` in the project (or pass `--dir`); call them by file name:
- **Pixabay** (pixabay.com/sound-effects and /music): free for commercial use, no attribution required. Read the
  current licence on the site before using.
- **YouTube Audio Library**: free music and effects; some tracks require attribution.
- Your platform's in-app library for trending audio — add it in the app, not inside the MP4.

## Placing effects
`reel.py sfx <video> -o <out> --at "1.20 whoosh" --at "5.10 pop -4"`, or a cues file with one `time sound [dB]` per
line (`#` comments). Time them from `.words.json` (the word they underline) or from the graphics (the moment an
element enters, 0.05 s before). Defaults: -10 dB under each effect's peak; adjust per cue. Then `reel.py level`
(effects change the mix loudness) and listen.

Taste rules that work: one effect per new element at most; soft; whoosh for things that slide, pop for things that
appear, ding for a result, riser before a reveal, impact for the punchline; nothing over a word that matters.

## Music
`ff audio <video> --music bed.mp3 --duck` puts a bed under the voice and lowers it while someone speaks
(`--music-volume -18`, `--music-fade-out 3`). Instrumental only; 10–15 % under the voice is plenty.
