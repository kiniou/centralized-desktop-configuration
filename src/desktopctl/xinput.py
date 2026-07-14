"""Shared low-level xinput helpers used by the keyboard and pointer modules.

Both features enumerate physical input slaves and match them by USB
vendor:product id, so that logic lives here once.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass


@dataclass
class Device:
    """A physical input slave reported by xinput."""
    name: str
    xinput_id: int
    usb: str = ""          # normalized "vendor:product" hex, "" if unknown


def norm_usb(s: str) -> str:
    """Normalize a 'vendor:product' hex id to zero-padded lowercase.

    Returns "" if the string is not a valid vendor:product pair.
    """
    try:
        vendor, product = s.strip().split(":")
        return f"{int(vendor, 16):04x}:{int(product, 16):04x}"
    except (ValueError, AttributeError):
        return ""


def device_usb(xinput_id: int) -> str:
    """Return the 'vendor:product' hex USB id for an xinput device.

    xinput exposes it as a decimal "Device Product ID (nnn): v, p"
    property.  Returns "" when the device reports no id (0, 0).
    """
    result = subprocess.run(
        ["xinput", "list-props", str(xinput_id)],
        capture_output=True, text=True,
    )
    m = re.search(r"Device Product ID \(\d+\):\s*(\d+),\s*(\d+)", result.stdout)
    if not m:
        return ""
    vendor, product = int(m.group(1)), int(m.group(2))
    if vendor == 0 and product == 0:
        return ""
    return f"{vendor:04x}:{product:04x}"


def device_matches(usb_id: str, name_match: str, dev: Device) -> bool:
    """Whether ``dev`` matches a config entry's ``id`` / ``match``.

    When both a USB id and a name substring are configured, the device must
    match *both* (precise — useful when several slaves share one USB id, e.g.
    a Wacom pen+touch sensor). When only one is given, match on that alone.
    """
    id_ok = bool(usb_id) and norm_usb(usb_id) == dev.usb
    name_ok = bool(name_match) and name_match in dev.name
    if usb_id and name_match:
        return id_ok and name_ok
    return id_ok or name_ok


def list_devices(kind: str) -> list[Device]:
    """Return a Device for each physical slave of the given kind.

    ``kind`` is "keyboard" or "pointer" — it matches the xinput
    "[slave <kind>" tag.  Virtual and XTEST devices are skipped.
    """
    result = subprocess.run(
        ["xinput", "list"], capture_output=True, text=True, check=True
    )
    devices = []
    for line in result.stdout.splitlines():
        m = re.search(rf"[↳]\s+(.+?)\s+id=(\d+)\s+\[slave\s+{kind}", line)
        if m:
            name = m.group(1).strip()
            dev_id = int(m.group(2))
            if "Virtual" not in name and "XTEST" not in name:
                devices.append(Device(name, dev_id, device_usb(dev_id)))
    return devices


def read_props(xinput_id: int) -> dict[str, list[str]]:
    """Return {property name: [values]} from ``xinput list-props``.

    Values are the comma-separated fields after the tab, stripped.
    """
    result = subprocess.run(
        ["xinput", "list-props", str(xinput_id)],
        capture_output=True, text=True, check=True,
    )
    props: dict[str, list[str]] = {}
    for line in result.stdout.splitlines():
        # "\tlibinput Accel Speed (340):\t1.000000"
        m = re.match(r"\s*(.+?)\s*\(\d+\):\s*(.*)", line)
        if not m:
            continue
        raw = m.group(2).strip()
        props[m.group(1)] = [v.strip() for v in raw.split(",")] if raw else []
    return props
