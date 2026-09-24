# CIT harness internals — charm-integration-testing

Reference for `charmed-mysql-nightly-triage` steps 3–4. The
`canonical/charm-integration-testing` (CIT) harness defines the wait
semantics that most Charmed MySQL CI failures hinge on.

## The wait condition: `idle_for_period`

`test_deploy` (in CIT's `test_suite/test_deploy.py`) does exactly:

1. `deploy_bundles`
2. `idle_for_period(timeout=15min)`
3. `validate_model(level="deep")`

`idle_for_period` requires **all** of, sampled periodically:

- all applications `active`
- all units `active`
- **all unit agents `idle`**

The strict variant (in CIT's `juju/client.py`) defaults to `count=10`
*consecutive* compliant samples; a single noncompliant sample **resets the
counter to zero** (`juju_jubilant/backend.py`).

Consequences:

- A unit whose agent oscillates `idle` → `executing` every 1–3 minutes can
  never accumulate 10 consecutive idle samples — guaranteed timeout even
  though the workload is healthy. Charmed MySQL dispatches
  `rotate_mysql_logs` (~60s) and `heal_mysql_cluster` (~120s) out-of-band,
  so long operations (slow rigs) structurally break this wait.
- The repo's own CI (jubilant-based) is looser: `Juju.wait` needs only ~3
  consecutive successful polls. That is why the same code passes repo CI
  and fails CIT.

## Action-gated interfaces cannot pass `test_deploy`

CIT's spec format (`docs/reference/spec-file.rst`) has **no concept of
charm actions** — models, applications, integrations, constraints only.
Any interface whose active state requires an operator action (e.g.
`mysql_async` replication needs `juju run <offer-unit> create-replication`
before it leaves `blocked "Ready to create replication"`) fails
`test_deploy` deterministically, on every run, with:

- offer side `blocked: Ready to create replication`
- consumer app `maintenance: Setting up replication` (or the post-fix
  "Waiting for create-replication..." message)

Confirm by grepping the full job log for the action name — zero hits means
the harness never ran it. CIT's own docs (`docs/explanation/wait-conditions.rst`)
describe `wait_application_settled` which accepts `active` **or**
`blocked` — the right tool for such interfaces — but `test_deploy` uses
the strict wait.

## Failure reporting quirks

- After a `test_deploy` timeout, the scheduler marks the environment state
  unknown and **skips all remaining state-marked tests**; the pytest exit
  code 1 does **not** fail the GitHub job (`conclusion: success`). Real
  results flow only through Test Observer.
- `gh run view <id> --log` returns empty for this repo — use the jobs API
  (`gh api repos/canonical/charm-integration-testing/actions/runs/<id>/jobs`)
  or the run-logs zip.
- `ghad` (current version) requires **full URLs** for job fetch; bare IDs
  crash.
- `npx` needs the nvm PATH: `export PATH="$HOME/.local/share/nvm/v24.13.0/bin:$PATH"`.

## Reading a CIT bundle

The logs bundle (from Test Observer `relevant_links`) is a juju-crashdump:

- `debug-log.txt` — uniter view (truncated ring buffer; check coverage).
- `pod/<unit>.log` — charm hook logs.
- `status-log/*.yaml` — timestamped status transitions (the gold for
  wait-timeout analysis: shows exactly when each status was set and by
  which message).
- `juju-status.txt` — final snapshot.

For bundle internals and grep cookbook, see the log-autopsy skill's
`references/bundle-anatomy.md`.

## Wait-condition fingerprints in `JujuWaitTimeoutError`

The error message lists noncompliant apps and units separately:

```
JujuWaitTimeoutError: Timed out while waiting for applications:
[active], units: [active], unit agents: [idle]
(applications: ['neighbor', 'target'], units: ['target/0'])
```

- `applications` lists ⊃ `units` lists → app-level status failures while
  units are fine (stale/lost app-status transitions).
- All agents in the units list with workload `active` → agent-busyness
  problem (scheduled dispatches), not a workload failure.
- Both lists large → genuine deployment failure; go to `pod/*.log`.
