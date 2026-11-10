# Install and troubleshooting

Everything is downloaded into one folder: `~/.tiger-reel-editor` (Windows: `C:\Users\<you>\.tiger-reel-editor`).
Set `TIGER_REEL_EDITOR_HOME` to put it elsewhere. Uninstall = delete that folder (FFmpeg and uv stay; remove
them with `brew uninstall ffmpeg-full uv` or `winget uninstall Gyan.FFmpeg astral-sh.uv`).

## Modules

| Module | What | Download |
|---|---|---|
| core | ffmpeg-skill 3.2.3 (pinned, hash-checked), Whisper large-v3-turbo, WhisperX word timings (~360 MB per language), MediaPipe face model | ~3.5 GB |
| voice | DeepFilterNet: removes noise and echo | ~1 GB |

```
reel.py setup --language en,es            # core, word timings for English and Spanish
reel.py setup --module voice              # add clean voice later
reel.py setup --yes                       # also allow installing FFmpeg/uv with Homebrew or winget
reel.py doctor                            # what is installed
```

System programs: **macOS** uses Homebrew (`brew install ffmpeg-full uv`; the plain `ffmpeg` formula cannot burn
captions because it has no libass). **Windows** uses winget (`Gyan.FFmpeg`, the full build, and `astral-sh.uv`).
Python environments are created by uv with Python 3.11, so the system Python does not matter beyond running
`reel.py` itself (3.9+).

## Requirements
- macOS on Apple Silicon, or Windows 10/11 (x64). Intel Macs are not supported (no current PyTorch builds).
- ~10 GB free (downloads plus working files), 8 GB RAM minimum, 16 GB recommended.
- Internet the first time; afterwards everything runs offline.

## Problems
- **"FFmpeg was installed but is not visible yet"** (Windows): open a new terminal and run setup again.
- **Exit code 3 from setup**: it is asking permission to install FFmpeg/uv. Run the printed commands or rerun
  with `--yes`.
- **Slow transcription**: it runs on the CPU. A 60 s clip takes about 1–2 minutes on a recent laptop.
  `--model small` is faster and less accurate.
- **ffmpeg-skill download blocked**: `reel.py setup --ffmpeg-skill-from <file.tgz or folder>` installs it from a
  local copy (for example a backup fork).
- **Model downloads fail behind a proxy**: set `HTTPS_PROXY`; models come from huggingface.co and pytorch.org.
