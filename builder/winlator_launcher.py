"""Single-file distribution launcher for the official 3Dii U Windows build.

This is a packaging experiment for Winlator, not a native Android port.
Keep the original application's files and licence notices intact.
"""
import ctypes
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import tempfile
import zipfile

VERSION = "1.0.2-2026-11-15.11"
EXE = "3Dii U Builder.exe"
REQUIRED = (
    EXE, "_internal/files.txt", "_internal/stamp.txt",
    "engine/stamp.txt", "engine/tools/win/build3ds.py",
    "engine/devkitpro/devkitPPC/bin/powerpc-eabi-gcc.exe",
    "engine/bin/shadergen.exe",
    "engine/third_party/cafeglsl/glslcompiler.exe",
)


def manifest(archive):
    """Return the original release's files, relative to its application folder."""
    files = {}
    roots = [entry.filename for entry in archive.infolist()
             if not entry.is_dir() and PurePosixPath(entry.filename).name == EXE]
    if len(roots) != 1:
        raise ValueError("Expected exactly one original Builder executable")
    prefix = roots[0][:-len(EXE)]
    for entry in archive.infolist():
        if entry.is_dir() or not entry.filename.startswith(prefix):
            continue
        name = entry.filename[len(prefix):]
        parts = PurePosixPath(name).parts
        if not parts or any(p in (".", "..", "/") or ":" in p or "\\" in p for p in parts):
            raise ValueError("Unsafe archive path: " + name)
        if name in files:
            raise ValueError("Duplicate archive path: " + name)
        files[name] = entry
    if len({name.casefold() for name in files}) != len(files):
        raise ValueError("Case-insensitive filename collision")
    for name in REQUIRED:
        if name not in files:
            raise ValueError("Missing original file in archive: " + name)
    expected = int(archive.read(files["_internal/files.txt"]).decode("ascii").strip())
    if len(files) < expected:
        raise ValueError(f"Original archive contains {len(files)} files; Builder expects {expected}")
    if archive.read(files["_internal/stamp.txt"]) != archive.read(files["engine/stamp.txt"]):
        raise ValueError("Original release contains different engine and app versions")
    return files, expected


def verify(folder, files):
    for name, info in files.items():
        path = folder.joinpath(*PurePosixPath(name).parts)
        if not path.is_file() or path.stat().st_size != info.file_size:
            raise OSError("Missing or truncated extracted file: " + name)


def install(archive, base):
    files, expected = manifest(archive)
    dest = base / VERSION
    if dest.is_dir():
        verify(dest, files)
        return dest
    base.mkdir(parents=True, exist_ok=True)
    needed = sum(info.file_size for info in files.values())
    if shutil.disk_usage(base).free < needed + 32 * 1024 * 1024:
        raise OSError("Not enough free storage to unpack 3Dii U Builder")
    stage = Path(tempfile.mkdtemp(prefix="stage-", dir=base))
    try:
        for name, info in files.items():
            path = stage.joinpath(*PurePosixPath(name).parts)
            path.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info) as source, path.open("xb") as target:
                shutil.copyfileobj(source, target, 1024 * 1024)
        verify(stage, files)
        if sum(len(names) for _, _, names in os.walk(stage)) < expected:
            raise OSError("File count after unpacking is below expectation")
        try:
            stage.rename(dest)
        except OSError:
            if not dest.is_dir():
                raise
            verify(dest, files)
        return dest
    finally:
        if stage.exists():
            shutil.rmtree(stage, ignore_errors=True)


def main():
    if len(sys.argv) == 3 and sys.argv[1] == "--check-archive":
        with zipfile.ZipFile(sys.argv[2]) as archive:
            files, expected = manifest(archive)
            bad = archive.testzip()
            if bad:
                raise ValueError("CRC failed: " + bad)
            print(f"Original archive verified: {len(files)} files; expected {expected}")
        return
    try:
        payload = Path(getattr(sys, "_MEIPASS", Path(__file__).parent)) / "payload.zip"
        base = Path(os.environ.get("LOCALAPPDATA") or str(Path.home())) / "3DiiU"
        with zipfile.ZipFile(payload) as archive:
            dest = install(archive, base)
        env = os.environ.copy()
        env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
        # The child is another independent PyInstaller executable.
        ctypes.windll.kernel32.SetDllDirectoryW(None)
        subprocess.Popen([str(dest / EXE)], cwd=str(dest), env=env)
    except Exception as exc:
        ctypes.windll.user32.MessageBoxW(
            None, f"3Dii U could not start:\n\n{exc}\n\n"
            "If an installed file is damaged, rename the version folder "
            "inside LocalAppData\\3DiiU and try again. Your game workspace is separate.",
            "3Dii U One File", 0x10)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
