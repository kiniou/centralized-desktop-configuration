# desktopctl — Centralized Desktop Configuration

Manage your Linux desktop settings from a single, version-controlled source.

`desktopctl` is a small CLI that keeps fiddly, per-machine desktop tweaks in
plain [TOML](https://toml.io) files you can commit, share and reapply. It
currently focuses on **per-device keyboard layouts** (so an external keyboard
and the built-in one can each get their own layout), **per-device pointer
settings** (touchpad / trackpoint / mouse tweaks) and a thin wrapper around an
**emoji picker**.

> Targets **X11** (uses `xinput`, `setxkbmap`, `xkbcomp`). Wayland is not
> supported yet.

---

## Features

- **Per-device keyboard layouts** — bind a layout/variant to a specific physical
  keyboard, matched by its USB `vendor:product` id (stable across renames) or by
  an `xinput` name substring.
- **Per-device pointer settings** — apply libinput tweaks (acceleration, click
  method, natural scrolling, tapping, enable/disable, …) to a specific touchpad,
  trackpoint or mouse, matched the same way.
- **Accurate status** — reads back the *actual* per-device XKB state with
  `xkbcomp -i` (which `setxkbmap -query` gets wrong for per-device layouts), and
  the live libinput property values for pointers.
- **Light/dark switching** — `desktopctl light` / `desktopctl dark` flip your
  apps between themes by running per-app shell commands from `daylight.toml`.
- **Apply everything** — `desktopctl apply` runs every configuration present.
- **Emoji picker** — launches [`rofimoji`](https://github.com/fdw/rofimoji) with
  options read from your config.
- **Shell completion** — generate completion scripts for `zsh`, `bash` or `fish`.

---

## Requirements

| Purpose            | Tools                                             |
| ------------------ | ------------------------------------------------- |
| Keyboard commands  | `xinput`, `setxkbmap`, `xkbcomp` (X11)            |
| Pointer commands   | `xinput` with the libinput X driver (X11)         |
| Emoji picker       | `rofimoji` (optional)                             |
| Install            | [`uv`](https://docs.astral.sh/uv/)               |

On Debian/Ubuntu:

```bash
sudo apt install x11-xserver-utils x11-xkb-utils xinput rofimoji
```

---

## Install

The recommended way is `uv tool`, which installs the `desktopctl` command into an
isolated environment and puts it on your `PATH`.

**From Git:**

```bash
uv tool install git+https://github.com/kiniou/centralized-desktop-configuration
```

**From a local checkout:**

```bash
git clone https://github.com/kiniou/centralized-desktop-configuration
cd centralized-desktop-configuration
uv tool install .
```

Then make sure the tool directory is on your `PATH` (once):

```bash
uv tool update-shell
```

Upgrade later with `uv tool upgrade desktopctl`, or remove with
`uv tool uninstall desktopctl`.

<details>
<summary>Run without installing (from a checkout)</summary>

```bash
uv run desktopctl --help
```

</details>

---

## Configure

Configuration lives in `~/.config/desktopctl/`. Copy the sample from
[`examples/`](examples/) and edit it:

```bash
mkdir -p ~/.config/desktopctl
cp examples/keyboard.toml examples/pointer.toml examples/daylight.toml ~/.config/desktopctl/
```

A minimal `keyboard.toml`:

```toml
[keyboard]
model = "pc105"
# Right Alt as AltGr, Shift+Right Alt as Compose
compose = "lv3:ralt_switch_multikey"
repeat_delay = 200   # xset r rate: ms before a key repeats
repeat_rate = 25     # repeats per second

# One [[device]] per physical keyboard, matched by "id" (USB vendor:product
# hex) and/or "match" (xinput name substring). Give both to require a match on
# id AND name; run `desktopctl keyboard list` to read a device's id and name.
[[device]]
description = "Internal ThinkPad keyboard"
id = "0001:0001"
match = "AT Translated Set 2 keyboard"
layout = "fr"
variant = "nodeadkeys"

[[device]]
description = "External US keyboard"
match = "ThinkPad Compact USB Keyboard"
layout = "us"
variant = "altgr-intl"

[emoji]
selector = "rofi"
action = "type"
skin_tone = "neutral"
```

A minimal `pointer.toml` (one `[[device]]` per pointer; same `id`/`match`
scheme as keyboards):

```toml
[[device]]
description = "Touchpad"
match = "Synaptics TM3418-002"
click_method = "clickfinger"    # prefer 1/2/3-finger clicks over button areas
natural_scrolling = true

[[device]]
description = "TrackPoint"
match = "TrackPoint"
accel_speed = 1.0               # libinput Accel Speed, in [-1.0, 1.0]
accel_profile = "adaptive"
```

See [`examples/pointer.toml`](examples/pointer.toml) for every supported
setting.

A minimal `daylight.toml` (one `[[app]]` per app; `{theme}` in `command` is
replaced with the `light`/`dark` value):

```toml
[[app]]
name = "desktop"
command = "gsettings set org.gnome.desktop.interface color-scheme {theme}"
light = "prefer-light"
dark  = "prefer-dark"

[[app]]
name = "alacritty"
command = "ln -nsf ~/.config/alacritty/{theme} ~/.config/alacritty/current-theme.toml && touch ~/.config/alacritty/alacritty.toml"
light = "solarized_light.toml"
dark  = "solarized_dark.toml"
```

Commands run through the shell, so `~`, `&&` and pipes work. The chosen mode is
recorded at `${XDG_STATE_HOME:-~/.local/state}/desktopctl/daylight`. Apps
already running inside a terminal (e.g. Neovim) can *watch* that file to follow
the switch — see [`examples/neovim-daylight.md`](examples/neovim-daylight.md).

> Prefer a different location? Point at it with `desktopctl -C <dir> …` or the
> `DESKTOPCTL_CONFIG` environment variable. You can also symlink your repo copy
> into `~/.config/desktopctl/` to keep everything version-controlled.

---

## Usage

```bash
desktopctl apply              # Apply every configuration that exists
desktopctl keyboard list      # List detected keyboards (with USB ids)
desktopctl keyboard apply     # Apply per-device layouts from keyboard.toml
desktopctl keyboard status    # Show the current layout of each device
desktopctl pointer list       # List detected pointers (with USB ids)
desktopctl pointer apply      # Apply per-device pointer settings from pointer.toml
desktopctl pointer status     # Show the current settings of each pointer
desktopctl light              # Switch configured apps to their light theme
desktopctl dark               # Switch configured apps to their dark theme
desktopctl emoji              # Launch the emoji picker
desktopctl --help             # Full command reference
```

Typical first run:

```bash
desktopctl keyboard list      # copy the id of each keyboard into keyboard.toml
desktopctl keyboard apply
```

### Shell completion

```bash
# current session
eval "$(desktopctl completion zsh)"

# persistent (zsh) — ensure ~/.zfunc is on $fpath
desktopctl completion zsh > ~/.zfunc/_desktopctl
```

Replace `zsh` with `bash` or `fish` as needed.

---

## Project layout

```
src/desktopctl/   # CLI (cli.py), keyboard.py, pointer.py, daylight.py, shared xinput.py
examples/         # sample configuration to copy into ~/.config/desktopctl/
```

---

## License

[WTFPL](LICENSE) — Do What The Fuck You Want To Public License.
