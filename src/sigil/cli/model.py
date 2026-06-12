"""Model profile commands."""

from __future__ import annotations

import os

import click

from ..zeta.models import (
    clear_active_model_profile,
    default_model_selection,
    load_model_profiles,
    resolve_active_model,
    resolve_model_profile,
    set_active_model_profile,
)
from ._base import cli


@cli.group("model")
def cmd_model() -> None:
    """Inspect and switch Zeta model profiles for this session."""


@cmd_model.command("list")
def cmd_model_list() -> int:
    """List configured model profiles."""
    catalog = load_model_profiles()
    for diagnostic in catalog.diagnostics:
        click.echo(f"model config: {diagnostic.message}", err=True)
    if not catalog.profiles:
        default = default_model_selection()
        click.echo(f"{default.profile}\t{default.model}\t{default.url}")
        click.echo(
            "no profiles configured; using the builtin local default. "
            "Add profiles in ~/.zeta/models.toml.",
            err=True,
        )
        return 1 if catalog.diagnostics else 0
    for profile in sorted(catalog.profiles.values(), key=lambda item: item.name):
        selection = resolve_model_profile(profile.name, catalog=catalog)
        if selection is None:
            continue
        line = f"{selection.profile}\t{selection.model}\t{selection.url}"
        if profile.name == catalog.default_profile:
            line += "\t(default)"
        click.echo(line)
    return 1 if catalog.diagnostics else 0


@cmd_model.command("use")
@click.argument("name")
def cmd_model_use(name: str) -> int:
    """Use a model profile for the current shell session."""
    catalog = load_model_profiles()
    for diagnostic in catalog.diagnostics:
        click.echo(f"model config: {diagnostic.message}", err=True)
    selection = resolve_model_profile(name, catalog=catalog)
    if selection is None:
        raise click.ClickException(f"unknown model profile: {name}")
    set_active_model_profile(selection.profile)
    click.echo(f"model: {selection.profile} -> {selection.model} @ {selection.url}")
    if not os.environ.get("SIGIL_SESSION_ID"):
        click.echo(
            'no shell session detected; the selection applies to session "default"',
            err=True,
        )
    return 0


@cmd_model.command("show")
def cmd_model_show() -> int:
    """Show the active model for the current shell session."""
    resolution = resolve_active_model()
    if resolution.stale_profile is not None:
        click.echo(
            f"model: {resolution.stale_profile} is no longer configured", err=True
        )
    active = resolution.selection
    click.echo(
        f"model: {active.profile} -> {active.model} @ {active.url}"
        f" ({resolution.source})"
    )
    return 0


@cmd_model.command("clear")
def cmd_model_clear() -> int:
    """Clear the active model profile for the current shell session."""
    removed = clear_active_model_profile()
    if removed:
        click.echo("model: cleared")
    else:
        click.echo("model: default")
    return 0
