import json
import os

import click
from flask import Flask, current_app

from app.extensions import db
from app.models import User


@click.command("create-admin")
@click.argument("username")
@click.argument("password")
def create_admin_command(username: str, password: str) -> None:
    """Create a new admin user or promote an existing user to admin."""
    user = User.query.filter_by(username=username).first()
    if user is None:
        user = User(username=username, role="admin")
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        click.echo(f"Admin user '{username}' created successfully.")
    else:
        user.role = "admin"
        user.set_password(password)
        db.session.commit()
        click.echo(f"Existing user '{username}' promoted to admin.")


create_admin = create_admin_command


@click.command("seed-content")
@click.option(
    "--path",
    default=None,
    help="Path to content.json (default: <project>/seed/content.json).",
)
def seed_content_command(path: str | None) -> None:
    """Load/refresh kana, characters, and chats from the seed JSON (idempotent)."""
    from seed.load_seed import load_seed

    if path is None:
        path = os.path.join(current_app.root_path, "..", "seed", "content.json")
    path = os.path.abspath(path)
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    counts = load_seed(data)
    click.echo(
        "Seed loaded from {path}: {kana} kana, {characters} characters, "
        "{rows} rows, {chats} chats, {steps} steps.".format(path=path, **counts)
    )


def register_cli_commands(app: Flask) -> None:
    """Register custom CLI commands with the Flask application."""
    app.cli.add_command(create_admin_command)
    app.cli.add_command(seed_content_command)
