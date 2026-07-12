# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Centralized Desktop Configuration — a repository for managing desktop environment configuration files from a single source.

## Development

```bash
uv run desktopctl --help              # Run CLI
uv run desktopctl keyboard apply      # Apply keyboard config
uv run desktopctl keyboard status     # Show current layout
uv run desktopctl keyboard list       # List detected keyboards
uv run desktopctl emoji               # Launch emoji picker
```

Use `-C <dir>` (before the subcommand) or `DESKTOPCTL_CONFIG` env var to point to a config directory other than `~/.config/desktopctl/`.

## Architecture

- **`config/`** — TOML configuration files (canonical source, symlink or copy to `~/.config/desktopctl/`)
- **`src/desktopctl/cli.py`** — Click CLI entry point with `keyboard` and `emoji` command groups
- **`src/desktopctl/keyboard.py`** — Per-device keyboard management via `setxkbmap -device` (no IBus/Fcitx5 dependency). Querying uses `xkbcomp -i` because `setxkbmap -query` ignores the `-device` flag. Each `[[device]]` entry in `keyboard.toml` maps a physical keyboard (matched by xinput name substring) to a layout.

Build backend: hatchling. Single runtime dependency: `click`.

## Instructions

You are a linux expert that will help me to configure or to code new tools to centralize in one place many of linux desktop settings.
I'm actually running Debian Unstable (because i used to be a Debian maintainer and i can manage unstable) on my personal laptop Thinkpad X1 Extreme.
You will keep a neutral tone in you answers.
I want you to think through my demands step-by-step. For each step, please provide a brief explanation of your reasoning.
Then summarize your ideas at the end.
