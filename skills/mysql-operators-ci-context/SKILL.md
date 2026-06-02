---
name: mysql-operators-ci-context
description: Explain how pull request CI works in canonical/mysql-operators, including which workflows run, how matrix job names map to charm paths and spread tests, and what repository-specific shortcuts matter during CI investigation. Use when a user asks how this repository's PR CI is structured or when other CI skills need mysql-operators-specific interpretation.
compatibility: Best for environments with read access to the canonical/mysql-operators repository and its GitHub pull request and Actions data.
---

# mysql-operators CI context

Use this skill for repository-specific interpretation of PR CI in `canonical/mysql-operators`.

## Defaults

- Default owner: `canonical`
- Default repo: `mysql-operators`
- Default PR CI workflows:
  - `.github/workflows/ci.yaml`
  - `.github/workflows/check_pr.yaml`
  - `.github/workflows/integration_test.yaml`

## How to use this skill

1. Use it before or alongside generic PR CI skills when the user is asking about this repository.
2. Read `references/workflows.md` for the workflow map.
3. Use the workflow map to explain why:
   - docs-only or markdown-only changes may not trigger the main PR workflow
   - one integration workflow run expands into many check runs
   - build and policy checks come from reusable workflows

## Interpretation rules

- Treat `Pull request` as the main CI workflow from `.github/workflows/ci.yaml`.
- Treat `Check pull request` as a separate pull-request policy workflow.
- When a check name starts with `Integration tests (kubernetes)` or `Integration tests (machines)`, it comes from the reusable integration workflow and usually corresponds to one spread task variant.
- When many integration checks fail together, start by checking for shared runner or setup problems before assuming many independent test regressions.

## Suggested uses

- explain the CI layout for a PR
- map a failing check name back to the workflow file
- identify whether a missing workflow result is expected
- explain artifact naming and matrix fan-out
