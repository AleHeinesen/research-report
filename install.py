#!/usr/bin/env python3
"""Install research-report, together with the fetch engine it calls.

    python install.py                        # auto-detect harness; installs both
    python install.py --target claude        # dsh | claude | cursor | agents
    python install.py --engine-src ../accessing-blocked-sites   # use a local checkout
    python install.py --engine-url https://github.com/AleHeinesen/accessing-blocked-sites

research-report ships no fetching code. This installer therefore resolves the
engine from, in order:

  1. --engine-src <path>            a local checkout of the engine repo
  2. ../accessing-blocked-sites     the sibling checkout used in development
  3. the target skills root         an engine that is already installed
  4. git clone --depth 1 <engine-url>

and copies the engine's skill into place next to research-report. Nothing is
downloaded at task time: if the engine is missing later, the skill reports it.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPORT = "research-report"
ENGINE = "accessing-blocked-sites"
REPORT_SRC = ROOT / "skills" / REPORT

DEFAULT_ENGINE_URL = "https://github.com/AleHeinesen/accessing-blocked-sites"
DEFAULT_ENGINE_REF = "main"

TARGETS = {
    "dsh": Path.home() / ".dsh" / "skills",
    "claude": Path.home() / ".claude" / "skills",
    "cursor": Path.home() / ".cursor" / "skills",
    "agents": Path.home() / ".agents" / "skills",
}

IGNORE = shutil.ignore_patterns(".venv", "__pycache__", "*.pyc", "*.pyo", ".DS_Store", ".install.json")

_TEMP_DIRS: list[Path] = []


def cleanup_temp() -> None:
    for path in _TEMP_DIRS:
        shutil.rmtree(path, ignore_errors=True)
    _TEMP_DIRS.clear()


def die(message: str) -> None:
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(2)


def log(message: str) -> None:
    print(message, flush=True)


def detect_target() -> str | None:
    for name in ("dsh", "claude", "cursor", "agents"):
        if TARGETS[name].parent.exists():
            return name
    return None


def resolve_target(target: str, explicit_dir: str | None) -> tuple[Path, str]:
    if explicit_dir:
        return Path(explicit_dir).expanduser().resolve(), explicit_dir
    name = detect_target() if target == "auto" else target
    if not name:
        die("no harness found in ~/.dsh, ~/.claude, ~/.cursor or ~/.agents.\n"
            "  Pass --target <name> or --dir <skills directory>.")
    if name not in TARGETS:
        die(f"unknown target {name!r}; choose from {', '.join(TARGETS)}")
    return TARGETS[name], name


def engine_skill_dir(repo: Path) -> Path:
    return repo / "skills" / ENGINE


def looks_like_engine(repo: Path) -> bool:
    return (engine_skill_dir(repo) / "scripts" / "batch_fetch.py").is_file()


def clone_engine(url: str, ref: str) -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="engine-"))
    _TEMP_DIRS.append(tmp)
    log(f"  cloning {url} @ {ref}")
    try:
        subprocess.run(["git", "clone", "--quiet", "--depth", "1", "--branch", ref,
                        url, str(tmp / "engine")],
                       check=True, capture_output=True, text=True, timeout=300)
    except Exception as exc:
        shutil.rmtree(tmp, ignore_errors=True)
        detail = getattr(exc, "stderr", "") or str(exc)
        die(f"could not clone the engine ({url} @ {ref}):\n  {str(detail).strip()}\n"
            "  Retry with --engine-src <local checkout>, --engine-url <mirror>, "
            "or install the engine repo first and re-run.")
    repo = tmp / "engine"
    if not looks_like_engine(repo):
        shutil.rmtree(tmp, ignore_errors=True)
        die(f"cloned {url} but no skills/{ENGINE}/scripts/batch_fetch.py inside; "
            "pass --engine-src <checkout of the engine repo>")
    return repo


def resolve_engine(args, target_root: Path) -> tuple[Path, str, bool]:
    """Return (repo_root, how, already_in_place)."""
    if args.engine_src:
        repo = Path(args.engine_src).expanduser().resolve()
        if not looks_like_engine(repo):
            die(f"--engine-src {repo} is not an engine checkout "
                f"(expected {repo}/skills/{ENGINE}/scripts/batch_fetch.py)")
        return repo, "flag", False

    sibling = ROOT.parent / ENGINE
    if looks_like_engine(sibling):
        return sibling, "sibling checkout", False

    if (target_root / ENGINE / "scripts" / "batch_fetch.py").is_file():
        return target_root, "already installed", True

    return clone_engine(args.engine_url, args.engine_ref), "cloned", False


def copy_engine(repo: Path, target_root: Path, in_place: bool, force: bool) -> Path:
    dest = target_root / ENGINE
    if in_place:
        log(f"  reusing  {dest}")
        return dest
    src = engine_skill_dir(repo)
    if dest.exists() and not already_ours(dest) and not force:
        die(f"{dest} exists and was not installed by an installer.\n"
            "  Move it away, or re-run with --force to replace it.")
    existed = dest.exists()
    shutil.copytree(src, dest, dirs_exist_ok=True, ignore=IGNORE)
    stamp(dest, str(repo), ENGINE)
    log(f"  {'updated' if existed else 'installed'}  {dest}")
    return dest


MARKER = ".install.json"


def already_ours(dest: Path) -> bool:
    return (dest / MARKER).is_file()


def stamp(dest: Path, origin: str, skill: str) -> None:
    import datetime
    meta = {"skill": skill, "origin": origin,
            "installed_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds")}
    (dest / MARKER).write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")


def py_exe(venv: Path) -> Path:
    return venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def has_module(python: Path, module: str) -> bool:
    try:
        return subprocess.run([str(python), "-c", f"import {module}"],
                              capture_output=True, timeout=30).returncode == 0
    except Exception:
        return False


def playwright_version(python: Path) -> str:
    try:
        out = subprocess.run(
            [str(python), "-c",
             "import importlib.metadata as m; print(m.version('playwright'))"],
            capture_output=True, text=True, timeout=30)
        return out.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def setup_venv(skill_dir: Path, dry_run: bool) -> None:
    venv = skill_dir / ".venv"
    python = py_exe(venv)
    if venv.exists() and python.exists() and has_module(python, "playwright"):
        log(f"  python        {python} (playwright {playwright_version(python)})")
        return
    if dry_run:
        log(f"  python        would create {venv} and install playwright")
        return

    uv = shutil.which("uv")
    try:
        if uv:
            subprocess.run([uv, "venv", "--python", "3.12", str(venv)],
                           check=True, capture_output=True, timeout=300)
            subprocess.run([uv, "pip", "install", "--python", str(python), "playwright"],
                           check=True, capture_output=True, timeout=600)
        else:
            subprocess.run([sys.executable, "-m", "venv", str(venv)],
                           check=True, capture_output=True, timeout=300)
            subprocess.run([str(python), "-m", "pip", "install", "--quiet", "playwright"],
                           check=True, capture_output=True, timeout=600)
    except Exception as exc:
        log(f"  python        FAILED to provision Playwright: {exc}")
        log(f"                install it yourself: {sys.executable} -m pip install playwright")
        return

    if has_module(python, "playwright"):
        log(f"  python        {python} (playwright {playwright_version(python)})")
    else:
        log("  python        Playwright installed but not importable; check the venv")


def local_engine(args) -> tuple[Path, str] | None:
    """A locally available engine checkout, if any."""
    if args.engine_src:
        repo = Path(args.engine_src).expanduser().resolve()
        if not looks_like_engine(repo):
            die(f"--engine-src {repo} is not an engine checkout "
                f"(expected {repo}/skills/{ENGINE}/scripts/batch_fetch.py)")
        return repo, "flag"
    sibling = ROOT.parent / ENGINE
    if looks_like_engine(sibling):
        return sibling, "sibling checkout"
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--target", default="auto", choices=("auto",) + tuple(TARGETS))
    parser.add_argument("--dir", default=None, help="explicit skills directory")
    parser.add_argument("--engine-src", default=None,
                        help="path to a local checkout of the engine repo")
    parser.add_argument("--engine-url", default=DEFAULT_ENGINE_URL,
                        help="engine repo URL used when no local copy is found")
    parser.add_argument("--engine-ref", default=DEFAULT_ENGINE_REF,
                        help="branch or tag of the engine repo to clone")
    parser.add_argument("--no-engine", action="store_true",
                        help="install research-report only (the engine must exist already)")
    parser.add_argument("--force", action="store_true",
                        help="replace copies not created by this installer")
    parser.add_argument("--no-venv", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    if not REPORT_SRC.is_dir():
        die(f"missing skill source: {REPORT_SRC}")

    target_root, target_name = resolve_target(args.target, args.dir)

    # Resolve the engine first: never leave a half install behind.
    engine_repo: Path | None = None
    engine_how = "skipped"
    in_place = False
    if not args.no_engine:
        found = local_engine(args)
        if found:
            engine_repo, engine_how = found
        elif (target_root / ENGINE / "scripts" / "batch_fetch.py").is_file():
            engine_repo, engine_how, in_place = target_root, "already installed", True
        elif args.dry_run:
            engine_how = f"would clone {args.engine_url} @ {args.engine_ref}"
        else:
            engine_repo = clone_engine(args.engine_url, args.engine_ref)
            engine_how = "cloned"

    log(f"source   {ROOT}")
    log(f"target   {target_root}  ({target_name})")
    if not args.no_engine:
        log(f"engine   {engine_repo or args.engine_url}  ({engine_how})")

    if args.dry_run:
        log(f"  would install  {REPORT}")
        log(f"  would install  {ENGINE}" if not args.no_engine else "  engine skipped")
    if not args.dry_run:
        # Preflight every destination before writing anything: a guard failure
        # must not leave a half install behind.
        dests = [target_root / REPORT]
        if not args.no_engine and engine_repo and engine_repo != target_root:
            dests.append(target_root / ENGINE)
        for dest in dests:
            if dest.exists() and not already_ours(dest) and not args.force:
                die(f"{dest} exists and was not installed by this installer.\n"
                    "  Move it away, or re-run with --force to replace it.")
        target_root.mkdir(parents=True, exist_ok=True)

        report_dest = target_root / REPORT
        existed = report_dest.exists()
        shutil.copytree(REPORT_SRC, report_dest, dirs_exist_ok=True, ignore=IGNORE)
        stamp(report_dest, str(ROOT), REPORT)
        log(f"  {'updated' if existed else 'installed'}  {report_dest}")

    engine_dir: Path | None = None
    if not args.no_engine:
        if args.dry_run:
            engine_dir = target_root / ENGINE
        else:
            engine_dir = copy_engine(engine_repo, target_root, in_place, args.force)
        if not args.no_venv:
            log("python")
            setup_venv(engine_dir, args.dry_run)

    log("")
    log("next")
    if engine_dir:
        log(f"  health check   python {engine_dir}/scripts/check_egress.py")
        log(f"  one page       python {engine_dir}/scripts/fetch_page.py <url> out --headed")
    cleanup_temp()
    log("  ask your agent for a researched answer; the research-report skill triggers on it")
    log("  restart the agent so it picks up the new skills")
    if args.no_engine:
        log("  note: --no-engine was used; verify the engine exists in the same skills root")
    return 0


if __name__ == "__main__":
    sys.exit(main())
