"""Keyboard layout management via setxkbmap and xkbcomp.

setxkbmap -device <id> correctly applies per-device layouts but its
-query flag ignores the device argument.  We use xkbcomp -i <id> to
read back the actual per-device XKB state instead.
"""

from __future__ import annotations

import os
import re
import subprocess
import tomllib
from dataclasses import dataclass, field
from pathlib import Path


# ── data model ───────────────────────────────────────────────────────

@dataclass
class DeviceLayout:
    match: str
    layout: str
    variant: str = ""

    def label(self) -> str:
        return f"{self.layout}({self.variant})" if self.variant else self.layout


@dataclass
class KeyboardConfig:
    model: str = "pc105"
    compose: str = ""
    devices: list[DeviceLayout] = field(default_factory=list)


@dataclass
class XkbState:
    layout: str
    variant: str
    group_name: str        # e.g. "French (no dead keys)"
    options: list[str]

    def label(self) -> str:
        return f"{self.layout}({self.variant})" if self.variant else self.layout


# ── config loading ───────────────────────────────────────────────────

def load(path: Path) -> KeyboardConfig:
    with open(path, "rb") as f:
        data = tomllib.load(f)

    kb = data.get("keyboard", {})
    devices = [
        DeviceLayout(
            match=entry["match"],
            layout=entry["layout"],
            variant=entry.get("variant", ""),
        )
        for entry in data.get("device", [])
    ]
    return KeyboardConfig(
        model=kb.get("model", "pc105"),
        compose=kb.get("compose", ""),
        devices=devices,
    )


# ── xinput helpers ───────────────────────────────────────────────────

def list_keyboards() -> list[tuple[str, int]]:
    """Return (name, xinput_id) for each physical keyboard slave."""
    result = subprocess.run(
        ["xinput", "list"], capture_output=True, text=True, check=True
    )
    devices = []
    for line in result.stdout.splitlines():
        m = re.search(
            r"[↳]\s+(.+?)\s+id=(\d+)\s+\[slave\s+keyboard", line
        )
        if m:
            name = m.group(1).strip()
            dev_id = int(m.group(2))
            if "Virtual" not in name and "XTEST" not in name:
                devices.append((name, dev_id))
    return devices


# ── xkbcomp query (the part setxkbmap -query gets wrong) ────────────

_DISPLAY_NUM: str | None = None

def _display_num() -> str:
    global _DISPLAY_NUM
    if _DISPLAY_NUM is None:
        display = os.environ.get("DISPLAY", ":0")
        _DISPLAY_NUM = display.rsplit(":", 1)[-1].split(".")[0]
    return _DISPLAY_NUM


# Non-layout components in xkb_symbols strings
_SKIP = {"pc", "inet"}
_OPTION_PREFIXES = {"level3", "lv3", "compose", "grp", "ctrl", "caps", "mod_led"}


def query_device(device_id: int) -> XkbState:
    """Query actual XKB state for a specific device via xkbcomp.

    Works with both master and slave device IDs.
    """
    result = subprocess.run(
        ["xkbcomp", "-w", "0", "-i", str(device_id),
         f":{_display_num()}", "-"],
        capture_output=True, text=True, check=True,
    )

    symbols = ""
    group_name = ""
    for line in result.stdout.splitlines():
        if not symbols:
            m = re.search(r'xkb_symbols\s+"(.+)"', line)
            if m:
                symbols = m.group(1)
        if not group_name:
            m = re.search(r'name\[group1\]\s*=\s*"(.+)"', line)
            if m:
                group_name = m.group(1)
        if symbols and group_name:
            break

    # Parse "pc+fr(nodeadkeys)+inet(evdev)+level3(ralt_switch_multikey)"
    layout = ""
    variant = ""
    options: list[str] = []

    for part in symbols.split("+"):
        name, _, var = part.partition("(")
        var = var.rstrip(")")

        if name in _SKIP:
            continue
        if name in _OPTION_PREFIXES:
            options.append(part)
            continue
        if not layout:
            layout = name
            variant = var

    return XkbState(
        layout=layout, variant=variant,
        group_name=group_name, options=options,
    )


# ── apply / status ──────────────────────────────────────────────────

def apply(config: KeyboardConfig) -> list[str]:
    """Apply per-device layouts via setxkbmap -device <slave_id>."""
    if not config.devices:
        raise ValueError("No devices defined in configuration")

    keyboards = list_keyboards()
    results = []

    for dev_cfg in config.devices:
        matched = [
            (name, did) for name, did in keyboards
            if dev_cfg.match in name
        ]
        if not matched:
            results.append(f"  {dev_cfg.match}: no matching device found")
            continue

        for name, did in matched:
            cmd = [
                "setxkbmap",
                "-device", str(did),
                "-model", config.model,
                "-layout", dev_cfg.layout,
                "-variant", dev_cfg.variant,
            ]
            if config.compose:
                cmd.extend(["-option", config.compose])
            subprocess.run(cmd, check=True)

            results.append(f"  {name} (id={did}): {dev_cfg.label()}")

    return results


def status(config: KeyboardConfig) -> list[str]:
    """Return per-device layout status by querying xkbcomp."""
    keyboards = list_keyboards()
    lines = []

    for dev_cfg in config.devices:
        matched = [
            (name, did) for name, did in keyboards
            if dev_cfg.match in name
        ]
        if not matched:
            lines.append(f"  {dev_cfg.match}: not connected")
            continue

        for name, did in matched:
            state = query_device(did)
            opts = f"  [{', '.join(state.options)}]" if state.options else ""
            lines.append(f"  {name} (id={did}): {state.group_name} [{state.label()}]{opts}")

    return lines
