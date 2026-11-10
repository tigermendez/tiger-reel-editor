# Sound effects and music

## What you get, and why no library is included
Free libraries like Pixabay let you use their sounds **in your videos**, but their licence forbids distributing
the files on their own — and a public repository would be exactly that. So this skill ships no samples. Instead,
setup **makes a starter set from scratch** with FFmpeg's generators (ours, MIT, usable anywhere): `whoosh`, `pop`,
`click`, `ding`, `riser`, `impact`, in `~/.tiger-reel-editor/sounds`, each described in its `sounds.txt`.
`reel.py sfx --list` shows every sound you can call by name and what it is for.

## How Claude knows what a sound is: `sounds.txt`
Claude cannot hear. It picks sounds from their names and from `sounds.txt` in each sounds folder: one line per file
(name without extension), what it sounds like and when to use it:

```
vine-boom: deep comic boom, 1 s — the joke or an absurd fact, never on a serious point
```

When the person adds files, `reel.py sfx --list` marks them "(no description yet)". Ask the person what each one
sounds like and when they want it (they can play it), then write the line:
`reel.py sfx --describe vine-boom "deep comic boom, 1 s — the joke or an absurd fact" --dir sounds`.
Tell them once, in plain words: "save new sounds in the `sounds` folder of your project with a clear name, and tell
me what each one is the first time — I write it down so I use it right from then on."

## Getting better sounds (download by hand, save in `sounds/`)
Open the link, press Download, save the file in your project's `sounds/` folder with the name in the first column,
and add its line (ready below) to `sounds/sounds.txt`.

| Save as | Pixabay page | Line for `sounds.txt` |
|---|---|---|
| `vine-boom.mp3` | [Vine boom — Fzst](https://pixabay.com/sound-effects/film-special-effects-vine-boom-162668/) | `vine-boom: deep comic boom — the joke or an absurd fact, never on a serious point` |
| `punch.mp3` | [Classic Punch Impact — Universfield](https://pixabay.com/sound-effects/film-special-effects-classic-punch-impact-352711/) | `punch: punchy hit — a hard statement, a "boom, done" moment` |
| `correct.mp3` | [Correct — DRAGON-STUDIO](https://pixabay.com/sound-effects/technology-correct-472358/) | `correct: game-like "correct" chime — a right answer, a passed check` |
| `record-scratch.mp3` | [record_scratch — freesound_community](https://pixabay.com/sound-effects/film-special-effects-record-scratch-108233/) | `record-scratch: vinyl scratch — "wait, what?", a twist or a stop` |
| `wow.mp3` | [Wow! — DRAGON-STUDIO](https://pixabay.com/sound-effects/film-special-effects-wow-423653/) | `wow: voice "wow!" — a surprising result (use rarely)` |

For more, search Pixabay by type and pick short ones (under 1 s for accents):
[whoosh](https://pixabay.com/sound-effects/search/whoosh/) ·
[pop](https://pixabay.com/sound-effects/search/pop/) ·
[click](https://pixabay.com/sound-effects/search/click/) ·
[ding](https://pixabay.com/sound-effects/search/ding/) ·
[riser](https://pixabay.com/sound-effects/search/riser/) ·
[typing](https://pixabay.com/sound-effects/search/typing/).
The **YouTube Audio Library** is another free source.

## Placing effects
`reel.py sfx <video> -o <out> --at "1.20 whoosh" --at "5.10 pop -4"`, or a cues file with one `time sound [dB]` per
line (`#` comments). Time them from `.words.json` (the word they underline) or from the graphics (the moment an
element enters, 0.05 s before). Defaults: -10 dB under each effect's peak; adjust per cue. Then `reel.py level`
(effects change the mix loudness) and ask the person to listen: you cannot judge how they sound.

Taste rules that work: one effect per new element at most; soft; follow each sound's line in `sounds.txt`;
nothing over a word that matters; fewer is better.

## Music
`ff audio <video> --music bed.mp3 --duck` puts a bed under the voice and lowers it while someone speaks
(`--music-volume -18`, `--music-fade-out 3`). Instrumental only; 10–15 % under the voice is plenty. Trending
audio is added in the app, not inside the MP4.
