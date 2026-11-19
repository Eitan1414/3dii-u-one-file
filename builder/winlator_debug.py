"""Console diagnostic for the Winlator single-file distribution."""
import ctypes
import os
from pathlib import Path
import shutil
import subprocess
import sys
import traceback
import zipfile

from winlator_launcher import EXE, VERSION, install, manifest

def log(message):
    print(message, flush=True)
    try:
        with (Path(os.environ.get("TEMP") or ".") / "3DiiU-debug.log").open("a", encoding="utf-8") as f:
            f.write(str(message) + "\n")
    except OSError:
        pass

def main():
    try:
        log("3Dii U Winlator diagnostic: Python started.")
        payload = Path(getattr(sys, "_MEIPASS", Path(__file__).parent)) / "payload.zip"
        base = Path(os.environ.get("LOCALAPPDATA") or str(Path.home())) / "3DiiU"
        log("Payload: " + str(payload))
        log("Installation: " + str(base / VERSION))
        base.mkdir(parents=True, exist_ok=True)
        log(f"Free storage: {shutil.disk_usage(base).free // (1024 * 1024)} MiB")
        with zipfile.ZipFile(payload) as archive:
            files, expected = manifest(archive)
            log(f"Archive opened: {len(files)} files (expected {expected}).")
            log("Checking or extracting files. Please wait...")
            dest = install(archive, base)
        log("All release files verified.")
        env = os.environ.copy()
        env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
        ctypes.windll.kernel32.SetDllDirectoryW(None)
        log("Starting original Builder...")
        child = subprocess.Popen([str(dest / EXE)], cwd=str(dest), env=env)
        log(f"Builder process started: PID {child.pid}. Waiting for exit.")
        code = child.wait()
        log(f"Builder exit code: {code} (0x{code & 0xFFFFFFFF:08X})")
    except Exception:
        log(traceback.format_exc())
    finally:
        try:
            input("Press Enter to close this diagnostic.")
        except (EOFError, OSError):
            pass

if __name__ == "__main__":
    main()
