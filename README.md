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
| **Cuts** | Lists every pause, keeps repeated takes visible so *you* choose the good one | FFmpeg |
| **Captions on every word** | Measures where each word is actually said (not where Whisper guesses), 1–2 words per caption. Fix a word, re-time in one command | WhisperX alignment |
| **Face check** | Tells you from which height captions fit below your chin, and fails if any text covers your face or mouth | MediaPipe |
| **Final review** | 1080×1920, 30 fps, H.264/AAC, −14 LUFS, true peak ≤ −1 dBTP, length — pass/fail, plus a contact sheet to look at | FFmpeg |
| **Graphics** *(optional)* | Titles, list counters and cards timed to your words, checked so nothing covers your face | HyperFrames |
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

## Tools

All through one entry point: `python3 skills/edit-reel/scripts/reel.py <command>` (`python` on Windows).

```
setup · doctor · new · transcribe · align · captions · silences · face · sfx · level · review · voice · overlaps
ff <ffmpeg-skill tool> · hf <HyperFrames command>
```

## Tested

Every push runs the full flow on **macOS and Windows** in GitHub Actions: clean install of the core module, then a
synthetic talking clip through transcribe → word timings → silences → captions → re-alignment → burned captions
→ Reels export → face check → review. See [`tests/e2e.py`](tests/e2e.py).

## Credits

Made by **Tiger Mendez** — AI builder. I edit my own reels this way; this is that workflow, cleaned up so you can
use it. Follow along on Instagram [@tigermendez_](https://instagram.com/tigermendez_) ·
[tigermendez.com](https://tigermendez.com).

Built on [ffmpeg-skill](https://github.com/kajisho5/ffmpeg-skill), [FFmpeg](https://ffmpeg.org),
[faster-whisper](https://github.com/SYSTRAN/faster-whisper), [WhisperX](https://github.com/m-bain/whisperX),
[MediaPipe](https://github.com/google-ai-edge/mediapipe), [HyperFrames](https://github.com/heygen-com/hyperframes) and [DeepFilterNet](https://github.com/Rikorose/DeepFilterNet).
Licences: [`NOTICE.md`](NOTICE.md). This project: MIT.
