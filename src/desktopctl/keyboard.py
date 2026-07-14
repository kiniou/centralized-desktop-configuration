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

from . import xinput


# ── data model ───────────────────────────────────────────────────────

# A physical keyboard slave reported by xinput.
Keyboard = xinput.Device


@dataclass
class DeviceLayout:
    layout: str
    variant: str = ""
    id: str = ""           # usb "vendor:product" hex, e.g. "17ef:6047" (preferred)
    match: str = ""        # xinput name substring (fallback / non-USB devices)
    description: str = ""  # human-readable note about the device

    def label(self) -> str:
        return f"{self.layout}({self.variant})" if self.variant else self.layout

    def key(self) -> str:
        """Short identifier for messages."""
        return self.description or self.id or self.match or "?"

    def matches(self, kb: Keyboard) -> bool:
        return xinput.device_matches(self.id, self.match, kb)


@dataclass
class KeyboardConfig:
    model: str = "pc105"
    compose: str = ""
    repeat_delay: int | None = None   # ms before key repeat starts (xset r rate)
    repeat_rate: int | None = None    # repeats per second
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
            layout=entry["layout"],
            variant=entry.get("variant", ""),
            id=entry.get("id", ""),
            match=entry.get("match", ""),
            description=entry.get("description", ""),
        )
        for entry in data.get("device", [])
    ]
    return KeyboardConfig(
        model=kb.get("model", "pc105"),
        compose=kb.get("compose", ""),
        repeat_delay=kb.get("repeat_delay"),
        repeat_rate=kb.get("repeat_rate"),
        devices=devices,
    )


# ── xinput helpers ───────────────────────────────────────────────────

def list_keyboards() -> list[Keyboard]:
    """Return a Keyboard for each physical keyboard slave."""
    return xinput.list_devices("keyboard")


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
        matched = [k for k in keyboards if dev_cfg.matches(k)]
        if not matched:
            results.append(f"  {dev_cfg.key()}: no matching device found")
            continue

        for k in matched:
            cmd = [
                "setxkbmap",
                "-device", str(k.xinput_id),
                "-model", config.model,
                "-layout", dev_cfg.layout,
                "-variant", dev_cfg.variant,
            ]
            if config.compose:
                cmd.extend(["-option", config.compose])
            subprocess.run(cmd, check=True)

            desc = f"{dev_cfg.description} — " if dev_cfg.description else ""
            results.append(
                f"  {desc}{k.name} (id={k.xinput_id}): {dev_cfg.label()}"
            )

    if repeat := _apply_repeat_rate(config):
        results.append(repeat)

    return results


def _apply_repeat_rate(config: KeyboardConfig) -> str | None:
    """Apply the X server key-repeat via `xset r rate <delay> <rate>`.

    `xset r rate` needs the delay first, so a rate without a delay is
    ignored.  Returns a status line, or None when nothing was configured.
    """
    if config.repeat_delay is None:
        return None
    cmd = ["xset", "r", "rate", str(config.repeat_delay)]
    if config.repeat_rate is not None:
        cmd.append(str(config.repeat_rate))
    subprocess.run(cmd, check=True)
    rate = f", rate {config.repeat_rate}/s" if config.repeat_rate is not None else ""
    return f"  key repeat: delay {config.repeat_delay}ms{rate}"


def _repeat_status(config: KeyboardConfig) -> str | None:
    """Return the live key-repeat rate (from `xset q`), or None if unset."""
    if config.repeat_delay is None and config.repeat_rate is None:
        return None
    result = subprocess.run(["xset", "q"], capture_output=True, text=True)
    m = re.search(
        r"auto repeat delay:\s*(\d+)\s+repeat rate:\s*(\d+)", result.stdout
    )
    if not m:
        return None
    delay, rate = m.group(1), m.group(2)
    want = []
    if config.repeat_delay is not None and str(config.repeat_delay) != delay:
        want.append(f"delay {config.repeat_delay}")
    if config.repeat_rate is not None and str(config.repeat_rate) != rate:
        want.append(f"rate {config.repeat_rate}")
    mark = f"  (want {', '.join(want)})" if want else ""
    return f"  key repeat: delay {delay}ms, rate {rate}/s{mark}"


def status(config: KeyboardConfig) -> list[str]:
    """Return per-device layout status by querying xkbcomp."""
    keyboards = list_keyboards()
    lines = []

    for dev_cfg in config.devices:
        matched = [k for k in keyboards if dev_cfg.matches(k)]
        if not matched:
            lines.append(f"  {dev_cfg.key()}: not connected")
            continue

        for k in matched:
            state = query_device(k.xinput_id)
            opts = f"  [{', '.join(state.options)}]" if state.options else ""
            desc = f"{dev_cfg.description} — " if dev_cfg.description else ""
            lines.append(
                f"  {desc}{k.name} (id={k.xinput_id}): "
                f"{state.group_name} [{state.label()}]{opts}"
            )

    if repeat := _repeat_status(config):
        lines.append(repeat)

    return lines
