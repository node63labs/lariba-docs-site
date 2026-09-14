import importlib.util
import unittest
from pathlib import Path


MODULE_PATH = (
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "release"
    / "node63_release.py"
)

SPEC = importlib.util.spec_from_file_location(
    "node63_release",
    MODULE_PATH,
)

node63_release = importlib.util.module_from_spec(
    SPEC
)

SPEC.loader.exec_module(
    node63_release
)


def authorized_record(
    release_class="RC-04",
    repository="node63labs/lariba-sdk-js",
    sha="a" * 40,
):
    record = {
        "schema_version": "1.0.0",
        "record_id": "TEST-001",
        "recorded_at": "2026-09-13T00:00:00Z",
        "lifecycle_state": "AUTHORIZED",
        "release_class": release_class,
        "repository": repository,
        "release_identity": {
            "kind": "version",
            "value": "test",
        },
        "source": {
            "commit_sha": sha,
            "ref": "main",
        },
        "authorization": {
            "decision": "AUTHORIZED",
            "authority": "node63-governance",
            "decided_at": "2026-09-13T00:00:00Z",
            "evidence": [
                {
                    "kind": "approval",
                    "locator": "governance:test-authority",
                }
            ],
        },
    }

    if release_class in {
        "RC-04",
        "RC-05",
    }:
        record["build"] = {
            "ci_evidence": [
                {
                    "kind": "ci-run",
                    "locator": "github:run:test",
                }
            ]
        }

    return record


class ReleaseRecordTests(unittest.TestCase):

    def test_authorized_record_passes(self):
        record = authorized_record()

        result = node63_release.validate_record(
            record,
            "node63labs/lariba-sdk-js",
            "RC-04",
            "a" * 40,
        )

        self.assertEqual(
            result["lifecycle_state"],
            "AUTHORIZED",
        )

    def test_authorized_release_action_blocks(self):
        record = authorized_record()

        record["release_action"] = {
            "kind": "package_publication",
            "target": "registry",
            "occurred_at": "2026-09-13T00:01:00Z",
            "evidence": [
                {
                    "kind": "publication",
                    "locator": "example",
                }
            ],
        }

        with self.assertRaises(
            node63_release.RecordError
        ):
            node63_release.validate_record(
                record,
                "node63labs/lariba-sdk-js",
                "RC-04",
                "a" * 40,
            )

    def test_gate_requires_matching_authority(self):
        record = authorized_record()

        with self.assertRaises(
            node63_release.RecordError
        ):
            node63_release.validate_gate(
                record,
                "node63labs/lariba-sdk-js",
                "RC-04",
                "a" * 40,
                "governance:wrong",
            )

        result = node63_release.validate_gate(
            record,
            "node63labs/lariba-sdk-js",
            "RC-04",
            "a" * 40,
            "governance:test-authority",
        )

        self.assertEqual(
            result["gate"],
            "ALLOW",
        )

    def test_source_sha_mismatch_blocks(self):
        record = authorized_record()

        with self.assertRaises(
            node63_release.RecordError
        ):
            node63_release.validate_record(
                record,
                "node63labs/lariba-sdk-js",
                "RC-04",
                "b" * 40,
            )

    def test_released_requires_release_action(self):
        record = authorized_record()

        record["lifecycle_state"] = "RELEASED"

        with self.assertRaises(
            node63_release.RecordError
        ):
            node63_release.validate_record(
                record,
                "node63labs/lariba-sdk-js",
                "RC-04",
                "a" * 40,
            )


if __name__ == "__main__":
    unittest.main()
