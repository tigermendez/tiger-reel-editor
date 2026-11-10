# tiger-reel-editor

**Edit Reels, TikToks and Shorts with Claude Code — with you as the director.**

A skill for [Claude Code](https://claude.com/claude-code) that turns Claude into a careful editing assistant for
short vertical videos. You bring the footage and the taste. Claude helps you find the story, cuts, puts captions
exactly on every word, warns you when a text covers your face, and checks the export before you post it.
Everything runs on your computer, for free, on **macOS and Windows**.

> It will not edit your reel for you while you sleep. Good editing is judgement — what to keep, what the first
> second says, when a cut feels wrong. This skill does the slow, technical parts and measures everything, so your
> judgement is the only thing left to do.

```
npx skills add tigermendez/tiger-reel-editor
```

Then open Claude Code in a folder with your video and say: *"Edit this clip into a reel"*.

---

## What it does

| Step | What happens | Built with |
|---|---|---|
| **Story first** | Transcribes your takes, proposes the story in one line and the hook, and waits for your OK before cutting | Whisper large-v3-turbo |
| **Cuts** | Lists every pause, keeps repeated takes visible so *you* choose the good one, and points to the moments worth listening to (stumbles, half-said words) | FFmpeg · Whisper |
| **Captions on every word** | Measures where each word is actually said (not where Whisper guesses), 1–2 words per caption. Fix a word, re-time in one command | WhisperX alignment |
| **Face check** | Tells you from which height captions fit below your chin, and fails if any text covers your face or mouth | MediaPipe |
| **Sound level** | The final mix to Instagram's −14 LUFS without distortion, even when camera and voice were recorded apart | FFmpeg |
| **Final review** | 1080×1920, 30 fps, H.264/AAC, loudness, true peak, length — pass/fail, plus a contact sheet to look at | FFmpeg |
| **Graphics** *(optional)* | Titles, list counters and cards timed to your words, checked so nothing covers your face; text behind your head | HyperFrames |
| **Long video → reels** | Reads a whole podcast or live, proposes the best moments by what is said, you pick, each becomes a reel | Whisper |
| **Sound effects** | A starter set made from scratch (whoosh, pop, ding…), placed at exact times under your voice | FFmpeg |
| **Your style** | A `style.md` in your words that Claude follows and grows every time you correct it twice | — |

The hands — cutting, burning captions, loudness, exporting — come from
[**ffmpeg-skill**](https://github.com/kajisho5/ffmpeg-skill) by kajisho5 (42 FFmpeg tools, MIT), pinned to a
fixed version and hash-checked. This skill adds the editor's judgement on top.

## Requirements

- **Claude Code** with a paid Claude plan (Pro or Max).
- **macOS** on Apple Silicon (M1 or newer) or **Windows 10/11** (x64).
- **~10 GB free disk** and **8 GB RAM** (16 GB recommended).
- **Internet the first time.** After that everything works offline.
- Speed: on a 10-core Apple M4 a minute of footage transcribes in about 12 s.

> **Download size:** the core module downloads about **3.5 GB** (mostly the Whisper speech model and Python
> libraries). Claude tells you before downloading anything and asks before installing FFmpeg.

## Install

**Recommended — any agent that reads skills:**

```
npx skills add tigermendez/tiger-reel-editor
```

**As a Claude Code plugin:**

```
/plugin marketplace add tigermendez/tiger-reel-editor
/plugin install tiger-reel-editor@tiger-reel-editor
```

The first time you ask for an edit, Claude checks your machine and installs what is missing, in modules:

| Module | What you get | Download |
|---|---|---|
| **core** | FFmpeg (Homebrew / winget), ffmpeg-skill, Whisper, word-exact captions, silences, face check, review | ~3.5 GB |
| **voice** *(optional)* | Removes background noise and room echo (DeepFilterNet) | ~1 GB |
| **graphics** *(optional)* | Animated titles, lists and cards with HyperFrames, plus an overlap/face check (needs Node.js) | ~0.6 GB |

Everything goes into one folder, `~/.tiger-reel-editor`. To uninstall, delete it.
Manual install and troubleshooting: [`references/install.md`](skills/edit-reel/references/install.md).

## How a session goes

1. *"New reel: how I automated my invoices"* → a project folder; drop your clips in `raw/` (never modified).
2. Claude transcribes, asks for the names you say (so they are spelled right), and proposes **the story in one
   line**. You correct it. It fills a scene table; you approve it.
3. It cuts, puts captions on every word, exports `out/<name>_v1.mp4`.
4. It runs the review and the face check, shows you the contact sheet, and lists what is still yours to check.
5. You say what to change. Each change is a new version; nothing is overwritten.

Want animated titles, list counters or a call-to-action card? Add the **graphics** module: it installs a pinned
[HyperFrames](https://hyperframes.heygen.com) (by HeyGen) and checks that no graphic overlaps another or covers
your face before rendering. Music and sample libraries are not included (most free libraries do not allow
redistribution); you get a starter set of effects made from scratch, and
[where to get better ones](skills/edit-reel/references/sounds.md).

## It learns your style

Show it an example — a reel you like, screenshots, a template, or just a description — and Claude measures it
(hook, rhythm, where the text goes, fonts, colours, sound) and writes a **recipe** in your project's `recipes/`
folder. From then on, "do it like the *list* recipe" is enough. Recipes are starting points: mix them, bend them,
or ask for something no recipe has — Claude builds it anyway.

Everything it learns lives in plain files in your project, so you own it and can edit it:

| File | What it holds |
|---|---|
| `style.md` | Your rules in your words. Correct something twice and Claude offers to add it here. |
| `recipes/*.md` | Looks learned from examples: what defines each one, what can change, how to build it. |
| `fonts/` | Your fonts as files (bring them, or Claude gets them from Google Fonts), so they look the same anywhere. |
| `sounds/` + `sounds.txt` | Your sound effects and what each one is for. |

It ships with two recipes to start from: **soft serif in mustard yellow** (the trending "curvy letters" look: one
fixed sentence on screen) and **list to camera**. Made a recipe that would help everyone? Open a pull request adding it to
`skills/edit-reel/templates/`.

## Tools

All through one entry point: `python3 skills/edit-reel/scripts/reel.py <command>` (`python` on Windows).

```
setup · doctor · new · study · transcribe · fix · align · words · captions · text · font · silences · face · sfx · level
review · voice · overlaps · cutout
ff <ffmpeg-skill tool> · hf <HyperFrames command>
```

## Tested

Every push runs the full flow on **macOS and Windows** in GitHub Actions, on clean machines: install the core and
graphics modules from scratch, then a synthetic talking clip through transcription, word timings, the
listen-to list, silences, captions (centred, per-shot heights), re-alignment after a fix, a cut made of pieces,
burned captions, Reels export, loudness, sound effects, face check, graphics overlap check, a transparent graphics
layer, cutout and the final review — plus the error cases (no sound, missing file). See [`tests/`](tests).
It has also been used end to end on real reels (talking head with list graphics; camera + voice-over + screen
recordings), compared side by side with versions edited by hand.

## Credits

Made by **Tiger Mendez** — AI builder. I edit my own reels this way; this is that workflow, cleaned up so you can
use it. Follow along on Instagram [@tigermendez_](https://instagram.com/tigermendez_) ·
[tigermendez.com](https://tigermendez.com).

Built on [ffmpeg-skill](https://github.com/kajisho5/ffmpeg-skill), [FFmpeg](https://ffmpeg.org),
[faster-whisper](https://github.com/SYSTRAN/faster-whisper), [WhisperX](https://github.com/m-bain/whisperX),
[MediaPipe](https://github.com/google-ai-edge/mediapipe), [HyperFrames](https://github.com/heygen-com/hyperframes) and [DeepFilterNet](https://github.com/Rikorose/DeepFilterNet).
Licences: [`NOTICE.md`](NOTICE.md). This project: MIT.
