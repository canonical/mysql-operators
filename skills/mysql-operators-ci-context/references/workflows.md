# Workflow map for canonical/mysql-operators

## `.github/workflows/ci.yaml`

Workflow name:
- `Pull request`

Purpose:
- main pull request CI

Jobs:
- lint
- unit-test
- alert-test
- build
- integration-test

Most jobs fan out over:
- `kubernetes`
- `machines`

The integration step calls the reusable workflow in `.github/workflows/integration_test.yaml`.

## `.github/workflows/check_pr.yaml`

Workflow name:
- `Check pull request`

Purpose:
- policy and pull-request metadata checks

## `.github/workflows/integration_test.yaml`

Workflow name:
- `Integration tests`

Purpose:
- collect spread jobs and run a large matrix of integration checks

Naming behavior:
- visible GitHub check names include the charm path and spread job details
- example pattern: `<test-file>:<variant> | <architecture> | <path>`

Important consequence:
- one failing workflow run can create many failed check runs, so summarize at both the workflow and job level
