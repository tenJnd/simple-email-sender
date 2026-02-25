import unittest
from dataclasses import dataclass


# Use a simple mocked template registry for readability.
@dataclass
class _Tpl:
    key: str
    subject: str
    body: str


class MockTemplateRegistry:
    def __init__(self) -> None:
        # Keep the mock self-contained and easy to read.
        self._templates = {
            "default": _Tpl(key="default", subject="S: default", body="B: default"),
            "generic": _Tpl(key="generic", subject="S: generic", body="B: generic"),
            "personal": _Tpl(key="personal", subject="S: personal", body="B: personal"),
        }

    def select(self, flags):
        # Selection rules: personal > generic > default
        fset = {f.lower() for f in (flags or [])}
        if "personal" in fset:
            return self._templates["personal"]
        if "generic" in fset:
            return self._templates["generic"]
        return self._templates["default"]


class TestTemplateRegistry(unittest.TestCase):
    def test_template_selection_default(self):
        reg = MockTemplateRegistry()
        tpl = reg.select([])
        self.assertEqual(tpl.key, "default")
        self.assertIn("default", tpl.subject)

    def test_template_selection_generic_key(self):
        reg = MockTemplateRegistry()
        tpl = reg.select(["generic"])  # selecting generic template
        self.assertEqual(tpl.key, "generic")
        self.assertIn("generic", tpl.subject)

    def test_template_selection_personal_overrides_generic(self):
        reg = MockTemplateRegistry()
        tpl = reg.select(["generic", "personal"])  # personal should take precedence
        self.assertEqual(tpl.key, "personal")
        self.assertIn("personal", tpl.subject)