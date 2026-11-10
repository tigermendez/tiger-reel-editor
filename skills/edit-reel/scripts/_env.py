"""Shared paths and helpers. Standard library only, so it runs before anything is installed."""
import os
import shutil
import subprocess
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
SCRIPTS = SKILL_DIR / "scripts"
IS_WIN = os.name == "nt"
IS_MAC = sys.platform == "darwin"

# Everything this skill downloads lives in one folder, so uninstalling is deleting it.
HOME = Path(os.environ.get("TIGER_REEL_EDITOR_HOME") or (Path.home() / ".tiger-reel-editor")).expanduser()
ENVS = HOME / "envs"
MODELS = HOME / "models"

# The "hands": kajisho5/ffmpeg-skill, pinned. The tarball is checked against npm's published hash.
FFMPEG_SKILL_VERSION = "3.2.3"
FFMPEG_SKILL_TARBALL = f"https://registry.npmjs.org/ffmpeg-skill/-/ffmpeg-skill-{FFMPEG_SKILL_VERSION}.tgz"
FFMPEG_SKILL_INTEGRITY = "sha512-HlkcmQnSxCIHyHTiLO/1sDux96Ndi1GXdzQGA5fUR++PdLSu1pr8g/b/TQpmHeBOg/eSTeskmHxYhelbSt1TsQ=="
FFMPEG_SKILL_DIR = HOME / "ffmpeg-skill" / FFMPEG_SKILL_VERSION

# Default speech model: Whisper large-v3-turbo converted for faster-whisper (~1.6 GB).
WHISPER_MODEL = os.environ.get("TIGER_REEL_EDITOR_WHISPER_MODEL", "large-v3-turbo")
FACE_MODEL = MODELS / "blaze_face_short_range.tflite"


def venv_python(name):
    return ENVS / name / ("Scripts/python.exe" if IS_WIN else "bin/python")


def _extra_paths():
    """Places where FFmpeg lands but that may not be on PATH yet."""
    out = []
    if IS_MAC:
        # Homebrew's plain `ffmpeg` has no libass/drawtext (no burned-in captions); `ffmpeg-full` does, but it is keg-only.
        for prefix in ("/opt/homebrew", "/usr/local"):
            out.append(f"{prefix}/opt/ffmpeg-full/bin")
    if IS_WIN:
        local = os.environ.get("LOCALAPPDATA")
        if local:
            out.append(str(Path(local) / "Microsoft" / "WinGet" / "Links"))  # winget puts shims here
    return [p for p in out if Path(p).is_dir()]


def env():
    e = dict(os.environ)
    e["PATH"] = os.pathsep.join(_extra_paths() + [e.get("PATH", "")])
    e.setdefault("HF_HOME", str(MODELS / "huggingface"))
    e.setdefault("TORCH_HOME", str(MODELS / "torch"))
    e.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
    e.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
    e.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")  # progress bars flood the agent's context
    e.setdefault("TQDM_DISABLE", "1")
    e["PYTHONIOENCODING"] = "utf-8"
    e["PYTHONUTF8"] = "1"
    return e


def which(tool):
    return shutil.which(tool, path=env()["PATH"])


def run(cmd, check=True, **kw):
    kw.setdefault("env", env())
    return subprocess.run([str(c) for c in cmd], check=check, **kw)


def need(tool, hint):
    if not which(tool):
        sys.exit(f"error: {tool} not found. {hint}\nRun: python {SCRIPTS / 'reel.py'} setup")
    return which(tool)


def in_venv(name, script, args):
    """Run one of our scripts inside a module's private Python environment."""
    py = venv_python(name)
    if not py.exists():
        module = {"core": "core", "face": "core", "voice": "voice"}.get(name, name)
        sys.exit(f"error: the '{module}' module is not installed.\n"
                 f"Run: python {SCRIPTS / 'reel.py'} setup --module {module}")
    return run([py, "-I", SCRIPTS / script, *args], check=False).returncode
