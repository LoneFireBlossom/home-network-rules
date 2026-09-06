import json
from pathlib import Path
import tempfile
import unittest

import update_rules


class RuleCompilerTests(unittest.TestCase):
    def test_parse_clash_payload(self):
        text = "payload:\n  - '+.example.com'\n  - 'exact.example.net'\n"
        self.assertEqual(
            update_rules.parse_clash_payload(text, "fixture"),
            {"domain:example.com", "full:exact.example.net"},
        )

    def test_rejects_non_domain_rule(self):
        with self.assertRaises(update_rules.RuleError):
            update_rules.parse_clash_payload("payload:\n  - IP-ASN,13335\n", "fixture")

    def test_rendered_ruleset_contains_service_sections_without_policy(self):
        service_defs = {
            "alpha": {"display_name": "Alpha", "source_note": "source alpha"},
            "beta": {"display_name": "Beta", "source_note": "source beta"},
        }
        services = {
            "alpha": {"full:a.example"},
            "beta": {"domain:b.example"},
        }
        output = update_rules.render_surge_ruleset(services, service_defs).decode()
        self.assertIn("# ===== Alpha =====", output)
        self.assertIn("# ===== Beta =====", output)
        rule_lines = [line for line in output.splitlines() if line.startswith(("DOMAIN,", "DOMAIN-SUFFIX,"))]
        self.assertIn("DOMAIN,a.example", rule_lines)
        self.assertIn("DOMAIN-SUFFIX,b.example", rule_lines)
        self.assertTrue(all("," not in line.split(",", 1)[1] for line in rule_lines), "rule lines must not carry a trailing policy")
        self.assertNotIn("IP-ASN", output)

    def test_compile_merges_upstream_and_local_rules(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "state").mkdir()
            baseline = {"domain:existing.example", *{"domain:base%d.example" % i for i in range(100000)}}
            update_rules.atomic_write(root / "state" / "baseline-direct-domains.txt", update_rules.render_entries(baseline), 0o600)
            fixture = root / "fixture"
            fixture.mkdir()
            (fixture / "general.txt").write_text("payload:\n" + "\n".join("  - '+.base%d.example'" % i for i in range(100000)) + "\n  - '+.new.example'\n")
            (fixture / "xiaohongshu.yaml").write_text("payload:\n  - +.xiaohongshu.com\n  - +.rednote.com.my\n")
            manifest = {
                "general_direct": {
                    "id": "general",
                    "urls": [],
                    "min_count": 100000,
                    "max_count": 130000,
                    "max_new_per_run": 10,
                    "exclude": [],
                },
                "services": {
                    "xiaohongshu": {
                        "display_name": "XHS",
                        "source_note": "source xhs",
                        "urls": [],
                        "min_count": 1,
                        "max_count": 20,
                        "canary": "xiaohongshu.com",
                        "include": ["rednote.com"],
                        "exclude": ["rednote.com.my"],
                    }
                },
                "canaries": {"proxy": ["chatgpt.com"]},
            }
            compiled = update_rules.compile_rules(manifest, root, fixture)
            self.assertIn("domain:new.example", compiled["accumulated"])
            self.assertEqual(compiled["services"]["xiaohongshu"], {"domain:xiaohongshu.com", "domain:rednote.com"})
            self.assertNotIn("domain:rednote.com.my", compiled["managed"])
            ruleset_text = compiled["surge_ruleset_bytes"].decode()
            self.assertIn("# ===== XHS =====", ruleset_text)
            rule_lines = [line for line in ruleset_text.splitlines() if line.startswith(("DOMAIN,", "DOMAIN-SUFFIX,"))]
            self.assertTrue(all("," not in line.split(",", 1)[1] for line in rule_lines), "rule lines must not carry a trailing policy")

    def test_general_addition_gate(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "state").mkdir()
            baseline = {"domain:base%d.example" % i for i in range(100000)}
            update_rules.atomic_write(root / "state" / "baseline-direct-domains.txt", update_rules.render_entries(baseline), 0o600)
            fixture = root / "fixture"
            fixture.mkdir()
            source_domains = {"base%d.example" % i for i in range(100000)} | {"new%d.example" % i for i in range(11)}
            (fixture / "general.txt").write_text("payload:\n" + "\n".join("  - '+.%s'" % domain for domain in sorted(source_domains)))
            (fixture / "service.yaml").write_text("payload:\n  - +.service.example\n")
            manifest = {
                "general_direct": {
                    "id": "general",
                    "urls": [],
                    "min_count": 100000,
                    "max_count": 130000,
                    "max_new_per_run": 10,
                    "exclude": [],
                },
                "services": {
                    "service": {
                        "display_name": "Service",
                        "source_note": "source service",
                        "urls": [],
                        "min_count": 1,
                        "max_count": 20,
                        "canary": "service.example",
                        "include": [],
                        "exclude": [],
                    }
                },
            }
            with self.assertRaises(update_rules.RuleError):
                update_rules.compile_rules(manifest, root, fixture)


if __name__ == "__main__":
    unittest.main()
