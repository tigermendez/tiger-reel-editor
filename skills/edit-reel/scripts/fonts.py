"""Fonts from files, the same on macOS and Windows. Standard library only. Called by `reel.py font` and `captions`.

A project keeps its fonts in `fonts/`. A font file the person brings is used as is; a font named (or identified from
a screenshot) is downloaded from Google Fonts' public repository (github.com/google/fonts, open licences), with its
licence file next to it.
"""
import json
import re
import struct
import sys
import urllib.request
from pathlib import Path

FONT_SUFFIXES = (".ttf", ".otf", ".ttc")


def family_name(path):
    """The family name stored inside a TTF/OTF file (what renderers match on), or the file stem as a fallback."""
    try:
        data = Path(path).read_bytes()
        off = 12 if data[:4] != b"ttcf" else struct.unpack(">I", data[12:16])[0] + 12
        n = struct.unpack(">H", data[off - 8:off - 6])[0]
        for i in range(n):
            tag, _, toff, _ = struct.unpack(">4sIII", data[off + 16 * i:off + 16 * (i + 1)])
            if tag != b"name":
                continue
            _, count, strings = struct.unpack(">HHH", data[toff:toff + 6])
            found = {}
            for j in range(count):
                pid, eid, lid, nid, length, soff = struct.unpack(">HHHHHH", data[toff + 6 + 12 * j:toff + 18 + 12 * j])
                if nid not in (1, 16):
                    continue
                raw = data[toff + strings + soff:toff + strings + soff + length]
                text = raw.decode("utf-16-be" if pid in (0, 3) else "latin-1", errors="ignore").strip("\x00 ")
                if text and (nid not in found or (pid == 3 and lid == 0x409)):
                    found[nid] = text
            return found.get(16) or found.get(1) or Path(path).stem
    except Exception:
        pass
    return Path(path).stem


def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "edit-reel", "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def download(name, folder):
    """Download every file of a Google Fonts family into folder/<Name>/. Returns the font files."""
    slug = re.sub(r"[^a-z0-9]", "", name.lower())
    target = Path(folder) / name.replace(" ", "")
    for licence in ("ofl", "apache", "ufl"):
        try:
            listing = json.loads(_get(f"https://api.github.com/repos/google/fonts/contents/{licence}/{slug}"))
        except Exception:
            continue
        files = [f for f in listing if f["type"] == "file" and
                 (f["name"].lower().endswith(FONT_SUFFIXES) or f["name"].upper().startswith(("OFL", "LICENSE")))]
        if not files:
            continue
        target.mkdir(parents=True, exist_ok=True)
        for f in files:
            (target / f["name"]).write_bytes(_get(f["download_url"]))
        return sorted(p for p in target.iterdir() if p.suffix.lower() in FONT_SUFFIXES)
    sys.exit(f"error: '{name}' was not found in Google Fonts. Check the exact name on fonts.google.com, or put the "
             "font file in fonts/ yourself.")


def find(name_or_file, folders=("fonts",)):
    """A font file and its family name: a path, or a family/file name searched in the project's fonts folders."""
    p = Path(name_or_file)
    if p.suffix.lower() in FONT_SUFFIXES and p.is_file():
        return p, family_name(p)
    want = re.sub(r"[^a-z0-9]", "", name_or_file.lower())
    for d in folders:
        for f in sorted(Path(d).rglob("*")) if Path(d).is_dir() else []:
            if f.suffix.lower() in FONT_SUFFIXES:
                fam = family_name(f)
                if want in (re.sub(r"[^a-z0-9]", "", fam.lower()), re.sub(r"[^a-z0-9]", "", f.stem.lower())):
                    return f, fam
    return None, None
