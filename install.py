"""One-step installer for ai-cli - Windows, Linux, macOS.

Usage:
    git clone https://github.com/slawti/ai-cli.git
    cd ai-cli
    python install.py [--yes] [--check]

What it does:
  1. Checks Python >= 3.10 and ensures pip.
  2. Installs pipx if missing (plain `pip --user`, no new tools to find).
  3. `pipx install .` (or `pipx reinstall ai-cli` on re-run, so it doubles as updater).
  4. Makes sure the pipx bin dir is on PATH (registry on Windows,
     shell-rc export on POSIX) - new terminals pick it up automatically.
  5. Verifies `ai-cli --help` runs.

`--check` only reports what would happen. `--yes` accepts all prompts
(non-interactive shells behave as if `--yes` were passed for safe steps
and warn-only for destructive ones).
"""

import os
import platform
import shutil
import subprocess
import sys
import sysconfig
from pathlib import Path

MIN_PYTHON = (3, 10)
PACKAGE = "ai-cli"
REPO_URL = "https://github.com/slawti/ai-cli.git"


def log(msg: str) -> None:
    print(f"[install] {msg}", flush=True)


def fail(msg: str) -> "NoReturn":
    print(f"[install] ERROR: {msg}", file=sys.stderr, flush=True)
    raise SystemExit(1)


def run(cmd: list, **kwargs) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(cmd, check=True, text=True,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              **kwargs)
    except FileNotFoundError:
        fail(f"command not found: {cmd[0]}")
    except subprocess.CalledProcessError as e:
        fail(f"command failed ({e.returncode}): {' '.join(cmd)}\n{e.stdout}")


def interactive() -> bool:
    try:
        return sys.stdin.isatty()
    except Exception:
        return False


def confirm(prompt: str, assume_yes: bool) -> bool:
    if assume_yes:
        return True
    if not interactive():
        log(f"{prompt} (non-interactive: skipping)")
        return False
    try:
        return input(f"[install] {prompt} [y/N] ").strip().lower() in ("y", "yes")
    except (EOFError, KeyboardInterrupt):
        print()
        return False


def user_scripts_dir() -> Path:
    """Where `pip --user` puts executables on this OS."""
    try:
        scheme = "nt_user" if os.name == "nt" else "posix_user"
        scripts = sysconfig.get_path("scripts", scheme=scheme)
        if scripts:
            return Path(scripts)
    except Exception:
        pass
    base = Path(sysconfig.get_config_var("userbase") or Path.home())
    return base / ("Scripts" if os.name == "nt" else "bin")


def pipx_bin_dir() -> Path:
    """Default pipx binary dir on every OS."""
    return Path.home() / ".local" / "bin"


def on_path(directory: Path) -> bool:
    entries = (os.environ.get("PATH", "") or "").split(os.pathsep)
    target = os.path.normcase(os.path.normpath(str(directory)))
    return any(os.path.normcase(os.path.normpath(p or "")) == target for p in entries)


def add_to_path_windows(directory: Path) -> bool:
    """Persist dir to the per-user PATH registry value + notify the shell."""
    try:
        import winreg
    except ImportError:
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment",
                            0, winreg.KEY_READ | winreg.KEY_WRITE) as key:
            try:
                cur, _ = winreg.QueryValueEx(key, "Path")
            except FileNotFoundError:
                cur = ""
            if on_path(directory):
                return True
            winreg.SetValueEx(key, "Path", 0, winreg.REG_EXPAND_SZ,
                              (cur.rstrip(";") + ";" + str(directory)) if cur else str(directory))
        try:  # tell running programs (Explorer, etc.) the env changed
            import ctypes
            HWND_BROADCAST, WM_SETTINGCHANGE = 0xFFFF, 0x001A
            ctypes.windll.user32.SendMessageTimeoutW(
                HWND_BROADCAST, WM_SETTINGCHANGE, 0, "Environment", 0, 5000, None)
        except Exception:
            pass
        return True
    except OSError as e:
        log(f"could not update registry PATH: {e}")
        return False


def add_to_path_posix(directory: Path) -> bool:
    """Append an export line to existing shell rc files (no duplicates)."""
    line = f'export PATH="{directory}:$PATH"'
    touched = False
    for rc in (Path.home() / ".bashrc", Path.home() / ".zshrc"):
        try:
            if not rc.exists():
                continue
            text = rc.read_text(encoding="utf-8", errors="replace")
            if str(directory) in text:
                touched = True
                continue
            with rc.open("a", encoding="utf-8") as f:
                f.write(f"\n# added by ai-cli installer\n{line}\n")
            touched = True
            log(f"added PATH export to {rc}")
        except OSError as e:
            log(f"could not update {rc}: {e}")
    return touched


def persisted_on_path(directory: Path) -> bool:
    """True if a *future* terminal would have dir on PATH (registry / rc files)."""
    target = os.path.normcase(os.path.normpath(str(directory)))
    if os.name == "nt":
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment",
                                0, winreg.KEY_READ) as key:
                cur, _ = winreg.QueryValueEx(key, "Path")
        except Exception:
            return False
        return any(os.path.normcase(os.path.normpath(p or "")) == target
                   for p in (cur or "").split(";"))
    for rc in (Path.home() / ".bashrc", Path.home() / ".zshrc"):
        try:
            if rc.exists() and str(directory) in rc.read_text(encoding="utf-8", errors="replace"):
                return True
        except OSError:
            pass
    return False


def ensure_on_path(directory: Path, assume_yes: bool) -> None:
    if on_path(directory) or persisted_on_path(directory):
        log(f"{directory} is already on PATH")
        return
    log(f"{directory} is not on PATH")
    if not confirm(f"add it to PATH permanently? ({directory})", assume_yes):
        log(f"skipped - add {directory} to PATH manually, then restart your terminal")
        return
    ok = add_to_path_windows(directory) if os.name == "nt" else add_to_path_posix(directory)
    if ok:
        log("PATH updated - restart your terminal for it to take effect")
    else:
        log(f"automatic PATH update failed - add {directory} manually")


def ensure_pip() -> None:
    log("checking pip...")
    r = subprocess.run([sys.executable, "-m", "pip", "--version"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if r.returncode != 0:
        log("bootstrapping pip with ensurepip...")
        run([sys.executable, "-m", "ensurepip", "--user"])
    run([sys.executable, "-m", "pip", "install", "--user", "-q", "--upgrade", "pip"])


def search_env() -> dict:
    """Env with our known bin dirs prepended - robust against stale shells."""
    path = (str(pipx_bin_dir()) + os.pathsep + str(user_scripts_dir())
            + os.pathsep + os.environ.get("PATH", ""))
    return {**os.environ, "PATH": path}


def ensure_pipx() -> None:
    if shutil.which("pipx") or (user_scripts_dir() / "pipx.exe").exists() or (
            user_scripts_dir() / "pipx").exists():
        os.environ["PATH"] = str(user_scripts_dir()) + os.pathsep + os.environ.get("PATH", "")
        log("pipx found")
        return
    log("installing pipx...")
    run([sys.executable, "-m", "pip", "install", "--user", "-q", "pipx"])
    scripts = user_scripts_dir()
    os.environ["PATH"] = str(scripts) + os.pathsep + os.environ.get("PATH", "")
    if not shutil.which("pipx"):
        fail(f"pipx installed but not runnable (looked in {scripts})")


def pipx_exe() -> str:
    """Absolute pipx path: Windows CreateProcess ignores env-PATH for lookup."""
    found = shutil.which("pipx") or shutil.which("pipx", path=search_env()["PATH"])
    if found:
        return found
    for cand in (user_scripts_dir() / "pipx.exe", user_scripts_dir() / "pipx"):
        if cand.exists():
            return str(cand)
    return "pipx"


def pipx_installed() -> bool:
    try:
        out = subprocess.run([pipx_exe(), "list", "--short"], check=True, text=True,
                             stdout=subprocess.PIPE, stderr=subprocess.DEVNULL).stdout
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False
    return any(line.split()[0].lower() == PACKAGE for line in out.splitlines() if line.strip())


def resolve_conflict(assume_yes: bool) -> None:
    """An ai-cli outside pipx's bin dir would shadow the new install."""
    found = shutil.which("ai-cli")
    if not found:
        return
    try:
        if Path(found).parent.samefile(pipx_bin_dir()):
            return
    except OSError:
        pass
    log(f"existing ai-cli found at {found} (outside pipx bin dir - it would shadow the new install)")
    if confirm("uninstall it with `pip uninstall -y ai-cli`?", assume_yes):
        run([sys.executable, "-m", "pip", "uninstall", "-y", "-q", PACKAGE])
        log("old ai-cli uninstalled")


def install_app_here() -> None:
    root = Path(__file__).resolve().parent
    if not (root / "pyproject.toml").exists():
        fail(f"run this from the ai-cli repo root (no pyproject.toml in {root})")
    if pipx_installed():
        log("ai-cli already installed via pipx - reinstalling (upgrade)...")
        run([pipx_exe(), "reinstall", PACKAGE])
    else:
        log("installing ai-cli with pipx...")
        run([pipx_exe(), "install", str(root)])


def verify() -> None:
    exe = pipx_bin_dir() / ("ai-cli.exe" if os.name == "nt" else "ai-cli")
    if not exe.exists():
        fail(f"install finished but {exe} is missing")
    env = dict(os.environ)
    env["PATH"] = str(pipx_bin_dir()) + os.pathsep + env.get("PATH", "")
    try:
        subprocess.run([str(exe), "--help"], check=True, text=True,
                       stdout=subprocess.DEVNULL, env=env)
    except (FileNotFoundError, subprocess.CalledProcessError):
        fail(f"{exe} --help failed")
    log("verified: ai-cli runs")
    if shutil.which("ai-cli"):
        log("`ai-cli` resolves on PATH in this shell - open a NEW terminal and run: ai-cli")
    else:
        log("open a NEW terminal (PATH refresh), then run: ai-cli")


def check_only() -> None:
    exe = pipx_bin_dir() / ("ai-cli.exe" if os.name == "nt" else "ai-cli")
    print(f"python: {platform.python_version()} (need >= {'.'.join(map(str, MIN_PYTHON))})")
    print(f"pipx: {'yes' if shutil.which('pipx', path=search_env()['PATH']) else 'no'}")
    print(f"pipx bin dir: {pipx_bin_dir()} ({'on PATH' if on_path(pipx_bin_dir()) else 'NOT on PATH'})")
    print(f"ai-cli exe present: {'yes' if exe.exists() else 'no'} ({exe})")
    print(f"ai-cli via pipx: {'yes' if pipx_installed() else 'no'}")
    print(f"ai-cli on PATH: {shutil.which('ai-cli') or 'no'}")


def main(argv: list) -> int:
    assume_yes = "--yes" in argv
    if "--check" in argv:
        check_only()
        return 0
    log(f"platform: {platform.system()} {platform.machine()}, python {platform.python_version()}")
    if sys.version_info < MIN_PYTHON:
        fail(f"Python {'.'.join(map(str, MIN_PYTHON))}+ required")
    ensure_pip()                                   # [1/6]
    ensure_pipx()                                  # [2/6] (+ keep pipx itself on PATH)
    ensure_on_path(user_scripts_dir(), assume_yes)
    run([pipx_exe(), "ensurepath"])                # [3/6] best effort; we verify below
    resolve_conflict(assume_yes)                   # [4/6]
    install_app_here()
    ensure_on_path(pipx_bin_dir(), assume_yes)     # [5/6] (+ verify [6/6])
    verify()
    log("done - first launch asks for your OpenRouter API key once")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
