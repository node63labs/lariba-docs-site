# NODE63 Release Evidence

Repository: `node63labs/lariba-docs-site`

Release class: `RC-03`

W3 gap: `W3-GAP-04`

This directory is the repository's ST-01 durable primary
release-evidence surface.

Canonical records use:

`evidence/releases/<record-id>.json`

Before a material release, the CI-C09 gate requires a record
in lifecycle state `AUTHORIZED`.

At `AUTHORIZED`:

- authorization evidence is required;
- release_action is absent;
- verification is absent;
- acceptance is absent;
- failure_recovery is absent.

The release-gate workflow validates evidence only. It does not
publish packages, create tags, deploy providers, push repository
state, or mutate a database.

Material release execution requires separate durable authority.

Current W3 gap closure: `NO`.
