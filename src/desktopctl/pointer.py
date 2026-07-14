"""Pointer (mouse / touchpad / trackpoint) configuration via xinput.

Mirrors keyboard.py: each ``[[device]]`` in pointer.toml matches a physical
pointer by USB vendor:product id or an xinput name substring, then applies a
set of libinput settings with ``xinput set-prop`` / ``set-float-prop`` (and an
optional enable/disable).

Friendly TOML keys are mapped to libinput properties by ``SETTINGS`` below.
Settings whose property does not exist on a matched device are skipped — the
same guard the original shell script did with ``grep -qF``, needed because a
single physical keyboard can expose several pointer slaves.
"""

from __future__ import annotations

import subprocess
import tomllib
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import cast

from . import xinput


# ── libinput setting registry ────────────────────────────────────────

@dataclass
class Setting:
    prop: str                                  # xinput property name
    encode: Callable[[object], list[str]]      # config value -> argv values
    decode: Callable[[list[str]], str]         # raw values -> friendly str
    float_prop: bool = False                   # use set-float-prop


def _bool_setting(prop: str) -> Setting:
    return Setting(
        prop,
        encode=lambda v: ["1" if v else "0"],
        decode=lambda vs: "true" if vs and vs[0] in ("1", "1.0") else "false",
    )


def _float_setting(prop: str) -> Setting:
    return Setting(
        prop,
        encode=lambda v: [str(float(cast(float, v)))],
        decode=lambda vs: f"{float(vs[0]):g}" if vs else "?",
        float_prop=True,
    )


# libinput exposes several toggles as a bitmask over an ordered set of modes,
# e.g. "Accel Profile Enabled" is [adaptive, flat] and "Click Method Enabled"
# is [buttonareas, clickfinger].  We surface a single friendly name instead.
_OFF = {"none", "off", "disabled", "false"}


def _enum_setting(prop: str, names: tuple[str, ...]) -> Setting:
    def encode(v: object) -> list[str]:
        name = str(v).lower()
        if name in _OFF:
            return ["0"] * len(names)
        if name not in names:
            raise ValueError(
                f"{prop}: expected one of {list(names)} or 'none', got {v!r}"
            )
        return ["1" if n == name else "0" for n in names]

    def decode(vs: list[str]) -> str:
        for name, raw in zip(names, vs):
            if raw in ("1", "1.0"):
                return name
        return "none"

    return Setting(prop, encode, decode)


SETTINGS: dict[str, Setting] = {
    "accel_speed": _float_setting("libinput Accel Speed"),
    "accel_profile": _enum_setting(
        "libinput Accel Profile Enabled", ("adaptive", "flat")
    ),
    "click_method": _enum_setting(
        "libinput Click Method Enabled", ("buttonareas", "clickfinger")
    ),
    "scroll_method": _enum_setting(
        "libinput Scroll Method Enabled", ("twofinger", "edge", "button")
    ),
    "natural_scrolling": _bool_setting("libinput Natural Scrolling Enabled"),
    "tapping": _bool_setting("libinput Tapping Enabled"),
    "middle_emulation": _bool_setting("libinput Middle Emulation Enabled"),
    "disable_while_typing": _bool_setting(
        "libinput Disable While Typing Enabled"
    ),
    "left_handed": _bool_setting("libinput Left Handed Enabled"),
}


def _fmt(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


# ── data model ───────────────────────────────────────────────────────

@dataclass
class DevicePointer:
    id: str = ""           # usb "vendor:product" hex (preferred)
    match: str = ""        # xinput name substring (fallback / non-USB devices)
    description: str = ""  # human-readable note about the device
    enabled: bool | None = None
    settings: dict[str, object] = field(default_factory=dict)

    def key(self) -> str:
        """Short identifier for messages."""
        return self.description or self.id or self.match or "?"

    def matches(self, dev: xinput.Device) -> bool:
        return xinput.device_matches(self.id, self.match, dev)


@dataclass
class PointerConfig:
    devices: list[DevicePointer] = field(default_factory=list)


# ── config loading ───────────────────────────────────────────────────

_RESERVED = {"id", "match", "description", "enabled"}


def load(path: Path) -> PointerConfig:
    with open(path, "rb") as f:
        data = tomllib.load(f)

    devices = []
    for entry in data.get("device", []):
        settings = {k: v for k, v in entry.items() if k not in _RESERVED}
        unknown = sorted(set(settings) - set(SETTINGS))
        if unknown:
            who = entry.get("description") or entry.get("match") or entry.get("id")
            raise ValueError(
                f"Unknown pointer setting(s) {unknown} for device {who!r}. "
                f"Known settings: {sorted(SETTINGS)}"
            )
        devices.append(DevicePointer(
            id=entry.get("id", ""),
            match=entry.get("match", ""),
            description=entry.get("description", ""),
            enabled=entry.get("enabled"),
            settings=settings,
        ))
    return PointerConfig(devices=devices)


# ── xinput actions ───────────────────────────────────────────────────

def _set_enabled(xinput_id: int, enabled: bool) -> None:
    subprocess.run(
        ["xinput", "enable" if enabled else "disable", str(xinput_id)],
        check=True,
    )


def _set_prop(xinput_id: int, setting: Setting, value: object) -> None:
    cmd = [
        "xinput",
        "set-float-prop" if setting.float_prop else "set-prop",
        str(xinput_id), setting.prop, *setting.encode(value),
    ]
    subprocess.run(cmd, check=True)


# ── apply / status ───────────────────────────────────────────────────

def apply(config: PointerConfig) -> list[str]:
    """Apply per-device pointer settings via xinput."""
    if not config.devices:
        raise ValueError("No devices defined in configuration")

    pointers = xinput.list_devices("pointer")
    results = []

    for dev_cfg in config.devices:
        matched = [p for p in pointers if dev_cfg.matches(p)]
        if not matched:
            results.append(f"  {dev_cfg.key()}: no matching device found")
            continue

        for p in matched:
            props = xinput.read_props(p.xinput_id)
            applied, skipped = [], []

            if dev_cfg.enabled is not None:
                _set_enabled(p.xinput_id, dev_cfg.enabled)
                applied.append("enabled" if dev_cfg.enabled else "disabled")

            for key, value in dev_cfg.settings.items():
                setting = SETTINGS[key]
                if setting.prop not in props:
                    skipped.append(key)
                    continue
                _set_prop(p.xinput_id, setting, value)
                applied.append(f"{key}={_fmt(value)}")

            desc = f"{dev_cfg.description} — " if dev_cfg.description else ""
            summary = ", ".join(applied) if applied else "nothing applicable"
            note = f"  (unsupported: {', '.join(skipped)})" if skipped else ""
            results.append(
                f"  {desc}{p.name} (id={p.xinput_id}): {summary}{note}"
            )

    return results


def status(config: PointerConfig) -> list[str]:
    """Return per-device pointer status by reading current xinput props."""
    pointers = xinput.list_devices("pointer")
    lines = []

    for dev_cfg in config.devices:
        matched = [p for p in pointers if dev_cfg.matches(p)]
        if not matched:
            lines.append(f"  {dev_cfg.key()}: not connected")
            continue

        for p in matched:
            props = xinput.read_props(p.xinput_id)
            desc = f"{dev_cfg.description} — " if dev_cfg.description else ""

            fields = []
            if dev_cfg.enabled is not None:
                cur = props.get("Device Enabled", ["?"])[0]
                want = "1" if dev_cfg.enabled else "0"
                mark = "" if cur == want else f" (want {_fmt(dev_cfg.enabled)})"
                shown = "true" if cur == "1" else "false" if cur == "0" else cur
                fields.append(f"enabled={shown}{mark}")

            for key, value in dev_cfg.settings.items():
                setting = SETTINGS[key]
                if setting.prop not in props:
                    fields.append(f"{key}=unsupported")
                    continue
                cur = setting.decode(props[setting.prop])
                want = setting.decode(setting.encode(value))
                mark = "" if cur == want else f" (want {want})"
                fields.append(f"{key}={cur}{mark}")

            body = ", ".join(fields) if fields else "no settings"
            lines.append(f"  {desc}{p.name} (id={p.xinput_id}): {body}")

    return lines
