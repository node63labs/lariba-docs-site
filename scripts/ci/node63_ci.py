#!/usr/bin/env python3

import argparse
import json
import re
from pathlib import Path


class ValidationError(Exception):
    pass


SHA_RE = re.compile(r"^[0-9a-f]{40}$")

PROFILES = {
    "CI-P03": {
        "repository": "node63labs/lariba-docs-site",
        "ci_c02": "NOT_APPLICABLE",
        "ci_c03": "REQUIRED_BUILD",
    },
    "CI-P04": {
        "repository": "node63labs/lariba-sdk-js",
        "ci_c02": "REQUIRED_TEST",
        "ci_c03": "REQUIRED_BUILD",
    },
    "CI-P05": {
        "repository": "node63labs/lariba-spec",
        "ci_c02": "NOT_APPLICABLE",
        "ci_c03": "REQUIRED_CONTRACT_VALIDATION",
    },
}


def require(condition, message):
    if not condition:
        raise ValidationError(message)


def validate_sha(value):
    require(
        isinstance(value, str)
        and SHA_RE.fullmatch(value) is not None,
        "source SHA must be 40 lowercase hexadecimal characters",
    )


def load_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValidationError(
            f"unable to load JSON: {path}: {exc}"
        ) from exc


def inspect_repository(profile, root):
    root = Path(root)

    if profile == "CI-P03":
        package = load_json(root / "package.json")
        scripts = package.get("scripts", {})

        for key in ("lint", "typecheck", "build"):
            require(
                key in scripts,
                f"docs package.json missing script: {key}",
            )

        require(
            "test" not in scripts,
            "docs CI-C02 resolution changed: test script now exists",
        )

    elif profile == "CI-P04":
        package = load_json(root / "package.json")
        scripts = package.get("scripts", {})

        for key in ("typecheck", "test", "build"):
            require(
                key in scripts,
                f"sdk package.json missing script: {key}",
            )

    elif profile == "CI-P05":
        spec = load_json(root / "openapi.json")

        require(
            isinstance(spec.get("openapi"), str),
            "openapi version missing",
        )

        require(
            spec["openapi"].startswith("3."),
            "OpenAPI 3.x required",
        )

        info = spec.get("info")

        require(
            isinstance(info, dict),
            "OpenAPI info object missing",
        )

        require(
            isinstance(info.get("title"), str)
            and info["title"],
            "OpenAPI title missing",
        )

        require(
            isinstance(info.get("version"), str)
            and info["version"],
            "OpenAPI info.version missing",
        )

        require(
            isinstance(spec.get("paths"), dict),
            "OpenAPI paths object missing",
        )

    else:
        raise ValidationError(
            f"unsupported profile: {profile}"
        )


def validate_profile(
    profile,
    repository,
    source_sha,
    source_kind,
    root,
):
    require(
        profile in PROFILES,
        f"unsupported profile: {profile}",
    )

    cfg = PROFILES[profile]

    require(
        repository == cfg["repository"],
        (
            f"profile {profile} requires repository "
            f"{cfg['repository']}"
        ),
    )

    validate_sha(source_sha)

    require(
        source_kind in {
            "PR_TEST_MERGE",
            "PUSH_TIP",
        },
        f"unsupported source kind: {source_kind}",
    )

    inspect_repository(profile, root)

    return {
        "profile": profile,
        "repository": repository,
        "source_sha": source_sha,
        "source_kind": source_kind,
        "ci_c02": cfg["ci_c02"],
        "ci_c03": cfg["ci_c03"],
        "result": "PASS",
    }


def resolve_control(profile, control):
    require(
        profile in PROFILES,
        f"unsupported profile: {profile}",
    )

    require(
        control in {"CI-C02", "CI-C03"},
        f"unsupported conditional control: {control}",
    )

    key = (
        "ci_c02"
        if control == "CI-C02"
        else "ci_c03"
    )

    return PROFILES[profile][key]


def validate_openapi(path, source_sha):
    validate_sha(source_sha)

    spec = load_json(path)

    require(
        isinstance(spec.get("openapi"), str)
        and spec["openapi"].startswith("3."),
        "OpenAPI 3.x required",
    )

    require(
        isinstance(spec.get("info"), dict),
        "OpenAPI info object missing",
    )

    require(
        isinstance(spec.get("paths"), dict),
        "OpenAPI paths object missing",
    )

    return {
        "source_sha": source_sha,
        "openapi": spec["openapi"],
        "result": "PASS",
    }


def main():
    parser = argparse.ArgumentParser()

    sub = parser.add_subparsers(
        dest="command",
        required=True,
    )

    p_profile = sub.add_parser("profile")
    p_profile.add_argument("--profile", required=True)
    p_profile.add_argument("--repository", required=True)
    p_profile.add_argument("--source-sha", required=True)
    p_profile.add_argument("--source-kind", required=True)
    p_profile.add_argument("--root", default=".")

    p_control = sub.add_parser("control")
    p_control.add_argument("--profile", required=True)
    p_control.add_argument("--control", required=True)

    p_openapi = sub.add_parser("openapi")
    p_openapi.add_argument("--path", required=True)
    p_openapi.add_argument("--source-sha", required=True)

    args = parser.parse_args()

    try:
        if args.command == "profile":
            result = validate_profile(
                args.profile,
                args.repository,
                args.source_sha,
                args.source_kind,
                args.root,
            )
            print(
                json.dumps(
                    result,
                    sort_keys=True,
                )
            )

        elif args.command == "control":
            print(
                resolve_control(
                    args.profile,
                    args.control,
                )
            )

        elif args.command == "openapi":
            result = validate_openapi(
                args.path,
                args.source_sha,
            )
            print(
                json.dumps(
                    result,
                    sort_keys=True,
                )
            )

    except ValidationError as exc:
        print(
            f"NODE63_CI_VALIDATION_ERROR={exc}"
        )
        raise SystemExit(1)


if __name__ == "__main__":
    main()
