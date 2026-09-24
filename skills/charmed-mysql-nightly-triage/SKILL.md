---
name: charmed-mysql-nightly-triage
description: >
  Triage failed CI runs for Charmed MySQL: nightly test runs, PR integration
  failures, Test Observer artefacts and executions. Classifies each failure
  as deterministic bug, flake, infrastructure failure, or test-plan bug,
  extracts evidence from logs bundles and the Test Observer API, detects
  recurring problems across runs, and produces a structured summary with
  basic analysis. Use when the user mentions nightly runs, failing CI,
  Test Observer executions/artefacts, charm QA results, "is this PR failure
  real", or asks for a summary of test results. Not for reading raw logs of
  a single incident without CI context (prefer log-autopsy) or for live
  debugging of a deployment.
license: Apache-2.0
metadata:
  author: canonical-data-platform
  version: "0.1.0"
  upstream-repo: canonical/mysql-operators
---

# Charmed MySQL nightly/CI triage

## Overview

Turns failed CI evidence into decisions: which failures are real charm bugs,
which are flakes or infra, which are test-plan bugs, and which PRs are
innocent. The workflow is API-heavy (Test Observer, GitHub Actions) but the
classification step reuses the log-forensics mindset of the
`charmed-mysql-log-autopsy` skill — load that skill's
`references/failure-taxonomy.md` when classifying signatures.

Ground rules:

- **GitHub job `conclusion` lies.** A charm-integration-testing job can
  exit `success` while pytest failed (exit code 1 does not fail the job);
  real results flow only through Test Observer. Never summarize from
  GitHub conclusions alone.
- **Issue/PR triage text (often AI-generated) is a lead, not evidence.**
- Every classification below comes with the evidence that distinguishes it;
  never classify without it.

## Workflow

### 1. Collect the runs

```bash
# List nightly runs (adapt repo/branch/workflow)
gh run list --repo canonical/mysql-operators --workflow=nightly.yaml \
  --branch=8.0/edge --limit=30 --json databaseId,createdAt,conclusion

# Jobs for a run (note: gh run view --log is empty for some repos)
gh api repos/canonical/mysql-operators/actions/runs/<id>/jobs --paginate \
  --jq '.jobs[] | "\(.databaseId) \(.name) \(.conclusion)"'

# Job log (ghad needs full URLs; bare IDs crash in current versions)
ghad job fetch "https://github.com/<org>/<repo>/actions/runs/<run>/job/<job>"
# or: gh api repos/<org>/<repo>/actions/jobs/<job_id>/logs > job.txt
# or run-logs zip: gh api repos/<org>/<repo>/actions/runs/<run>/logs > run.zip

# Re-run only failed jobs when a retry is warranted
gh run rerun <run_id> --repo canonical/mysql-operators --failed
```

For Test Observer artefacts/executions, load
[test-observer-api.md](references/test-observer-api.md). Key shortcuts:
the API host is `https://test-observer-api.canonical.com` (the frontend
host 503s and returns HTML — red herrings); execution metadata carries the
failure message, charm/juju versions and channel/base; `relevant_links`
points to the logs bundle and `ci_link` to the GitHub run;
`previous_results` gives cross-revision history.

### 2. Extract the failure signal

From the job log (or `io_log` in Test Observer test results):

- The failing test name(s) and the error type:
  - `JujuWaitTimeoutError: Timed out while waiting for ...` — note the
    apps/units lists (asymmetry between them is diagnostic).
  - Hook failures (`hook failed: "<hook>"`), tracebacks, MySQL error codes.
  - Setup-phase errors (concierge, snap, microk8s) with **no pytest
    output** — infra flake signature.
- The execution metadata fields: `charm_qa:failure:charm:<app>:status`
  often names the failing hook/unit status before any log is opened.
- Environment fingerprint: juju version, charm revision(s), channel+base
  (encoded in the execution name), k8s versions. Different environment ⇒
  not comparable to other runs.

### 3. Classify (with evidence)

Classify each failure into exactly one bucket:

| Bucket | Distinguishing evidence |
|---|---|
| **Deterministic charm bug** | Same traceback/signature on every retry and every run; reproducible locally or by reading code; hook `error` state with identical tracebacks |
| **Flake / timing** | Fails intermittently across runs/revisions; passes on retry; timing-sensitive thresholds (30s waits vs 41s slow-hardware startup); agent-idle oscillation |
| **Infra failure** | No pytest output; failure during concierge/snap/microk8s setup; runner noise ("The node is not part of a Kubernetes cluster", Pebble socket not found after container restart) |
| **Test-plan bug** | The plan cannot pass by construction — e.g. deploy-and-wait harness (`idle_for_period`) against an action-gated interface, or a required operator action never in the spec |
| **PR-unrelated red check** | Label/lint policy failures ("Check pull request" label errors), or failures in tests with zero textual overlap with the diff |

For signature-level classification (KeyError shapes, status freezes,
NO_QUORUM signals, poisoned retries), load the log-autopsy skill's
`references/failure-taxonomy.md`.

### 4. Extract deeper evidence when the bucket is unclear

- Download the logs bundle (`relevant_links[].url` →
  `juju-controller-*.tar.gz`) and extract: `pod/<unit>.log`,
  `debug-log.txt`, `status-log/*.yaml`, `juju-status.txt`, `db-dump.yaml`.
  See the log-autopsy skill's bundle-anatomy reference for the file map
  and grep cookbook.
- Check `previous_results` (Test Observer) for cross-revision history:
  which revisions passed/failed before? A failure appearing at exactly one
  revision with clean neighbors is a regression candidate; the same
  signature across many revisions is structural or environmental.
- For PR exoneration, apply the checklist:
  1. Directly affected tests (same feature/integration file as the diff)
     all passed.
  2. Zero textual overlap between failing tests and the changed code
     (`grep` test files for changed symbols/strings).
  3. Failures are timeouts, infra noise, or policy checks.
  For a status-string-only change, (1)+(2)+(3) is sufficient to call the
  PR innocent.

### 5. Summarize

Produce a report using the template in
[report-format.md](references/report-format.md):

- One line per failure: test, environment, classification, confidence,
  evidence pointer (execution ID / job ID / log line).
- A cross-run section: recurring signatures and their stability across
  runs/revisions.
- Recommended next actions per failure (file issue with which evidence,
  retry, ignore, fix test plan, fix charm).

## Gotchas

- **Token/env prerequisites**: `TO_TOKEN` for Test Observer; `npx` needs
  the nvm PATH (`export PATH="$HOME/.local/share/nvm/v24.13.0/bin:$PATH"`);
  occasional 503s — retry or fall back to plain `curl` with the bearer
  token for GETs.
- **CI timing is not local timing**: operations take 9–72s on CI rigs vs
  2–5s locally. A test that passes locally at a threshold can be
  structurally unable to pass on the rig.
- **Sequential nightly runs on the same artefact**: compare within the
  same channel/base/revision set; promotion runs change the artefact under
  test mid-history.
- **Charm revisions in bundles are often mixed** (a model left deployed
  from a previous experiment) — verify each app's revision in
  `juju-status` before attributing a failure to a revision.
- `gh run view <id> --log` returns empty for some repos — use the jobs
  API, the run-logs zip, or ghad with full URLs.
- CIT `test_deploy` does `deploy_bundles` → `idle_for_period(timeout)` →
  `validate_model`; `idle_for_period` requires *all* applications active,
  *all* units active, *all* unit agents idle. Any charm with periodic
  out-of-band dispatches (Charmed MySQL rotates logs every 60s and
  self-heals every 120s) can structurally fail this even when healthy —
  classify as test-plan/harness mismatch, not a charm bug, after confirming
  the dispatch cadence in the debug-log.

## References

- [references/test-observer-api.md](references/test-observer-api.md) —
  step 1/2: API invocation patterns, endpoints, metadata fields.
- [references/cit-harness.md](references/cit-harness.md) — step 3/4:
  charm-integration-testing internals and wait-condition semantics.
- [references/report-format.md](references/report-format.md) — step 5:
  nightly summary and PR-triage report templates.
- The `charmed-mysql-log-autopsy` skill's
  `references/failure-taxonomy.md` — step 3: signature classification.
