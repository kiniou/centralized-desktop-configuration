"""CLI entry point for desktopctl."""

from __future__ import annotations

import os
import shutil
import subprocess
import tomllib
from pathlib import Path

import click

from . import keyboard as kb

DEFAULT_CONFIG_DIR = Path(
    os.environ.get("DESKTOPCTL_CONFIG", "~/.config/desktopctl")
).expanduser()


@click.group()
@click.option(
    "--config-dir",
    "-C",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
    envvar="DESKTOPCTL_CONFIG",
    help="Configuration directory (default: ~/.config/desktopctl)",
)
@click.pass_context
def cli(ctx, config_dir: Path | None):
    """Centralized desktop configuration tool."""
    ctx.ensure_object(dict)
    ctx.obj["config_dir"] = config_dir or DEFAULT_CONFIG_DIR


def _keyboard_config(ctx: click.Context) -> kb.KeyboardConfig:
    config_path = ctx.obj["config_dir"] / "keyboard.toml"
    if not config_path.exists():
        raise click.ClickException(f"Config not found: {config_path}")
    return kb.load(config_path)


@cli.group("keyboard")
def keyboard_group():
    """Keyboard layout management."""


@keyboard_group.command("apply")
@click.pass_context
def keyboard_apply(ctx):
    """Apply per-device keyboard layouts from keyboard.toml."""
    config = _keyboard_config(ctx)
    results = kb.apply(config)
    click.echo("Applied:")
    for line in results:
        click.echo(line)
    if config.compose:
        click.echo(f"Compose: {config.compose}")


@keyboard_group.command("status")
@click.pass_context
def keyboard_status(ctx):
    """Show per-device keyboard layout status."""
    config = _keyboard_config(ctx)
    lines = kb.status(config)
    if lines:
        for line in lines:
            click.echo(line)
    else:
        click.echo("No configured devices found")


@keyboard_group.command("list")
def keyboard_list():
    """List detected keyboard devices."""
    for k in kb.list_keyboards():
        usb = k.usb or "-"
        click.echo(f"  id={k.xinput_id:<3} usb={usb:<9}  {k.name}")


@cli.command()
@click.pass_context
def emoji(ctx):
    """Launch emoji picker (rofimoji)."""
    if not shutil.which("rofimoji"):
        raise click.ClickException(
            "rofimoji is not installed. Install with: sudo apt install rofimoji"
        )

    cmd = ["rofimoji"]

    # Read emoji settings from keyboard.toml
    config_path = ctx.obj["config_dir"] / "keyboard.toml"
    if config_path.exists():
        with open(config_path, "rb") as f:
            data = tomllib.load(f)
        emoji_cfg = data.get("emoji", {})

        # Map TOML keys to rofimoji flags
        flag_map = {
            "selector": "--selector",
            "action": "--action",
            "skin_tone": "--skin-tone",
            "typer": "--typer",
            "clipboarder": "--clipboarder",
            "prompt": "--prompt",
        }
        for key, flag in flag_map.items():
            if value := emoji_cfg.get(key):
                cmd.extend([flag, value])

        if (max_recent := emoji_cfg.get("max_recent")) is not None:
            cmd.extend(["--max-recent", str(max_recent)])

        if selector_args := emoji_cfg.get("selector_args"):
            cmd.extend(["--selector-args", selector_args])

    subprocess.run(cmd)
