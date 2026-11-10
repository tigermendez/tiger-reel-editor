"""Clean a voice: removes background noise and room echo with DeepFilterNet. Runs in the 'voice' environment.

  voice.py <video|audio> <out.wav> [--max-db 15]

--max-db is how much the noise may be lowered at most: higher cleans more but sounds more processed.
The result is a 48 kHz mono WAV; put it back on the video with ffmpeg-skill's `audio.py --replace`.
"""
import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

from df.enhance import enhance, init_df, load_audio, save_audio
# -I ignores PYTHONUTF8, and Windows consoles cannot print "→" or accents in their legacy code page.
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("input")
    p.add_argument("output")
    p.add_argument("--max-db", type=float, default=15.0)
    a = p.parse_args()
    model, state, _ = init_df(log_level="ERROR")
    with tempfile.TemporaryDirectory() as tmp:
        wav = Path(tmp) / "audio.wav"
        subprocess.run(["ffmpeg", "-nostdin", "-y", "-loglevel", "error", "-i", a.input, "-vn", "-ac", "1",
                        "-ar", str(state.sr()), str(wav)], check=True)
        audio, _ = load_audio(str(wav), sr=state.sr())
        save_audio(a.output, enhance(model, state, audio, atten_lim_db=a.max_db), state.sr())
    print(f"clean voice → {a.output}")


if __name__ == "__main__":
    main()
