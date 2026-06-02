---
name: github-pr-ci-artifact-inspection
description: Inspect GitHub Actions artifacts and log bundles for a pull request workflow run, especially for failed integration jobs. Use when a user asks for artifacts, uploaded logs, coverage outputs, or other downloadable CI evidence tied to a PR.
compatibility: Requires GitHub Actions access. Best with tools that can list workflow run artifacts, retrieve workflow run details, and fetch job log URLs or artifact downloads.
---

# GitHub PR CI artifact inspection

Use this skill when the user needs evidence beyond the job summary.

## Workflow

1. Resolve the PR and identify the relevant workflow run ids.
2. List workflow run artifacts for the selected run.
3. Summarize what the run uploaded.
   - artifact name
   - size
   - expired or available
4. If the user needs a specific artifact, identify the exact artifact id to download.
5. If the user needs raw logs, use the workflow run log URL or job-specific logs.
6. Report the artifact naming pattern so the user can tell which test or path it belongs to.

## mysql-operators routing notes

- Read `references/mysql-operators-artifacts.md` when working in `canonical/mysql-operators`.
- Integration runs can upload per-job log bundles and Allure results.
- Build runs may also expose packaged charm artifacts through the reusable build workflow.

## Output shape

Prefer:

- workflow run id and name
- available artifacts
- missing or expired artifacts
- exact artifact names tied to failing jobs
- next evidence source if the artifact is not enough

## Guardrails

- Do not claim an artifact exists until the workflow run artifact listing confirms it.
- If artifacts are missing, say whether the workflow never uploaded them or whether they may have expired.
