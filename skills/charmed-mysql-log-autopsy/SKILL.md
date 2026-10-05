---
name: charmed-mysql-log-autopsy
description: >
  Diagnoses Charmed MySQL (mysql or mysql-k8s) failures to a root cause
  from evidence: juju debug-log output, Test Observer log bundles,
  juju crashdumps, pasted tracebacks, issue reports, or a reproduced
  failure. Fingerprints charm revisions, reconstructs hook/event
  timelines, and maps evidence to charm source code. Use when logs, a
  crashdump, a Test Observer execution, or a bare traceback needs
  explaining, or when a bug report or AI-triaged regression claim needs
  verification.
license: Apache-2.0
metadata:
  author: canonical-data-platform
  version: "0.3.0"
  upstream-repo: canonical/mysql-operators
---

# Charmed MySQL log autopsy

## Overview

Static diagnosis of Charmed MySQL problems from captured evidence only. The
output of this skill is a **root-cause analysis**: what failed, in which
component, why the observed statuses/log lines follow, and suggested fix
directions — with a confidence level. It never assumes the system is
reachable: every claim must be derivable from the artifacts plus source code.

Charmed MySQL context you must know up front (for monorepo layout and
reading charm source at a specific revision, see the
`mysql-operators-source` skill):

- Cluster health is Group Replication (single-primary InnoDB Cluster,
  optionally ClusterSet for async replication). Charm statuses are
  *opinions* derived on `update-status`; they lag and can mask reality.
- Charm errors and statuses are raised from a small, greppable surface:
  grep the exact message string in the repo to find the emitting class, the
  unit tests asserting it, and the statuses doc (`docs/reference/charm-statuses.md`).

## Workflow

Work through these steps in order; each one narrows the hypothesis space.
Load reference files only when the step calls for them (paths in
[References](#references)).

### 1. Fingerprint the deployment

Extract from the artifacts, before any theorizing:

- **Charm revisions** per app (`juju-status.txt`, issue text, TO execution
  metadata), and the **channel/branch** they imply (8.0/stable, 8.4/edge, ...).
- **Juju version, Kubernetes client/server versions, MySQL version** (the
  `get-cluster-status` payload embeds member `version`; k8s versions are in
  `kubernetes-version.txt`; ops version appears in logs as
  `ops <X> up and running.` — one line per hook process).
- **The coverage window** of the capture: first and last timestamp of every
  log file. An event "absent" from a log that starts *after* the incident
  proves nothing. Bundles are truncated ring buffers — always check coverage
  before claiming absence of evidence.
- For CI evidence: Test Observer execution metadata carries
  `charm_qa:juju:version` and an environment name encoding channel + base.

### 2. Identify the topology from the artifacts

Determine which applications existed, how they were related, and
**whether a router is in the path** — many "database" symptoms are actually
router symptoms, and vice versa:

- From `juju-status.yaml` / `db-dump.yaml`: list apps and their charms;
  look for an app running the `mysql-router` charm related via
  `backend-database` (consumes MySQL's `database` endpoint) and, in turn,
  providing a `database` endpoint to client apps. Chains
  (`mysql-k8s → router → router → app`) are legal and known-buggy territory.
- From logs: `mysqlrouter`/`charmed_router` role or user mentions,
  `backend-database` relation log lines, router status messages.
- Note which app set which status: application-level vs unit-level statuses
  are set by different code paths (see [Hook forensics](references/hook-forensics.md)).

### 3. Map the evidence to its sources

Know what each file can and cannot prove. Load
[bundle-anatomy.md](references/bundle-anatomy.md) for the full file map,
grep cookbook, and `db-dump.yaml` parsing guidance. Quick orientation:

| Evidence | Proves | Cannot prove |
|---|---|---|
| `pod/<unit>.log` | charm hook execution, juju-log lines, full tracebacks | workload-side (mysqld) internals |
| `debug-log.txt` | uniter operations, hook lifecycle, controller view | (often truncated — check window) |
| `status-log/*.yaml` | exact status/message transition timestamps | *why* a status was set |
| `db-dump.yaml` | relation databags, secret metadata, permissions | charm-side timing |
| `juju-status.txt` | final state snapshot | history |
| workload `error.log` | mysqld/GR server-side truth | charm behavior |

### 4. Reconstruct the failure

Load [hook-forensics.md](references/hook-forensics.md), then:

- Group log lines by **hook-context UUID** to reconstruct single hook
  invocations; a Juju retry of a failed hook carries a different UUID.
- Read tracebacks by **frame shape**: which lines belong to the charm vs
  `ops/model.py` vs site-packages. A `KeyError` at a charm line with *no
  ops frame* underneath means a plain-dict operation — frequently the
  `{}` fallback returned when the peer relation no longer exists.
- Correlate hook timestamps (teardown ordering matters: once
  `database-peers-relation-broken` completes, every later hook sees
  `peers = None`).
- Count `Deferring ...` vs `Re-emitting deferred event ...` lines; a
  deferral with no final re-emission — or a handler that returned without
  deferring — means a lost state transition (classic cause of stale app
  statuses).
- If the failure is about agent busyness/idle timeouts, parse the uniter
  operation lifecycle with `scripts/parse_uniter_ops.py`.

### 5. Judge the report you were handed

- Issue bodies and AI-generated triages are **leads, not facts**. Verify
  every causal claim ("this is a regression in rev X", "the hook never
  ran") cheaply before building on it — revision A/B comparisons and git
  archaeology have repeatedly refuted such premises.
- Pasted log excerpts can mix hook contexts or truncate tracebacks.
  Re-derive from the full bundle whenever one exists.
- Distinguish expected noise from symptoms: e.g. a charm related to
  `data-integrator` blocks with "Please specify either topic, index,
  database name, or prefix" until configured — that is by design.

### 6. Verify against source

Load [version-archaeology.md](references/version-archaeology.md) from the
`mysql-operators-source` skill, then:

- Read the code **of the branch/revision that was deployed**, not your
  checkout: `git show origin/8.0/edge:<path>` / `git show <charm>/revNNN:<path>`.
  Charmhub revisions map to git tags in the monorepo.
- Anchor deployed tracebacks by **line content, not number** — line numbers
  drift between the deployed revision and current branches.
- If a log line has no hit in the charm repo, search dependency code under
  the charm's venv/site-packages (e.g. `mysql_shell` library ERROR strings).
- Apply the design-intent check: before calling a frozen status, a refusal,
  or a blocked state a bug, enumerate every setter of that status and find
  the update-status suppression path. Several blocked/waiting states are
  contractual (action-gated interfaces, quorum-loss guards).

### 7. Verdict

Produce a structured conclusion:

1. **Symptom signature** — the observable failure, one paragraph.
2. **Root cause** — mechanism, with the evidence chain (log line → code
   line). Separate *trigger* (often transient/incidental) from *defects*
   (what turned a transient event into a permanent or visible failure).
3. **Confidence** — verified (reproduced or bit-identical mechanism),
   likely, or hypothesis. State what evidence would settle it.
4. **Fix directions** — options with trade-offs; idempotency and
   self-healing considerations. This skill stops here; it does not write
   the fix.
5. **What to collect next** if confidence is low (specific greps, actions
   to run on the live system, fields missing from the bundle). Gather
   live evidence with the `charmed-mysql-juju-inspect` skill; test the
   hypothesis by injecting faults with the `charmed-mysql-fault-injection`
   skill.

For classification of common signatures, load
[failure-taxonomy.md](references/failure-taxonomy.md) — tables of
signature → likely cause → how to confirm, distilled from real cases.

## Gotchas

- **MySQL state is external to Juju rollback.** A failed hook rolls back
  databag writes and Juju secrets created during the hook, but nothing
  already executed inside MySQL. "MySQL write succeeds → hook fails later"
  produces poisoned-retry states (error 1396 on retry, committed
  wrong-password secrets). A handler that fails *cleanly* (caught error,
  exit 0) commits the data-interfaces diff snapshot and permanently
  disarms the retry mechanism.
- **Databag deletion == setting the key to `""`** (Juju semantics, mirrored
  by ops). `del databag[key]` never raises on a real databag — it only
  crashes on the plain-`{}` fallback taken when `peers` is `None`.
- **App vs unit status asymmetry**: app status is rebuilt only by the
  leader in specific handlers; unit status can be overwritten by unrelated
  paths (cluster creation, crash recovery). App `maintenance` + unit
  `active` = stale app status from a lost event, not a second broken unit.
- **update-status overwrites**: unit statuses derived purely from
  peer-databag `member-state`/`member-role` clobber any blocked status set
  by other handlers within one update-status interval. A blocked status
  that "healed itself" after ~40s–5min was masked, not fixed.
- **`get-cluster-status` failing is a signal, not noise**: mysqlsh
  `cluster.status()` requires quorum; from a minority survivor the action
  fails with "Failed to read cluster status" — that failure *means*
  NO_QUORUM from that unit's perspective.
- **mysqlsh refusals are contracts**: "Cannot perform operation on an
  healthy cluster because it can only be used to restore a cluster from
  quorum loss" is Group Replication's safety guard, not a bug.
- **8.0 vs 8.4 divergence**: the same lib file ships on both branches with
  diverging refactors and renamed databag keys. Grep the branch that
  matches the deployed revision. The `kubernetes/` and `machines/` copies
  of shared libs are kept byte-identical — a fix must usually touch both.
- **Consecutive Charmhub revision numbers are often arch/channel pairs**,
  not feature revisions (e.g. 747=arm64, 748=amd64 of the same code).

## References

Load on demand (all paths relative to this skill):

- [references/bundle-anatomy.md](references/bundle-anatomy.md) — step 3:
  file map of Test Observer bundles and crashdumps, grep cookbook,
  `db-dump.yaml` and `status-log` parsing.
- [references/hook-forensics.md](references/hook-forensics.md) — step 4:
  hook-context reconstruction, traceback frame analysis, retry/teardown
  semantics, deferred-event and uniter-operation analysis.
- `mysql-operators-source` skill — step 6: revision↔tag mapping, source
  reading at a deployed revision, branch selection, ops-version pinning
  (its `references/version-archaeology.md`).
- [references/failure-taxonomy.md](references/failure-taxonomy.md) —
  step 7: signature → cause → confirmation tables.
- `scripts/parse_uniter_ops.py` — step 4: measure uniter operation
  durations/gaps from `debug-log.txt` (`--help` for usage).
