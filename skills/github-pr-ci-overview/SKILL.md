---
name: github-pr-ci-overview
description: Query the GitHub Actions status of a pull request, correlate check runs to workflow runs and jobs, and summarize what is passing, failing, pending, or skipped. Use when a user asks for the CI status of a PR, wants to know which jobs ran, or provides a PR number, branch, or URL for CI investigation.
compatibility: Requires GitHub pull request and Actions access. Best with tools that can read PR metadata, check runs, workflow runs, workflow jobs, and workflow definitions.
---

# GitHub PR CI overview

Use this skill to turn a pull request into a reliable CI summary.

## Inputs

- Repository owner and name
- Pull request number, URL, or branch name

If the task is in this repository and the user does not specify a repo, default to `canonical/mysql-operators`.

## Workflow

1. Resolve the pull request first.
   - Read the PR metadata to get the head branch, head SHA, base branch, and current state.
2. Get the current checks for the PR head commit.
   - Use the PR check-run view as the fastest way to see the latest pass/fail/pending state.
3. List workflow runs for the PR branch.
   - Filter for `pull_request` runs when possible.
   - Match runs by PR number, head SHA, or both.
   - Prefer the highest `run_attempt` for each workflow run number.
4. For each relevant workflow run, list the jobs.
   - Keep the workflow run id, job id, job name, conclusion, timestamps, and HTML URL.
5. Correlate check runs to workflow jobs.
   - Match on job URL first.
   - Fall back to job name when needed.
6. Return a concise report.
   - Overall PR CI status
   - Workflow runs grouped by workflow
   - Failed jobs
   - Pending or queued jobs
   - Canceled or skipped jobs
   - Useful links

## Output shape

Prefer a summary like:

- PR: number, title, head SHA
- Overall: passing, failing, pending, or mixed
- Workflow runs:
  - workflow name / run id / attempt / conclusion
  - failed jobs
  - pending jobs
- Notes:
  - reruns present
  - no workflow triggered
  - checks missing for this commit

## mysql-operators routing notes

- Read `references/mysql-operators-workflows.md` when you need repository-specific workflow meaning.
- In this repository, `.github/workflows/ci.yaml` ignores `docs/**`, markdown-only changes, and `.github/renovate.json5`.
- A PR can therefore show only the pull-request policy workflow, or no main PR CI workflow at all, for docs-only changes.
- Integration checks fan out into many matrix jobs, so summarize by workflow first and then by failing job names.

## Edge cases

- If the user gives only a branch, find the PR for that branch before inspecting CI.
- If multiple workflow attempts exist, use the latest attempt and mention earlier attempts only if they change the conclusion.
- If a run is still in progress, report which jobs are queued, pending, or running.
- If checks exist without a matching workflow run, report them anyway; the check-run view is still authoritative for the current head SHA.
