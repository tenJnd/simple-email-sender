import tempfile
import unittest
from pathlib import Path

from typer.testing import CliRunner

import importlib.util
from mailer import app
from src.db import Store


@unittest.skipUnless(importlib.util.find_spec("sqlalchemy") is not None, "SQLAlchemy not installed")
class TestCLI(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()
        self.td = tempfile.TemporaryDirectory()
        self.addCleanup(self.td.cleanup)
        self.tmpdir = Path(self.td.name)
        self.db_path = self.tmpdir / "state.sqlite"

    def _write_csv(self, rows):
        csv_path = self.tmpdir / "recipients.csv"
        with csv_path.open("w", encoding="utf-8", newline="") as f:
            f.write("name;place;email;email_type;size\n")
            for r in rows:
                f.write(";".join(r) + "\n")
        return csv_path

    def test_import_and_send_dry_run_and_stats(self):
        # Prepare CSV with a single recipient and flags/notes
        csv_path = self._write_csv([
            ("Company A", "Brno", "a@example.com", "generic", "small"),
        ])

        # Import
        result = self.runner.invoke(app, [
            "import", str(csv_path), "--db", str(self.db_path),
        ])
        self.assertEqual(result.exit_code, 0, msg=result.output)
        self.assertIn("Imported/updated 1 recipients", result.output)

        # Verify notes mapping via DB
        store = Store(self.db_path)
        cid = store.get_or_create_campaign("camp1")
        pending = store.get_pending_recipients(cid)
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0].flags, ["generic"])
        self.assertEqual(pending[0].notes, "Company: Company A, Location: Brno, Size: small")

        # Send in dry-run with custom from
        result2 = self.runner.invoke(app, [
            "send", "--campaign", "camp1", "--dry-run", "--db", str(self.db_path), "--from", "test@example.com",
        ])
        self.assertEqual(result2.exit_code, 0, msg=result2.output)
        self.assertIn("EMAIL (console)", result2.output)
        self.assertIn("From: test@example.com", result2.output)
        self.assertIn("Processed 1 recipients. Mode: dry-run", result2.output)

        # Stats should reflect no sent entries (dry-run doesn't log)
        result3 = self.runner.invoke(app, [
            "stats", "--campaign", "camp1", "--db", str(self.db_path),
        ])
        self.assertEqual(result3.exit_code, 0, msg=result3.output)
        self.assertIn("sent: 0", result3.output)
        self.assertIn("pending: 1", result3.output)

    def test_optout_prevents_sending(self):
        csv_path = self._write_csv([
            ("Company A", "Brno", "a@example.com", "generic", "small"),
        ])

        # Import
        r1 = self.runner.invoke(app, ["import", str(csv_path), "--db", str(self.db_path)])
        self.assertEqual(r1.exit_code, 0, msg=r1.output)

        # Opt-out
        r2 = self.runner.invoke(app, ["optout", "a@example.com", "--db", str(self.db_path)])
        self.assertEqual(r2.exit_code, 0, msg=r2.output)
        self.assertIn("Opted out", r2.output)

        # Send dry-run should find nothing
        r3 = self.runner.invoke(app, [
            "send", "--campaign", "camp2", "--dry-run", "--db", str(self.db_path)
        ])
        self.assertEqual(r3.exit_code, 0, msg=r3.output)
        self.assertIn("Nothing to send (pending=0).", r3.output)
