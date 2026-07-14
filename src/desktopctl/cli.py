"""CLI entry point for desktopctl."""

from __future__ import annotations

import os
import shutil
import subprocess
import tomllib
from pathlib import Path

import click

from . import keyboard as kb
from . import pointer as ptr

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


def _pointer_config(ctx: click.Context) -> ptr.PointerConfig:
    config_path = ctx.obj["config_dir"] / "pointer.toml"
    if not config_path.exists():
        raise click.ClickException(f"Config not found: {config_path}")
    return ptr.load(config_path)


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


@cli.group("pointer")
def pointer_group():
    """Pointer (mouse / touchpad / trackpoint) management."""


@pointer_group.command("apply")
@click.pass_context
def pointer_apply(ctx):
    """Apply per-device pointer settings from pointer.toml."""
    config = _pointer_config(ctx)
    click.echo("Applied:")
    for line in ptr.apply(config):
        click.echo(line)


@pointer_group.command("status")
@click.pass_context
def pointer_status(ctx):
    """Show per-device pointer settings status."""
    config = _pointer_config(ctx)
    lines = ptr.status(config)
    if lines:
        for line in lines:
            click.echo(line)
    else:
        click.echo("No configured devices found")


@pointer_group.command("list")
def pointer_list():
    """List detected pointer devices."""
    for d in ptr.xinput.list_devices("pointer"):
        usb = d.usb or "-"
        click.echo(f"  id={d.xinput_id:<3} usb={usb:<9}  {d.name}")


@cli.command("apply")
@click.pass_context
def apply_all(ctx):
    """Apply every available configuration (keyboard, pointer)."""
    config_dir = ctx.obj["config_dir"]
    sections = [
        ("Keyboard", "keyboard.toml", lambda p: kb.apply(kb.load(p))),
        ("Pointer", "pointer.toml", lambda p: ptr.apply(ptr.load(p))),
    ]

    ran = False
    for title, filename, run in sections:
        path = config_dir / filename
        if not path.exists():
            continue
        ran = True
        click.echo(f"{title}:")
        try:
            for line in run(path):
                click.echo(line)
        except Exception as exc:  # keep applying the other sections
            click.echo(f"  error: {exc}")

    if not ran:
        raise click.ClickException(f"No configuration found in {config_dir}")


@cli.command()
@click.argument(
    "shell", type=click.Choice(["zsh", "bash", "fish"]), default="zsh"
)
def completion(shell: str):
    """Output a shell completion script (default: zsh).

    \b
    Load it for the current session:
        eval "$(desktopctl completion zsh)"

    Or install it persistently (zsh):
        desktopctl completion zsh > ~/.zfunc/_desktopctl
    (ensure ~/.zfunc is on $fpath and `autoload -U compinit && compinit` runs).
    """
    from click.shell_completion import get_completion_class

    comp_cls = get_completion_class(shell)
    if comp_cls is None:
        raise click.ClickException(f"Unsupported shell: {shell}")
    comp = comp_cls(cli, {}, "desktopctl", "_DESKTOPCTL_COMPLETE")
    click.echo(comp.source())


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
