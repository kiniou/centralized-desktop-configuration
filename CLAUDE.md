# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Centralized Desktop Configuration — a repository for managing desktop environment configuration files from a single source.

## Development

```bash
uv run desktopctl --help              # Run CLI
uv run desktopctl keyboard list       # List detected keyboards (with USB ids)
uv run desktopctl keyboard apply      # Apply keyboard config
uv run desktopctl keyboard status     # Show current layout
uv run desktopctl emoji               # Launch emoji picker
uv run desktopctl completion zsh      # Emit a shell completion script
```

Use `-C <dir>` (before the subcommand) or `DESKTOPCTL_CONFIG` env var to point to a config directory other than `~/.config/desktopctl/`.

Runtime relies on X11 tools (`xinput`, `setxkbmap`, `xkbcomp`) and, for the emoji picker, `rofimoji`.

## Architecture

- **`examples/`** — sample TOML configuration users copy (or symlink) into `~/.config/desktopctl/`. Not read at runtime; the CLI defaults to `~/.config/desktopctl/`.
- **`src/desktopctl/cli.py`** — Click CLI entry point with `keyboard` and `emoji` command groups plus a top-level `completion` command.
- **`src/desktopctl/keyboard.py`** — Per-device keyboard management via `setxkbmap -device` (no IBus/Fcitx5 dependency). Querying uses `xkbcomp -i` because `setxkbmap -query` ignores the `-device` flag. Each `[[device]]` entry in `keyboard.toml` maps a physical keyboard to a layout, matched by USB `vendor:product` id (`id`) or by an `xinput` name substring (`match`).

Build backend: hatchling. Single runtime dependency: `click`. License: WTFPL.
