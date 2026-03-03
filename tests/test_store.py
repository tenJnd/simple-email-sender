import importlib.util
import tempfile
import unittest
from pathlib import Path

from src.db import Store, Recipient


@unittest.skipUnless(importlib.util.find_spec("sqlalchemy") is not None, "SQLAlchemy not installed")
class TestStoreBasicFlow(unittest.TestCase):
    def test_flow(self):
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "state.sqlite"
            store = Store(db_path)

            # upsert recipients (insert)
            r1 = Recipient(email="a@example.com", flags=["generic"], status="active", notes="n1")
            r2 = Recipient(email="b@example.com", flags=["personal"], status="active", notes="n2")
            count = store.upsert_recipients([r1, r2])
            self.assertEqual(count, 2)

            # upsert recipients (update)
            r1u = Recipient(email="a@example.com", flags=["generic", "x"], status="active", notes="n1u")
            count = store.upsert_recipients([r1u])
            self.assertEqual(count, 1)

            # campaign create and get
            cid = store.create_campaign("test_campaign")
            self.assertIsInstance(cid, int)
            cid2 = store.get_or_create_campaign("test_campaign")
            self.assertEqual(cid2, cid)

            # pending before log
            pending = store.get_pending_recipients(cid)
            emails = {r.email for r in pending}
            self.assertEqual(emails, {"a@example.com", "b@example.com"})

            # log send for one; idempotent repeat shouldn't error
            store.log_send(cid, "a@example.com", template_key="generic")
            store.log_send(cid, "a@example.com", template_key="generic")

            # pending after one sent
            pending2 = store.get_pending_recipients(cid)
            emails2 = {r.email for r in pending2}
            self.assertEqual(emails2, {"b@example.com"})

            # opt out existing should return True
            self.assertTrue(store.set_opt_out("b@example.com"))

            # opt out non-existing should return False but create record
            self.assertFalse(store.set_opt_out("c@example.com"))

            # stats
            stats = store.stats_campaign(cid)
            self.assertGreaterEqual(stats["total_active"], 1)  # at least a@example.com remains active
            self.assertEqual(stats["sent"], 1)
            self.assertGreaterEqual(stats["pending"], 0)

