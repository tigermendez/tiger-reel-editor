# Third-party software

This repository contains no third-party code. At install time, `reel.py setup` downloads:

| What | Licence | How it is used |
|---|---|---|
| [ffmpeg-skill](https://github.com/kajisho5/ffmpeg-skill) 3.2.3 by kajisho5 | MIT | Pinned npm tarball, checked against its published sha512; all cutting, burning, loudness and export |
| [FFmpeg](https://ffmpeg.org) | LGPL/GPL (build dependent) | Installed with Homebrew (`ffmpeg-full`) or winget (`Gyan.FFmpeg`) |
| [faster-whisper](https://github.com/SYSTRAN/faster-whisper) + Whisper large-v3-turbo | MIT | Speech to text |
| [WhisperX](https://github.com/m-bain/whisperX) | BSD-2-Clause | Word timings (wav2vec2 alignment models from torchaudio/Hugging Face, each under its own licence) |
| [MediaPipe](https://github.com/google-ai-edge/mediapipe) + BlazeFace short range | Apache-2.0 | Face check |
| [HyperFrames](https://github.com/heygen-com/hyperframes) 0.9.27 by HeyGen (graphics module) | Apache-2.0 | Pinned npm package; renders HTML graphics with its own headless Chrome |
| [DeepFilterNet](https://github.com/Rikorose/DeepFilterNet) (voice module) | MIT / Apache-2.0 | Clean voice |

No music or sample sound effects are included. The starter effects are synthesised at setup from FFmpeg's
generators (`skills/edit-reel/scripts/sfx.py`), part of this MIT project. See `skills/edit-reel/references/sounds.md`.
