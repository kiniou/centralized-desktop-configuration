# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Centralized Desktop Configuration — a repository for managing desktop environment configuration files from a single source.

## Development

```bash
uv run desktopctl --help              # Run CLI
uv run desktopctl apply               # Apply every configuration at once
uv run desktopctl keyboard list       # List detected keyboards (with USB ids)
uv run desktopctl keyboard apply      # Apply keyboard config
uv run desktopctl keyboard status     # Show current layout
uv run desktopctl pointer list        # List detected pointers (with USB ids)
uv run desktopctl pointer apply       # Apply pointer config
uv run desktopctl pointer status      # Show current pointer settings
uv run desktopctl emoji               # Launch emoji picker
uv run desktopctl completion zsh      # Emit a shell completion script
```

Use `-C <dir>` (before the subcommand) or `DESKTOPCTL_CONFIG` env var to point to a config directory other than `~/.config/desktopctl/`.

Runtime relies on X11 tools (`xinput`, `setxkbmap`, `xkbcomp`) and, for the emoji picker, `rofimoji`.

## Architecture

- **`examples/`** — sample TOML configuration users copy (or symlink) into `~/.config/desktopctl/`. Not read at runtime; the CLI defaults to `~/.config/desktopctl/`.
- **`src/desktopctl/cli.py`** — Click CLI entry point with `keyboard`, `pointer` and `emoji` command groups, a top-level `apply` (runs every config that exists) and a `completion` command.
- **`src/desktopctl/xinput.py`** — Shared low-level helpers: USB id normalization, per-device USB id lookup, physical-slave enumeration (`list_devices("keyboard"|"pointer")`), `read_props`, and `device_matches` (the id/`match` rule: both given → AND, one given → that one). Used by both feature modules.
- **`src/desktopctl/keyboard.py`** — Per-device keyboard management via `setxkbmap -device` (no IBus/Fcitx5 dependency). Querying uses `xkbcomp -i` because `setxkbmap -query` ignores the `-device` flag. Each `[[device]]` entry in `keyboard.toml` maps a physical keyboard to a layout, matched by USB `vendor:product` id (`id`) and/or an `xinput` name substring (`match`) via `xinput.device_matches` (supplying both requires matching id AND name). The `[keyboard]` table also carries global `repeat_delay`/`repeat_rate` applied with `xset r rate`.
- **`src/desktopctl/pointer.py`** — Per-device pointer settings via `xinput set-prop`/`set-float-prop`. Each `[[device]]` in `pointer.toml` matches a pointer (same `id`/`match` scheme) and carries an optional `enabled` flag plus friendly libinput keys (`accel_speed`, `accel_profile`, `click_method`, `natural_scrolling`, …) mapped through the `SETTINGS` registry. Settings whose libinput property is absent on a matched slave are skipped (reported "unsupported"), so a keyboard exposing several pointer slaves is handled gracefully.

Build backend: hatchling. Single runtime dependency: `click`. License: WTFPL.
