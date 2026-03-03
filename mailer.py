#!/usr/bin/env python3
"""
Simple Email Sender CLI (Typer)

Commands (examples):
  # import recipients (default DB: state.sqlite)
  python mailer.py import recipients.csv

  # campaigns
  python mailer.py campaign create <name>
  python mailer.py campaign list

  # send (idempotent per campaign)
  python mailer.py send --campaign <name>
  python mailer.py send --campaign <name> --limit 100
  python mailer.py send --campaign <name> --dry-run

  # opt-out and stats
  python mailer.py optout <email>
  python mailer.py stats --campaign <name>

Options:
  --db PATH              Path to SQLite file or SQLAlchemy URL (default: state.sqlite)
  --from EMAIL           Sender email (default: info@partonomy.eu)

Notes:
  - Gmail (Google Workspace) sending via Service Account is REQUIRED for non-dry-run sends.
  - Place service-account.json in project root (or set GMAIL_SERVICE_ACCOUNT_FILE) and follow README.
  - Default sender: info@partonomy.eu (override with --from flag or GMAIL_SENDER_EMAIL env var).
  - Default storage: SQLite file 'state.sqlite' in project root.
  - Do NOT type square brackets in commands; they indicated "optional" in some docs and can break in zsh.
"""
from __future__ import annotations

import csv
from pathlib import Path
from typing import List, Optional

import typer

from src.db import Store, Recipient
from src.sender import ConsoleSender, GmailServiceAccountSender
from src.templates import TemplateRegistry

app = typer.Typer(help="Simple, idempotent email sender (Google Workspace via Gmail API)")

DEF_DB_PATH = Path("state.sqlite")


def _get_store(db: Path) -> Store:
    return Store(db)


@app.command("import")
def import_cmd(
        csv_path: Path = typer.Argument(
            ..., exists=True, readable=True,
            help="CSV file (semicolon-delimited): name;place;email;email_type;size"
        ),
        db: Path = typer.Option(DEF_DB_PATH, help="SQLite file path or SQLAlchemy URL"),
) -> None:
    store = _get_store(db)
    count = 0
    with csv_path.open(newline="") as f:
        # Only semicolon-delimited CSV is supported (Format 2)
        reader = csv.DictReader(f, delimiter=';')
        fieldnames = set(reader.fieldnames or [])

        required = {"email"}
        missing = required - fieldnames
        if missing:
            typer.secho(
                f"CSV missing required columns: {', '.join(sorted(missing))}", err=True, fg=typer.colors.RED
            )
            raise typer.Exit(code=1)

        batch: List[Recipient] = []
        for row in reader:
            email = (row.get("email") or "").strip().lower()
            if not email:
                continue

            # Map email_type from CSV to flags used by templates
            # CSV values: "personal" | "generic"
            raw_email_type = (row.get("email_type") or "").strip().lower()
            type_map = {
                "personal": "personal",
                "generic": "generic",
            }
            mapped_flag = type_map.get(raw_email_type, "")
            flags = [mapped_flag] if mapped_flag else []

            name = (row.get("name") or "").strip()
            place = (row.get("place") or "").strip()
            size = (row.get("size") or "").strip()
            notes_parts = []
            if name:
                notes_parts.append(f"Company: {name}")
            if place:
                notes_parts.append(f"Location: {place}")
            if size:
                notes_parts.append(f"Size: {size}")
            notes = ", ".join(notes_parts)
            status = "active"

            batch.append(Recipient(email=email, flags=flags, status=status, notes=notes))
        count = store.upsert_recipients(batch)
    typer.echo(f"Imported/updated {count} recipients from {csv_path}")


campaign_app = typer.Typer(help="Manage campaigns")
app.add_typer(campaign_app, name="campaign")


@campaign_app.command("create")
def campaign_create(
        name: str = typer.Argument(..., help="Campaign name"),
        db: Path = typer.Option(DEF_DB_PATH, help="SQLite file path or SQLAlchemy URL"),
) -> None:
    store = _get_store(db)
    cid = store.create_campaign(name)
    typer.echo(f"Campaign created: id={cid} name={name}")


@campaign_app.command("list")
def campaign_list(
        db: Path = typer.Option(DEF_DB_PATH, help="SQLite file path or SQLAlchemy URL"),
) -> None:
    store = _get_store(db)
    rows = store.list_campaigns()
    if not rows:
        typer.echo("No campaigns.")
        return
    for r in rows:
        typer.echo(f"{r['id']}\t{r['name']}\t{r['created_at']}")


def _resolve_campaign_id(store: Store, name: str) -> int:
    return store.get_or_create_campaign(name)


@app.command("send")
def send_cmd(
        campaign: str = typer.Option(..., "--campaign", help="Campaign name"),
        limit: Optional[int] = typer.Option(None, "--limit", help="Max recipients to process"),
        dry_run: bool = typer.Option(False, "--dry-run", help="Print emails to console without sending"),
        db: Path = typer.Option(DEF_DB_PATH, help="SQLite file path or SQLAlchemy URL"),
        sender_email: str = typer.Option("info@partonomy.eu", "--from", help="Sender email address"),
) -> None:
    store = _get_store(db)
    cid = _resolve_campaign_id(store, campaign)
    pending = store.get_pending_recipients(cid, limit=limit)
    if not pending:
        typer.echo("Nothing to send (pending=0).")
        return
    typer.echo(f"Pending to send: {len(pending)} for campaign '{campaign}' (id={cid})")

    templates = TemplateRegistry()

    sender = None
    if not dry_run:
        try:
            sender = GmailServiceAccountSender(sender_email=sender_email)
        except Exception as e:
            typer.secho(f"Failed to initialize Gmail sender: {e}", err=True, fg=typer.colors.RED)
            raise typer.Exit(code=2)

    sent = 0
    for r in pending:
        if r.status == "opt_out":
            continue
        tpl = templates.select(r.flags)
        if dry_run:
            ConsoleSender().send(r.email, tpl.subject, tpl.body, from_email=sender_email)
        else:
            assert sender is not None
            sender.send(r.email, tpl.subject, tpl.body, from_email=sender_email)
            store.log_send(cid, r.email, tpl.key)
        sent += 1
    typer.echo(f"Processed {sent} recipients. Mode: {'dry-run' if dry_run else 'gmail-service-account'}")


@app.command("optout")
def optout_cmd(
        email: str = typer.Argument(..., help="Email to mark as opt-out"),
        db: Path = typer.Option(DEF_DB_PATH, help="SQLite file path or SQLAlchemy URL"),
) -> None:
    store = _get_store(db)
    email_n = email.strip().lower()
    if not email_n:
        typer.secho("Provide a valid email.", err=True, fg=typer.colors.RED)
        raise typer.Exit(code=1)
    ok = store.set_opt_out(email_n)
    if ok:
        typer.echo(f"Opted out: {email_n}")
    else:
        typer.echo(f"Recipient not found, created as opt_out: {email_n}")


@app.command("stats")
def stats_cmd(
        campaign: str = typer.Option(..., "--campaign", help="Campaign name"),
        db: Path = typer.Option(DEF_DB_PATH, help="DuckDB file path"),
) -> None:
    store = _get_store(db)
    cid = _resolve_campaign_id(store, campaign)
    totals = store.stats_campaign(cid)
    typer.echo(f"Campaign '{campaign}' (id={cid})")
    for k, v in totals.items():
        typer.echo(f"{k}: {v}")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
