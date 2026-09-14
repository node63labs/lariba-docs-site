import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = (
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "ci"
    / "node63_ci.py"
)

SPEC = importlib.util.spec_from_file_location(
    "node63_ci",
    MODULE_PATH,
)

node63_ci = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(node63_ci)


class Node63CITests(unittest.TestCase):

    def test_sha_validation(self):
        node63_ci.validate_sha("a" * 40)

        with self.assertRaises(
            node63_ci.ValidationError
        ):
            node63_ci.validate_sha("bad")

    def test_control_resolution(self):
        self.assertEqual(
            node63_ci.resolve_control(
                "CI-P03",
                "CI-C02",
            ),
            "NOT_APPLICABLE",
        )

        self.assertEqual(
            node63_ci.resolve_control(
                "CI-P04",
                "CI-C02",
            ),
            "REQUIRED_TEST",
        )

        self.assertEqual(
            node63_ci.resolve_control(
                "CI-P05",
                "CI-C03",
            ),
            "REQUIRED_CONTRACT_VALIDATION",
        )

    def test_docs_profile(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)

            (
                root / "package.json"
            ).write_text(
                json.dumps(
                    {
                        "scripts": {
                            "lint": "eslint .",
                            "typecheck": "tsc --noEmit",
                            "build": "next build",
                        }
                    }
                ),
                encoding="utf-8",
            )

            result = node63_ci.validate_profile(
                "CI-P03",
                "node63labs/lariba-docs-site",
                "1" * 40,
                "PUSH_TIP",
                root,
            )

            self.assertEqual(
                result["result"],
                "PASS",
            )

    def test_sdk_profile(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)

            (
                root / "package.json"
            ).write_text(
                json.dumps(
                    {
                        "scripts": {
                            "typecheck": "tsc --noEmit",
                            "test": "npm run typecheck",
                            "build": "tsup",
                        }
                    }
                ),
                encoding="utf-8",
            )

            result = node63_ci.validate_profile(
                "CI-P04",
                "node63labs/lariba-sdk-js",
                "2" * 40,
                "PR_TEST_MERGE",
                root,
            )

            self.assertEqual(
                result["result"],
                "PASS",
            )

    def test_spec_profile(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)

            (
                root / "openapi.json"
            ).write_text(
                json.dumps(
                    {
                        "openapi": "3.1.0",
                        "info": {
                            "title": "Example",
                            "version": "1.0.0",
                        },
                        "paths": {},
                    }
                ),
                encoding="utf-8",
            )

            result = node63_ci.validate_profile(
                "CI-P05",
                "node63labs/lariba-spec",
                "3" * 40,
                "PUSH_TIP",
                root,
            )

            self.assertEqual(
                result["result"],
                "PASS",
            )


if __name__ == "__main__":
    unittest.main()
