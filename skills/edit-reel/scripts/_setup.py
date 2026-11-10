"""Install and check the modules. Standard library only.

Every module installs only what is missing, so running setup again is the way to repair or update.
System programs (FFmpeg, uv) are installed with Homebrew on macOS and winget on Windows, and only with --yes:
without it, setup prints the exact commands and stops, so the person can approve them first.
"""
import base64
import hashlib
import io
import json
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path

import _env as E

PY = "3.11"

# Pinned so every machine gets the same thing; CI proves these on macOS and Windows.
MODULES = {
    "core": {
        "about": "FFmpeg + ffmpeg-skill, Whisper large-v3-turbo, word-exact captions (WhisperX), silences, face check, review",
        "size_gb": 3.5,
        "envs": {
            "core": ["whisperx==3.8.6"],
            "face": ["mediapipe==1.1.1"],
        },
    },
    "voice": {
        "about": "Clean voice: removes background noise and room echo (DeepFilterNet)",
        "size_gb": 1.0,
        "envs": {"voice": ["deepfilternet==0.5.6", "torch==2.5.1", "torchaudio==2.5.1", "numpy<2"]},
    },
    "graphics": {
        "about": "Animated titles, lists, cards and captions in HTML (HyperFrames by HeyGen) + overlap/face check",
        "size_gb": 0.6,
        "envs": {},
        "npm": {"hyperframes": "0.9.27"},
    },
}
NODE_MIN = 18

FACE_MODEL_URL = ("https://storage.googleapis.com/mediapipe-models/face_detector/"
                  "blaze_face_short_range/float16/1/blaze_face_short_range.tflite")


def ok(msg):
    print(f"  ok  {msg}")


def bad(msg):
    print(f"  --  {msg}")


# ---------------------------------------------------------------- this computer

def ram_gb():
    try:
        if E.IS_MAC:
            return int(subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, text=True).stdout) / 2**30
        if E.IS_WIN:
            import ctypes

            class MEM(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                            ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                            ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                            ("sullAvailExtendedVirtual", ctypes.c_ulonglong)]
            m = MEM()
            m.dwLength = ctypes.sizeof(MEM)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
            return m.ullTotalPhys / 2**30
        with open("/proc/meminfo") as f:
            return int(f.readline().split()[1]) / 2**20
    except Exception:
        return None


def machine_problem():
    """A reason this computer cannot run the skill, or None. Checked before downloading anything."""
    if E.IS_MAC:
        arm = subprocess.run(["sysctl", "-n", "hw.optional.arm64"], capture_output=True, text=True).stdout.strip()
        if arm != "1":
            return ("this Mac has an Intel processor. edit-reel needs a Mac with Apple Silicon (M1 or newer): "
                    "the speech and face models it uses (PyTorch, MediaPipe) no longer publish Intel Mac versions. "
                    "Nothing was installed.")
    return None


def machine_notes():
    notes = []
    gb = ram_gb()
    if gb is not None and gb < 7.5:
        notes.append(f"only {gb:.0f} GB of RAM: transcription may be very slow or run out of memory (8 GB minimum, "
                     "16 GB recommended). Close other apps while it runs.")
    if E.IS_WIN and platform.machine().upper() in ("ARM64", "AARCH64"):
        notes.append("Windows on ARM is not tested; it may fail to install the speech models.")
    return notes, gb


# ---------------------------------------------------------------- system programs

def ffmpeg_state():
    """(found, has_libass, version line)."""
    ff = E.which("ffmpeg")
    if not ff or not E.which("ffprobe"):
        return False, False, None
    ver = subprocess.run([ff, "-hide_banner", "-version"], capture_output=True, text=True, env=E.env()).stdout.splitlines()
    filters = subprocess.run([ff, "-hide_banner", "-filters"], capture_output=True, text=True, env=E.env()).stdout
    libass = any(line.split()[1:2] == ["subtitles"] for line in filters.splitlines() if len(line.split()) > 1)
    return True, libass, (ver[0] if ver else "ffmpeg")


def node_ok():
    node = E.which("node")
    if not node or not E.which("npm"):
        return False
    v = subprocess.run([node, "--version"], capture_output=True, text=True).stdout.strip().lstrip("v")
    return int(v.split(".")[0] or 0) >= NODE_MIN


def system_plan(want_node=False):
    """Commands that would install the missing system programs on this OS."""
    found, libass, _ = ffmpeg_state()
    cmds = []
    need_node = want_node and not node_ok()
    if E.IS_MAC:
        if not E.which("brew"):
            return None, "Homebrew is needed first: https://brew.sh"
        if not found or not libass:
            cmds.append(["brew", "install", "ffmpeg-full"])  # plain `ffmpeg` cannot burn captions (no libass)
        if not E.which("uv"):
            cmds.append(["brew", "install", "uv"])
        if need_node:
            cmds.append(["brew", "install", "node"])
    elif E.IS_WIN:
        if not E.which("winget"):
            return None, "winget is needed (App Installer from the Microsoft Store)."
        flags = ["--accept-source-agreements", "--accept-package-agreements", "--silent", "-e"]
        if not found or not libass:
            cmds.append(["winget", "install", "--id", "Gyan.FFmpeg", *flags])  # full build, includes libass
        if not E.which("uv"):
            cmds.append(["winget", "install", "--id", "astral-sh.uv", *flags])
        if need_node:
            cmds.append(["winget", "install", "--id", "OpenJS.NodeJS.LTS", *flags])
    else:
        missing = [n for n, ok_ in (("ffmpeg (with libass)", found and libass), ("uv", E.which("uv"))) if not ok_]
        if missing:
            return None, ("Linux is not officially supported yet. Install " + ", ".join(missing) +
                          " with your package manager (uv: https://docs.astral.sh/uv/).")
    return cmds, None


def ensure_system(yes, want_node=False):
    cmds, problem = system_plan(want_node)
    if problem:
        sys.exit(f"error: {problem}")
    if cmds and not yes:
        print("These system programs are missing. Approve, then run setup again with --yes:\n")
        for c in cmds:
            print("    " + " ".join(c))
        sys.exit(3)
    for c in cmds:
        print("$ " + " ".join(c))
        E.run(c)
    found, libass, ver = ffmpeg_state()
    if not found:
        sys.exit("error: FFmpeg was installed but is not visible yet. Open a new terminal and run setup again.")
    ok(ver)
    (ok if libass else bad)("FFmpeg can burn captions (libass)" if libass else
                            "this FFmpeg has no libass: burned-in captions will not work")
    ok(f"uv {subprocess.run([E.which('uv'), '--version'], capture_output=True, text=True).stdout.split()[1]}")
    if want_node:
        if not node_ok():
            sys.exit(f"error: Node.js {NODE_MIN}+ was installed but is not visible yet. Open a new terminal and run setup again.")
        ok(f"Node.js {subprocess.run([E.which('node'), '--version'], capture_output=True, text=True).stdout.strip()}")


# ---------------------------------------------------------------- ffmpeg-skill (the hands)

def ensure_ffmpeg_skill(source=None):
    d = E.FFMPEG_SKILL_DIR
    if (d / "SKILL.md").exists() and (d / "scripts" / "cut.py").exists():
        ok(f"ffmpeg-skill {E.FFMPEG_SKILL_VERSION}")
        return
    if source:  # a local .tgz or folder, e.g. a backup fork, when the registry is unreachable
        src = Path(source)
        if src.is_dir():
            shutil.copytree(src, d)
            ok(f"ffmpeg-skill from {src}")
            return
        data = src.read_bytes()
    else:
        print(f"  ..  downloading ffmpeg-skill {E.FFMPEG_SKILL_VERSION} (npm, ~0.5 MB)")
        with urllib.request.urlopen(E.FFMPEG_SKILL_TARBALL, timeout=120) as r:
            data = r.read()
        algo, want = E.FFMPEG_SKILL_INTEGRITY.split("-", 1)
        got = base64.b64encode(hashlib.new(algo, data).digest()).decode()
        if got != want:
            sys.exit("error: ffmpeg-skill tarball does not match its pinned hash; refusing to install it.")
    tmp = Path(tempfile.mkdtemp(prefix="ffmpeg-skill-", dir=E.HOME))
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as t:
        for m in t.getmembers():  # no absolute paths, no "..", no links
            if m.issym() or m.islnk() or m.name.startswith("/") or ".." in Path(m.name).parts:
                sys.exit(f"error: unexpected entry in the ffmpeg-skill tarball: {m.name}")
        t.extractall(tmp)
    d.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(tmp / "package"), str(d))
    shutil.rmtree(tmp, ignore_errors=True)
    ok(f"ffmpeg-skill {E.FFMPEG_SKILL_VERSION} → {d}")


# ---------------------------------------------------------------- Python environments and models

def ensure_env(name, packages):
    py = E.venv_python(name)
    marker = py.parent.parent / ".packages.json"
    if py.exists() and marker.exists() and json.loads(marker.read_text()) == packages:
        ok(f"environment '{name}'")
        return
    uv = E.which("uv")
    print(f"  ..  environment '{name}': {' '.join(packages)} (this can take a few minutes)")
    E.run([uv, "venv", "--quiet", "--allow-existing", "--python", PY, py.parent.parent])
    E.run([uv, "pip", "install", "--quiet", "--python", py, *packages])
    marker.write_text(json.dumps(packages))
    ok(f"environment '{name}'")


def py_in(name, code):
    return E.run([E.venv_python(name), "-I", "-c", code], check=False).returncode == 0


def ensure_core_models(languages, model):
    print(f"  ..  speech model '{model}' (~1.6 GB the first time)")
    if not py_in("core", "import sys\nfrom faster_whisper.utils import download_model\n"
                          f"print('  ok  speech model in', download_model({model!r}))"):
        sys.exit("error: could not download the speech model.")
    for lang in languages:
        print(f"  ..  word-timing model for '{lang}' (~360 MB the first time)")
        code = ("import warnings; warnings.filterwarnings('ignore')\nimport whisperx\n"
                f"whisperx.load_align_model(language_code={lang!r}, device='cpu')\nprint('  ok  word timings: {lang}')")
        if not py_in("core", code):
            sys.exit(f"error: no word-timing model for '{lang}'.")
    if not E.FACE_MODEL.exists():
        E.MODELS.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(FACE_MODEL_URL, timeout=120) as r:
            E.FACE_MODEL.write_bytes(r.read())
    ok("face model (BlazeFace, 0.2 MB)")
    if not (E.SOUNDS / "whoosh.wav").exists():
        import sfx
        sfx.make_starter(E.SOUNDS)
    ok(f"starter sound effects in {E.SOUNDS}")


def ensure_npm(packages):
    """Pinned Node packages in <home>/graphics, plus the headless Chrome HyperFrames renders with."""
    d = E.GRAPHICS
    d.mkdir(parents=True, exist_ok=True)
    pkg = {"name": "tiger-reel-editor-graphics", "private": True, "dependencies": packages}
    marker = d / "package.json"
    have = json.loads(marker.read_text()) if marker.exists() else {}
    npm = E.which("npm")
    if have.get("dependencies") != packages or not (d / "node_modules" / "hyperframes").exists():
        print(f"  ..  {', '.join(f'{k}@{v}' for k, v in packages.items())} (npm)")
        marker.write_text(json.dumps(pkg, indent=2))
        E.run([npm, "install", "--no-fund", "--no-audit", "--loglevel", "error"], cwd=d, shell=E.IS_WIN)
    ok(f"hyperframes {packages['hyperframes']}")
    hf = E.hyperframes_cmd()
    E.run([*hf, "telemetry", "disable"], cwd=d, stdout=subprocess.DEVNULL, check=False)
    print("  ..  Chrome for rendering (~150 MB the first time)")
    E.run([*hf, "browser", "ensure"], cwd=d, stdout=subprocess.DEVNULL)
    ok("headless Chrome")


def ensure_voice_model():
    if not py_in("voice", "from df.enhance import init_df; init_df(log_level='ERROR'); print('  ok  DeepFilterNet model')"):
        sys.exit("error: DeepFilterNet did not load.")


# ---------------------------------------------------------------- entry points

def setup(modules, yes=False, languages=("en",), model=None, ffmpeg_skill_from=None):
    problem = machine_problem()
    if problem:
        sys.exit(f"error: {problem}")
    notes, gb = machine_notes()
    for n in notes:
        print(f"  !!  {n}")
    E.HOME.mkdir(parents=True, exist_ok=True)
    free = shutil.disk_usage(E.HOME).free / 1e9
    need = sum(MODULES[m]["size_gb"] for m in modules)
    print(f"Installing into {E.HOME}  (needs ~{need:.1f} GB, {free:.0f} GB free)")
    if free < need + 1:
        sys.exit("error: not enough free disk space.")
    print("System")
    ensure_system(yes, want_node="graphics" in modules)
    for m in modules:
        print(f"Module '{m}': {MODULES[m]['about']}")
        if m == "core":
            ensure_ffmpeg_skill(ffmpeg_skill_from)
        for name, pkgs in MODULES[m]["envs"].items():
            ensure_env(name, pkgs)
        if m == "core":
            ensure_core_models(languages, model or E.WHISPER_MODEL)
        if m == "voice":
            ensure_voice_model()
        if MODULES[m].get("npm"):
            ensure_npm(MODULES[m]["npm"])
    print("Done. Check everything with: python " + str(E.SCRIPTS / "reel.py") + " doctor")


def doctor():
    """Report what is installed. Exit 0 when the core module is ready."""
    print(f"Home: {E.HOME}")
    problem = machine_problem()
    if problem:
        bad(problem)
        return 1
    notes, gb = machine_notes()
    ok(f"{platform.system()} {platform.machine()}" + (f", {gb:.0f} GB RAM" if gb else ""))
    for n in notes:
        print(f"  !!  {n}")
    found, libass, ver = ffmpeg_state()
    (ok if found else bad)(ver or "FFmpeg not found")
    if found:
        (ok if libass else bad)("libass (burned-in captions)")
    (ok if E.which("uv") else bad)("uv" if E.which("uv") else "uv not found")
    core_ready = found and bool(E.which("uv"))
    has_skill = (E.FFMPEG_SKILL_DIR / "SKILL.md").exists()
    (ok if has_skill else bad)(f"ffmpeg-skill {E.FFMPEG_SKILL_VERSION}")
    core_ready &= has_skill
    for m, spec in MODULES.items():
        present = all(E.venv_python(n).exists() for n in spec["envs"])
        if spec.get("npm"):
            present = present and (E.GRAPHICS / "node_modules" / "hyperframes").exists()
        (ok if present else bad)(f"module '{m}'" + ("" if present else f"  (install: reel.py setup --module {m})"))
        if m == "core":
            core_ready &= present and E.FACE_MODEL.exists()
    print("Core module ready." if core_ready else "Core module not ready: run reel.py setup")
    return 0 if core_ready else 1
