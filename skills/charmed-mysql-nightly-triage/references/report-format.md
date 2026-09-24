# Report format — nightly summaries and PR triage

Reference for `charmed-mysql-nightly-triage` step 5.

## Nightly run summary

```markdown
# Nightly triage — <repo> <branch> — <date range>

## Runs covered
| Artefact | Executions | Revisions | Result |
|---|---|---|---|
| mysql-k8s 8.0/candidate r423 | 443474, 443546 | 423 | 3 failed / 12 passed |

## Failures
| # | Test | Environment | Classification | Confidence | Evidence |
|---|---|---|---|---|---|
| 1 | test_scale_in_and_scale_out | 3/stable ubuntu 22.04 k8s, r400, juju 3.6.20 | Deterministic charm bug | High | Exec 443474; KeyError traceback, identical across 5 runs |
| 2 | test_deploy (async replication) | same | Test-plan bug | High | Exec 659755; `create-replication` never run (0 grep hits) |
| 3 | test_upgrade arm64 | ... | Infra | Medium | No pytest output; concierge containerd restart failure |

## Recurring problems
- test_deploy agent-idle timeouts: 7/10 runs on r426 (all arches with
  dispatch cadence ≥ op duration). Structural; needs harness change or
  charm-side scheduling fix.

## Recommended actions
- #1: file/track issue (mechanism: peers-teardown `{}` fallback); backport check 8.4.
- #2: escalate test-plan gap to testing platform (actions unsupported in spec).
- #3: retry; file runner issue if pattern persists.
```

## PR triage report

```markdown
# PR #<n> — "<title>" — CI triage

## Verdict: <unrelated failures | real regression | policy-only>

## Directly affected tests
<list from the diff's feature area> — <pass/fail per arch/channel>

## Failing checks
| Check | Failure | Classification |
|---|---|---|
| integration (machines, arm64) | `wait timed out after 1200s` in unrelated test X | Flake/timeout — zero overlap with diff |
| Check pull request | `ValueError: Pull request must have 'bug'...` label | Policy, not code |

## Exoneration checklist
- [x] Affected tests pass (both arches, both channels)
- [x] Zero textual overlap: `grep -rE '<changed symbols>' tests/` → no matches
- [x] Failures are timeouts/infra/policy

## Notes
- Diff touches only status strings; unit tests assert types only.
```

## Field conventions

- **Classification**: deterministic-bug | flake | infra | test-plan-bug |
  policy-only. Always pair with **confidence** (high/medium/low) and the
  evidence that would change it.
- **Evidence pointers**: execution IDs (Test Observer), job IDs (GitHub),
  file+line in bundles. Every row must be traceable.
- **Recurring problems**: quantify (n/m runs, revisions affected). A
  signature failing >50% of runs on one artefact across ≥2 revisions is
  structural; across one revision only, suspect the revision.
- **Cross-revision history** (from `previous_results`): include when it
  discriminates (regression-candidate vs structural).
