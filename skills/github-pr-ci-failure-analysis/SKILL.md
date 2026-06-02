---
name: github-pr-ci-failure-analysis
description: Diagnose why a GitHub pull request CI job failed by finding the failing workflow run, loading the failed job logs, and summarizing the root cause and next evidence to inspect. Use when a user asks why CI failed, which jobs are broken, or wants a failure triage summary for a PR.
compatibility: Requires GitHub pull request and Actions access. Best with tools that can read PR metadata, workflow jobs, and job logs.
---

# GitHub PR CI failure analysis

Use this skill after identifying a failing PR or when the user asks for failure triage directly.

## Workflow

1. Resolve the pull request and head SHA.
2. Find failing or cancelled checks for the current head commit.
3. Map those checks to workflow runs and job ids.
4. Load the failing job logs.
   - Prefer job-specific logs.
   - If many jobs failed in the same run, you can also load failed jobs for the whole run.
5. Classify each failure before proposing next steps:
   - lint or formatting failure
   - unit-test assertion failure
   - build or packaging failure
   - integration-test failure
   - environment or infrastructure failure
   - timeout or cancellation
6. Summarize the likely root cause.
   - Quote the key failing command, test name, assertion, or infrastructure error.
   - Keep the summary short and evidence-based.
7. If more evidence is needed, point to the next artifact or workflow file to inspect.

## mysql-operators routing notes

- Read `references/failure-signals.md` for repository-specific failure patterns.
- The main PR workflow runs lint, unit, alert, build, and integration jobs.
- Integration failures often come from spread jobs inside the reusable integration workflow, so the failing GitHub job name often includes the test file, Juju variant, architecture, and charm path.
- When a large number of integration checks fail together, first look for shared setup failures rather than isolated test regressions.

## Output shape

Prefer:

- failing workflow / run id
- failing job names
- root cause category
- key evidence
- whether the failure looks code-related, flaky, or infrastructure-related
- what to inspect next if the evidence is incomplete

## Guardrails

- Do not guess beyond the visible log evidence.
- Distinguish test failures from runner, network, disk, or dependency setup failures.
- If a job was rerun, make sure you are reading the latest attempt before summarizing.
