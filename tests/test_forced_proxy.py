import json
from pathlib import Path
import tempfile
import unittest

import update_rules


def make_root(root):
    (root / "state").mkdir()
    baseline = {"domain:base%d.example" % i for i in range(100000)}
    update_rules.atomic_write(root / "state" / "baseline-direct-domains.txt", update_rules.render_entries(baseline), 0o600)
    fixture = root / "fixture"
    fixture.mkdir()
    (fixture / "general.txt").write_text("payload:\n" + "\n".join("  - '+.base%d.example'" % i for i in range(100000)) + "\n  - '+.xhs.example'\n")
    (fixture / "xhs.yaml").write_text("payload:\n  - +.xhs.example\n  - +.cdn-xhs.example\n  - full:api.xhs.example\n")
    return fixture


def manifest(**overrides):
    m = {
        "general_direct": {"id": "general", "urls": [], "min_count": 100000, "max_count": 130000, "max_new_per_run": 10, "exclude": []},
        "services": {"xhs": {"display_name": "XHS", "source_note": "s", "urls": [], "min_count": 1, "max_count": 20,
                             "canary": "img.cdn-xhs.example", "include": [], "exclude": []}},
        "forced_proxy": {"domains": ["xhs.example"], "canary": "www.xhs.example"},
        "canaries": {"proxy": ["chatgpt.com"]},
    }
    m.update(overrides)
    return m


class ForcedProxyTests(unittest.TestCase):
    def test_forced_suffix_removed_from_direct_outputs_and_emitted_as_proxy(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); fixture = make_root(root)
            compiled = update_rules.compile_rules(manifest(), root, fixture)
            self.assertEqual(compiled["services"]["xhs"], {"domain:cdn-xhs.example"})
            self.assertNotIn("domain:xhs.example", compiled["managed"])
            self.assertNotIn("full:api.xhs.example", compiled["managed"])
            self.assertNotIn("domain:xhs.example", compiled["accumulated"])
            self.assertEqual(compiled["proxy_bytes"].decode(), "domain:xhs.example\n")
            self.assertIn("DOMAIN-SUFFIX,xhs.example", compiled["surge_proxy_bytes"].decode())
            self.assertNotIn("xhs.example", [l.split(",", 1)[1] for l in compiled["surge_ruleset_bytes"].decode().splitlines() if l.startswith("DOMAIN")])
            self.assertEqual(compiled["canaries_bytes"].decode(), "direct img.cdn-xhs.example\nproxy chatgpt.com\nproxy www.xhs.example\n")

    def test_service_canary_under_forced_suffix_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); fixture = make_root(root)
            m = manifest(); m["services"]["xhs"]["canary"] = "www.xhs.example"
            with self.assertRaises(update_rules.RuleError):
                update_rules.compile_rules(m, root, fixture)

    def test_forced_canary_must_be_under_forced_suffix(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); fixture = make_root(root)
            m = manifest(); m["forced_proxy"]["canary"] = "img.cdn-xhs.example"
            with self.assertRaises(update_rules.RuleError):
                update_rules.compile_rules(m, root, fixture)

    def test_without_forced_proxy_section_outputs_are_empty_but_valid(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); fixture = make_root(root)
            m = manifest(); del m["forced_proxy"]
            compiled = update_rules.compile_rules(m, root, fixture)
            self.assertEqual(compiled["proxy_bytes"], b"")
            self.assertIn("domain:xhs.example", compiled["managed"])
            self.assertEqual(compiled["canaries_bytes"].decode(), "direct img.cdn-xhs.example\nproxy chatgpt.com\n")


if __name__ == "__main__":
    unittest.main()
