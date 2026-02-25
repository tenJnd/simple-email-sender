Simple Email Sender
===================

A small, idempotent CLI tool to send generic emails from a Google Workspace mailbox, manage recipients, and keep persistent state.

What’s new
- Typer-based CLI for clearer, modern command definitions
- Gmail (Google Workspace) sending is required for non-dry-run runs
- Persistent recipients and send log in a SQLite file by default (`state.sqlite`) using SQLAlchemy ORM
- Optional PostgreSQL support by passing a SQLAlchemy URL to `--db`
- Idempotent per campaign (UNIQUE `(campaign_id, recipient_email)`)
- Dry-run mode prints to console for safe testing
- Simple static templates selected by recipient flags

Install
```
pip install -r requirements.txt
```

Google Workspace (Gmail API) setup - Service Account
1) In Google Cloud Console, enable the Gmail API for your project.
2) Create a Service Account and enable Domain-Wide Delegation.
3) Download the service account credentials JSON as `service-account.json` (or set `GMAIL_SERVICE_ACCOUNT_FILE=/path/to/file.json`).
4) In Google Workspace Admin Console, authorize the service account's Client ID with scope: `https://www.googleapis.com/auth/gmail.send`
5) Set the sender email (default: info@partonomy.eu) via `GMAIL_SENDER_EMAIL` environment variable or `--from` flag.
6) The tool uses scope `https://www.googleapis.com/auth/gmail.send` and sends emails from the configured sender address.

CSV format
Only one CSV format is supported (semicolon-delimited): Required: `email`. Optional: `name`, `place`, `email_type`, `size`.
```
name;place;email;email_type;size
Company A;Brno;info@companya.com;personal;small
Company B;Prague;contact@companyb.com;generic;medium
```
Notes:
- `email_type` accepts `personal` or `generic` and is mapped internally to templates:
  - `personal` → `to_person` template
  - `generic` → `info` template
  You may also pass internal flags directly (`to_person`, `info`).
- `name`, `place`, and `size` are concatenated into the `notes` field.

Commands
- Import recipients:
```
# uses default DB (state.sqlite)
python mailer.py import recipients.csv

# specify custom DB path
python mailer.py import recipients.csv --db ./my_state.sqlite

# or use PostgreSQL via SQLAlchemy URL (optional)
python mailer.py import recipients.csv --db postgresql+psycopg2://user:pass@host:5432/db
```

- Create/list campaigns:
```
python mailer.py campaign create feb_2026
python mailer.py campaign list

# with custom DB
python mailer.py campaign create feb_2026 --db ./my_state.sqlite
python mailer.py campaign list --db ./my_state.sqlite
```

- Send emails (uses Gmail API with Service Account; requires service account credentials):
```
# basic send with a limit
python mailer.py send --campaign feb_2026 --limit 50

# override sender and DB path
python mailer.py send --campaign feb_2026 --limit 50 --from info@partonomy.eu --db ./my_state.sqlite
```

- Dry-run (no send, just prints to console):
```
python mailer.py send --campaign feb_2026 --dry-run
python mailer.py send --campaign feb_2026 --dry-run --db ./my_state.sqlite
```

- Mark opt-out:
```
python mailer.py optout someone@company.com
python mailer.py optout someone@company.com --db ./my_state.sqlite
```

- Stats:
```
python mailer.py stats --campaign feb_2026
python mailer.py stats --campaign feb_2026 --db ./my_state.sqlite
```

Data model (current implementation)
- `recipients(email PK, flags JSON/TEXT, status, notes, created_at, updated_at)`
- `campaigns(id INTEGER PK AUTOINCREMENT, name UNIQUE, created_at)`
- `send_log(id, campaign_id INTEGER FK to campaigns.id, recipient_email FK to recipients.email, template_key, sent_at, UNIQUE(campaign_id, recipient_email))`

Notes
- Idempotency is enforced by the database. Re-running `send` won’t resend already-logged deliveries for the same campaign.
- Default DB path is `state.sqlite`. Override with `--db /path/to/file.sqlite` or use a SQLAlchemy URL (e.g., PostgreSQL).
- Non–dry-run sending requires a Google Service Account with Domain‑Wide Delegation and the `gmail.send` scope.

Common issues
- zsh: bad pattern: [--db]
  - Do not type square brackets when running commands. In shell docs, brackets often mean “optional”; they are not part of the command. Some shells (like zsh) treat `[` and `]` as glob patterns and error out. Use the examples above without brackets.
