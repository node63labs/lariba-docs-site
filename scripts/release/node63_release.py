#!/usr/bin/env python3

import argparse
import json
import re
from datetime import datetime
from pathlib import Path


class RecordError(Exception):
    pass


SHA_RE = re.compile(r"^[0-9a-f]{40}$")

ALLOWED_CLASSES = {
    "RC-01",
    "RC-02",
    "RC-03",
    "RC-04",
    "RC-05",
}

STATE_RULES = {
    "CANDIDATE": {
        "authorization": "ABSENT",
        "release_action": "ABSENT",
        "verification": "ABSENT",
        "acceptance": "ABSENT",
        "failure_recovery": "ABSENT",
    },
    "AUTHORIZED": {
        "authorization": "AUTHORIZED",
        "release_action": "ABSENT",
        "verification": "ABSENT",
        "acceptance": "ABSENT",
        "failure_recovery": "ABSENT",
    },
    "DENIED": {
        "authorization": "DENIED",
        "release_action": "ABSENT",
        "verification": "ABSENT",
        "acceptance": "ABSENT",
        "failure_recovery": "ABSENT",
    },
    "RELEASED": {
        "authorization": "AUTHORIZED",
        "release_action": "REQUIRED",
        "verification": "ABSENT",
        "acceptance": "ABSENT",
        "failure_recovery": "ABSENT",
    },
    "VERIFIED": {
        "authorization": "AUTHORIZED",
        "release_action": "REQUIRED",
        "verification": "PASS",
        "acceptance": "ABSENT",
        "failure_recovery": "ABSENT",
    },
    "ACCEPTED": {
        "authorization": "AUTHORIZED",
        "release_action": "REQUIRED",
        "verification": "PASS",
        "acceptance": "ACCEPTED",
        "failure_recovery": "ABSENT",
    },
    "REJECTED": {
        "authorization": "AUTHORIZED",
        "release_action": "REQUIRED",
        "verification": "PASS",
        "acceptance": "REJECTED",
        "failure_recovery": "ABSENT",
    },
    "FAILED": {
        "authorization": "AUTHORIZED",
        "release_action": "CONDITIONAL",
        "verification": "FAIL_IF_PRESENT",
        "acceptance": "ABSENT",
        "failure_recovery": "FAILURE_REQUIRED",
    },
    "ROLLED_BACK": {
        "authorization": "AUTHORIZED",
        "release_action": "REQUIRED",
        "verification": "OPTIONAL",
        "acceptance": "OPTIONAL",
        "failure_recovery": "ROLLBACK_REQUIRED",
    },
    "RECOVERED": {
        "authorization": "AUTHORIZED",
        "release_action": "CONDITIONAL",
        "verification": "OPTIONAL",
        "acceptance": "OPTIONAL",
        "failure_recovery": "RECOVERY_REQUIRED",
    },
}


def require(condition, message):
    if not condition:
        raise RecordError(message)


def present(record, key):
    return (
        key in record
        and record[key] is not None
    )


def require_absent(record, key):
    require(
        not present(record, key),
        f"{key} must be absent",
    )


def parse_datetime(value, field):
    require(
        isinstance(value, str)
        and value,
        f"{field} must be a non-empty date-time",
    )

    try:
        parsed = datetime.fromisoformat(
            value.replace("Z", "+00:00")
        )
    except ValueError as exc:
        raise RecordError(
            f"{field} is not a valid ISO date-time"
        ) from exc

    require(
        parsed.tzinfo is not None,
        f"{field} must include timezone information",
    )


def require_evidence(value, field):
    require(
        isinstance(value, list)
        and len(value) > 0,
        f"{field} must be a non-empty array",
    )

    for index, item in enumerate(value):
        require(
            isinstance(item, dict),
            f"{field}[{index}] must be an object",
        )

        require(
            isinstance(item.get("kind"), str)
            and item["kind"],
            f"{field}[{index}].kind missing",
        )

        require(
            isinstance(item.get("locator"), str)
            and item["locator"],
            f"{field}[{index}].locator missing",
        )


def validate_authorization(record, expected):
    if expected == "ABSENT":
        require_absent(
            record,
            "authorization",
        )
        return

    auth = record.get("authorization")

    require(
        isinstance(auth, dict),
        "authorization object required",
    )

    require(
        auth.get("decision") == expected,
        (
            "authorization.decision must be "
            f"{expected}"
        ),
    )

    require(
        isinstance(auth.get("authority"), str)
        and auth["authority"],
        "authorization.authority required",
    )

    parse_datetime(
        auth.get("decided_at"),
        "authorization.decided_at",
    )

    require_evidence(
        auth.get("evidence"),
        "authorization.evidence",
    )


def validate_release_action(record, requirement):
    exists = present(
        record,
        "release_action",
    )

    if requirement == "ABSENT":
        require(
            not exists,
            "release_action must be absent",
        )
        return

    if requirement == "CONDITIONAL" and not exists:
        return

    require(
        exists,
        "release_action required",
    )

    action = record["release_action"]

    require(
        isinstance(action, dict),
        "release_action must be an object",
    )

    require(
        isinstance(action.get("kind"), str)
        and action["kind"],
        "release_action.kind required",
    )

    require(
        isinstance(action.get("target"), str)
        and action["target"],
        "release_action.target required",
    )

    parse_datetime(
        action.get("occurred_at"),
        "release_action.occurred_at",
    )

    require_evidence(
        action.get("evidence"),
        "release_action.evidence",
    )


def validate_verification(record, requirement):
    exists = present(
        record,
        "verification",
    )

    if requirement == "ABSENT":
        require(
            not exists,
            "verification must be absent",
        )
        return

    if requirement == "OPTIONAL" and not exists:
        return

    if requirement == "FAIL_IF_PRESENT" and not exists:
        return

    require(
        exists,
        "verification required",
    )

    verification = record["verification"]

    require(
        isinstance(verification, dict),
        "verification must be an object",
    )

    if requirement == "PASS":
        require(
            verification.get("result") == "PASS",
            "verification.result must be PASS",
        )

    elif requirement == "FAIL_IF_PRESENT":
        require(
            verification.get("result") == "FAIL",
            "verification.result must be FAIL",
        )

    else:
        require(
            verification.get("result")
            in {"PASS", "FAIL"},
            "verification.result invalid",
        )

    if "verified_at" in verification:
        parse_datetime(
            verification["verified_at"],
            "verification.verified_at",
        )

    if "evidence" in verification:
        require_evidence(
            verification["evidence"],
            "verification.evidence",
        )


def validate_acceptance(record, requirement):
    exists = present(
        record,
        "acceptance",
    )

    if requirement == "ABSENT":
        require(
            not exists,
            "acceptance must be absent",
        )
        return

    if requirement == "OPTIONAL" and not exists:
        return

    require(
        exists,
        "acceptance required",
    )

    acceptance = record["acceptance"]

    require(
        isinstance(acceptance, dict),
        "acceptance must be an object",
    )

    expected = (
        requirement
        if requirement in {
            "ACCEPTED",
            "REJECTED",
        }
        else None
    )

    if expected is not None:
        require(
            acceptance.get("result") == expected,
            (
                "acceptance.result must be "
                f"{expected}"
            ),
        )

    else:
        require(
            acceptance.get("result")
            in {"ACCEPTED", "REJECTED"},
            "acceptance.result invalid",
        )


def validate_failure_recovery(
    record,
    requirement,
):
    exists = present(
        record,
        "failure_recovery",
    )

    if requirement == "ABSENT":
        require(
            not exists,
            "failure_recovery must be absent",
        )
        return

    require(
        exists,
        "failure_recovery required",
    )

    recovery = record["failure_recovery"]

    require(
        isinstance(recovery, list)
        and len(recovery) > 0,
        "failure_recovery must be a non-empty array",
    )

    for index, item in enumerate(recovery):
        require(
            isinstance(item, dict),
            (
                "failure_recovery"
                f"[{index}] must be an object"
            ),
        )

        require_evidence(
            item.get("evidence"),
            (
                "failure_recovery"
                f"[{index}].evidence"
            ),
        )


def load_record(record_path):
    path = Path(record_path)

    require(
        not path.is_absolute(),
        "record path must be repository-relative",
    )

    require(
        ".." not in path.parts,
        "record path traversal prohibited",
    )

    require(
        len(path.parts) >= 3
        and path.parts[0] == "evidence"
        and path.parts[1] == "releases",
        (
            "record must use ST-01 path "
            "evidence/releases/"
        ),
    )

    require(
        path.suffix == ".json",
        "release record must be JSON",
    )

    try:
        return json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )
    except Exception as exc:
        raise RecordError(
            f"unable to load release record: {exc}"
        ) from exc


def validate_record(
    record,
    repository,
    release_class,
    source_sha,
):
    require(
        isinstance(record, dict),
        "release record must be an object",
    )

    require(
        record.get("schema_version")
        == "1.0.0",
        "schema_version must be 1.0.0",
    )

    require(
        isinstance(record.get("record_id"), str)
        and record["record_id"],
        "record_id required",
    )

    parse_datetime(
        record.get("recorded_at"),
        "recorded_at",
    )

    state = record.get("lifecycle_state")

    require(
        state in STATE_RULES,
        f"unsupported lifecycle_state: {state}",
    )

    require(
        release_class in ALLOWED_CLASSES,
        f"unsupported release class: {release_class}",
    )

    require(
        record.get("release_class")
        == release_class,
        "release_class mismatch",
    )

    require(
        record.get("repository")
        == repository,
        "repository mismatch",
    )

    source = record.get("source")

    require(
        isinstance(source, dict),
        "source object required",
    )

    commit_sha = source.get("commit_sha")

    require(
        isinstance(commit_sha, str)
        and SHA_RE.fullmatch(commit_sha),
        "source.commit_sha invalid",
    )

    require(
        commit_sha == source_sha,
        "source.commit_sha does not match governed source",
    )

    require(
        isinstance(source.get("ref"), str)
        and source["ref"],
        "source.ref required",
    )

    release_identity = record.get(
        "release_identity"
    )

    require(
        isinstance(release_identity, dict)
        and release_identity,
        "release_identity required",
    )

    if release_class in {
        "RC-04",
        "RC-05",
    }:
        build = record.get("build")

        require(
            isinstance(build, dict),
            (
                "build object required for "
                f"{release_class}"
            ),
        )

        require_evidence(
            build.get("ci_evidence"),
            "build.ci_evidence",
        )

    rules = STATE_RULES[state]

    validate_authorization(
        record,
        rules["authorization"],
    )

    validate_release_action(
        record,
        rules["release_action"],
    )

    validate_verification(
        record,
        rules["verification"],
    )

    validate_acceptance(
        record,
        rules["acceptance"],
    )

    validate_failure_recovery(
        record,
        rules["failure_recovery"],
    )

    return {
        "record_id": record["record_id"],
        "repository": repository,
        "release_class": release_class,
        "source_sha": source_sha,
        "lifecycle_state": state,
        "result": "PASS",
    }


def validate_gate(
    record,
    repository,
    release_class,
    source_sha,
    release_authority_ref,
):
    result = validate_record(
        record,
        repository,
        release_class,
        source_sha,
    )

    require(
        record["lifecycle_state"]
        == "AUTHORIZED",
        (
            "CI-C09 requires lifecycle_state "
            "AUTHORIZED"
        ),
    )

    require_absent(
        record,
        "release_action",
    )

    require_absent(
        record,
        "verification",
    )

    require_absent(
        record,
        "acceptance",
    )

    require_absent(
        record,
        "failure_recovery",
    )

    require(
        isinstance(release_authority_ref, str)
        and release_authority_ref
        not in {
            "",
            "NONE",
            "NOT_AUTHORIZED",
        },
        (
            "separate release authority "
            "reference required"
        ),
    )

    evidence = (
        record["authorization"]["evidence"]
    )

    locators = {
        item["locator"]
        for item in evidence
    }

    require(
        release_authority_ref in locators,
        (
            "release authority reference "
            "must match durable authorization evidence"
        ),
    )

    result["release_authority_ref"] = (
        release_authority_ref
    )

    result["gate"] = "ALLOW"

    return result


def main():
    parser = argparse.ArgumentParser()

    sub = parser.add_subparsers(
        dest="command",
        required=True,
    )

    for name in ("validate", "gate"):
        p = sub.add_parser(name)

        p.add_argument(
            "--record",
            required=True,
        )

        p.add_argument(
            "--repository",
            required=True,
        )

        p.add_argument(
            "--release-class",
            required=True,
        )

        p.add_argument(
            "--source-sha",
            required=True,
        )

        if name == "gate":
            p.add_argument(
                "--release-authority-ref",
                required=True,
            )

    args = parser.parse_args()

    try:
        record = load_record(
            args.record
        )

        if args.command == "validate":
            result = validate_record(
                record,
                args.repository,
                args.release_class,
                args.source_sha,
            )

        else:
            result = validate_gate(
                record,
                args.repository,
                args.release_class,
                args.source_sha,
                args.release_authority_ref,
            )

        print(
            json.dumps(
                result,
                sort_keys=True,
            )
        )

    except RecordError as exc:
        print(
            f"NODE63_RELEASE_RECORD_ERROR={exc}"
        )
        raise SystemExit(1)


if __name__ == "__main__":
    main()
