# mysql-operators pull request workflows

## Main PR workflow

File: `.github/workflows/ci.yaml`

Trigger:
- `pull_request`
- ignores `docs/**`
- ignores `**.md`
- ignores `.github/renovate.json5`

Top-level jobs:
- `lint` with a `kubernetes` and `machines` matrix
- `unit-test` with a `kubernetes` and `machines` matrix
- `alert-test` with a `kubernetes` and `machines` matrix
- `build` with a `kubernetes` and `machines` matrix through `canonical/data-platform-workflows/.github/workflows/build_charm.yaml`
- `integration-test` with a `kubernetes` and `machines` matrix through the local reusable workflow `.github/workflows/integration_test.yaml`

## Pull-request policy workflow

File: `.github/workflows/check_pr.yaml`

Trigger:
- `pull_request`
- types `opened`, `labeled`, `unlabeled`, `edited`
- branch `8.4/edge`

Purpose:
- repository policy checks for pull requests

## Integration workflow

File: `.github/workflows/integration_test.yaml`

Important details:
- The workflow first collects spread jobs and then fans out into a large matrix.
- Check names look like:
  - `Integration tests (kubernetes) / test_storage.py:juju36 | amd64 | kubernetes`
  - `Integration tests (machines) / test_upgrade.py:juju36 | amd64 | machines`
- The matrix names come from spread job metadata and the charm path.

Use these mappings when you need to explain why one workflow produced many GitHub check runs.
