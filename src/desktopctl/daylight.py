"""Light/dark theme switching across apps via shell command templates.

Each ``[[app]]`` in daylight.toml declares a shell ``command`` with a
``{theme}`` placeholder plus ``light``/``dark`` theme values.  ``desktopctl
light`` / ``desktopctl dark`` substitute the matching theme into the command
and run it through the shell (so ``~``, ``&&`` and pipes work).

The chosen mode is recorded at ``$XDG_STATE_HOME/desktopctl/daylight`` (default
``~/.local/state/...``) so other tools can read the current setting.
"""

from __future__ import annotations

import os
import subprocess
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

MODES = ("light", "dark")


# ── data model ───────────────────────────────────────────────────────

@dataclass
class App:
    name: str
    command: str          # shell command; "{theme}" is substituted
    light: str = ""
    dark: str = ""

    def theme(self, mode: str) -> str:
        return self.light if mode == "light" else self.dark


@dataclass
class DaylightConfig:
    apps: list[App] = field(default_factory=list)


# ── config loading ───────────────────────────────────────────────────

def load(path: Path) -> DaylightConfig:
    with open(path, "rb") as f:
        data = tomllib.load(f)

    apps = [
        App(
            name=entry["name"],
            command=entry["command"],
            light=entry.get("light", ""),
            dark=entry.get("dark", ""),
        )
        for entry in data.get("app", [])
    ]
    return DaylightConfig(apps=apps)


# ── current-mode state ───────────────────────────────────────────────

def _state_path() -> Path:
    base = Path(os.environ.get("XDG_STATE_HOME", "~/.local/state")).expanduser()
    return base / "desktopctl" / "daylight"


def current_mode() -> str | None:
    """Return the last applied mode, or None if never set."""
    try:
        return _state_path().read_text().strip() or None
    except OSError:
        return None


def _write_state(mode: str) -> None:
    path = _state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(mode + "\n")


# ── apply ────────────────────────────────────────────────────────────

def apply(config: DaylightConfig, mode: str) -> list[str]:
    """Switch every configured app to ``mode`` ("light" or "dark")."""
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}, got {mode!r}")
    if not config.apps:
        raise ValueError("No apps defined in configuration")

    results = []
    for app in config.apps:
        theme = app.theme(mode)
        if "{theme}" in app.command and not theme:
            results.append(f"  {app.name}: no '{mode}' theme configured, skipped")
            continue
        # str.replace, not str.format: shell commands can contain literal "{}".
        cmd = app.command.replace("{theme}", theme)
        proc = subprocess.run(cmd, shell=True)
        if proc.returncode != 0:
            results.append(f"  {app.name}: error (exit {proc.returncode})")
            continue
        shown = f" → {theme}" if theme else ""
        results.append(f"  {app.name}{shown}")

    _write_state(mode)
    return results
