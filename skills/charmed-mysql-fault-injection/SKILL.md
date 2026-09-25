---
name: charmed-mysql-fault-injection
description: >
  Reproduce Charmed MySQL failures on a live deployment: simulate member
  death and quorum loss with the right kill primitive, force control-plane
  failures, test self-healing and recovery paths, and build deterministic
  reproductions of race-conditional bugs. Includes the failure-injection
  taxonomy (graceful vs abrupt member exit, StatefulSet/Pebble supervision),
  Group Replication quorum semantics, and model/experiment hygiene. Use when
  reproducing a reported bug, testing recovery behavior, simulating quorum
  loss or process death, verifying error-path logging, or a repro won't
  stick. Not for passive inspection of a misbehaving deployment (prefer
  juju-inspect) or log-only analysis (prefer log-autopsy).
license: Apache-2.0
metadata:
  author: canonical-data-platform
  version: "0.1.0"
  upstream-repo: canonical/mysql-operators
---

# Charmed MySQL fault injection

## Overview

Deliberately breaking a live Charmed MySQL deployment to reproduce bugs
and exercise recovery paths. The skill's core discipline: **state the
target cluster state first, then choose the primitive by the post-kill
dynamics** — the same intent ("kill mysqld") produces healthy,
degraded-quorate, or NO_QUORUM clusters depending on the technique.

Assumes familiarity with the inspection basics (containers, ports,
credentials, pebble) from the `charmed-mysql-juju-inspect` skill — read
its references if the environment is unfamiliar. Everything here needs
live access.

## The decision sequence

### 1. Name the target state precisely

Before touching anything, write down the state you need at the moment you
assert/fire. Common targets:

- **Control-plane failure** (charm cannot reach mysqld): connection
  refused on the admin port.
- **Member death with self-healing** (recovery-path verification): member
  down, cluster re-forms without it.
- **Genuine quorum loss (NO_QUORUM)**, stable: majority of members
  unreachable and staying down.
- **Degraded-but-quorate** (`OK_NO_TOLERANCE*`): single member surviving,
  view shrunk cleanly.
- **Application-visible failure**: e.g. relation setup partially done.

A "successful" injection that leaves the cluster in a different state than
targeted has taught you nothing — re-verify the state (via
`get-cluster-status` / `replication_group_members`) before concluding.

### 2. Choose the primitive (the taxonomy)

| Primitive | Member exit | Supervision response | Cluster outcome |
|---|---|---|---|
| `kubectl delete pod` (or `--grace-period=0 --force`) | pod gone | **StatefulSet recreates** (~1s), mysqld back in ~4s, quorum restored ~10–40s | Self-heals quorate — **not** member death |
| `pebble stop mysqld` | SIGTERM → **graceful GR leave** (shutdown path runs `group_replication` stop) | Service user-stopped, stays down | View shrinks cleanly → **healthy** `OK_NO_TOLERANCE` single-member group |
| `mysqladmin shutdown` / `systemctl stop` | process dies (graceful) | Pebble/systemd **auto-restart** | Self-healing; wrong for durable death |
| `pkill -x mysqld --signal SIGKILL` + `pebble stop mysqld` | **abrupt** (UNREACHABLE, no clean exit) | `pebble stop` suppresses the auto-restart; stays down | 2/3 unreachable, no majority → **stable NO_QUORUM** |
| `pkill -f mysqld` via `juju ssh` | — | **Kills its own wrapper shell** (exit 137); helper aborts before follow-up steps | Never use `-f` patterns through exec-with-shell |
| `pkill -f <pattern> --signal SIGSTOP` | frozen, alive | none | Member appears UNREACHABLE while stopped (replication-pause tests) |
| `STOP GROUP_REPLICATION` (SQL, needs `serverconfig`) | clean leave, mysqld alive | none | Member gone from group, unit looks active — ambiguous, use deliberately |

The unifying principles:

- **Graceful shutdown is not failure simulation.** SIGTERM lets mysqld
  execute an orderly Group Replication exit; the group reconfigures
  cleanly and stays healthy. If you need NO_QUORUM, the process must die
  abruptly and stay down.
- **Two-layer supervision = two recovery agents to defeat**: the K8s
  StatefulSet (recreates pods) and Pebble (restarts failed services).
  Durable death requires neutering both; `pebble stop` immediately after
  SIGKILL does (cancels the backoff restart, or SIGTERMs a not-yet-started
  replacement before GR loads).
- **Pick by desired dynamics, not habit**: `mysqladmin shutdown`'s
  self-healing is exactly right for testing error-path logging and exactly
  wrong for quorum-loss tests.
- No re-kill loops: if a single deterministic sequence doesn't hold, find
  out *why* (that's a bug to diagnose), don't mask it. Verify with
  `pgrep -x mysqld` (bounded poll, fail fast).

### 3. Group Replication guardrails

Load [gr-quorum-internals.md](references/gr-quorum-internals.md) for the
mechanics; the operational rules:

- **Majority loss is a designed deadlock**: no quorum → no expulsion → no
  view shrink. The cluster stays NO_QUORUM until either enough members
  come back *reachable* or an operator runs `promote-to-primary
  force=true` (`forceQuorumUsingPartitionOf`) on a survivor.
- **Force-quorum refusal is the contract**: mysqlsh refuses
  `forceQuorumUsingPartitionOf` on a quorate cluster
  ("The cluster has quorum according to instance ..." / "Cannot perform
  operation on an healthy cluster because it can only be used to restore a
  cluster from quorum loss"). If the action fails with this, your
  injection failed to produce NO_QUORUM — fix the injection, never paper
  over the guard in the charm.
- **Wrong knob warning**: `group_replication_member_expel_timeout` looks
  like the lever for keeping members UNREACHABLE, but expulsion is
  executed *by a quorate group* — in majority loss the knob is never
  consulted. Before reaching for any GR variable, read its manual entry
  (scope, default, dynamic?, **who acts on it and do they need quorum?**).
- **A failing read is a signal**: `get-cluster-status` failing on a
  survivor = NO_QUORUM from its view.
- Post-recovery behavior evolved: newer charms (8.4 with the safe
  auto-recover work) have a designed no-quorum→offline→reboot-from-outage
  path when all nodes become reachable again. Don't assume "pebble start
  is required" without checking the deployed charm's recovery code.

### 4. Control-plane and non-kill injections

For failures that are not member death:

- **Control-channel failure** (charm↔mysqld): shut down mysqld on **all**
  units in parallel via `mysqladmin shutdown` against port 33062
  (self-heals; right tool for error-path/log testing), then immediately
  trigger the action under test. Mind: the charm roams to
  `instance_address` — leaving any unit up may let the action succeed via
  it; and actions take seconds (mysqlsh timeouts), so don't declare
  "no logs" instantly.
- **K8s object deletion**: `kubectl delete svc <app>-primary <app>-replicas`
  makes endpoint DNS resolution fail deterministically (nothing recreates
  the Services until a charm restart) — reproduces relation-setup races
  without chasing the original trigger.
- **Marker-file fault injection**: hook processes are fresh each run but
  the filesystem persists — edit the *deployed* charm source
  (`/var/lib/juju/agents/unit-<app>-0/charm/src/...`) to raise once when a
  marker file exists; create/remove the file from outside. Precise,
  reversible, no race.
- **`update-status-hook-interval` as a dial**: `15s` makes status-masking
  visible quickly; a long interval (e.g. `30m`) freezes charm reactions so
  you can observe intermediate states. You cannot have both at once — pick
  per experiment and **restore afterwards**.

### 5. Deterministic reproduction discipline

- **Strip the incidental trigger.** Race-conditional originals ("CoreDNS
  was slow that morning") are unreproducible by design. Identify the
  *essence* ("any failure between user creation and relation-data commit")
  and force it deterministically (§4 techniques).
- **Never kill the observer or the observed mid-flight**: deleting a pod
  during a running action kills the charm process mid-retry — it logs
  nothing, and `kubectl logs` history is lost. Let actions/hooks run to
  completion; then break; then observe.
- **A/B experiments**: same model, two charms side by side (or sequential
  models) with an identical protocol; capture with
  `juju debug-log -i <unit> -n 0` (replay + follow) *and* periodic
  `juju status --format json` sampling. **Sampling lies** (a 2s operation
  falls between 10s samples); the uniter operation lifecycle in debug-log
  is ground truth — count them separately.
- Background captures from a tool harness: `setsid juju debug-log ... >
  f 2>&1 < /dev/null &` — the detached process survives; check the file.

### 6. Model and experiment hygiene

- **Sequential models per experiment** (`testing2`, `testing3`, ...).
  Failed-run models are forensic material — never `destroy-model` before
  the post-mortem.
- Reset recipe for a clean slate:
  `juju destroy-model <m> --destroy-storage --no-prompt --force` then
  `juju add-model <m>` (the k8s namespace must be gone first; retry if it
  lingers).
- Confirm the starred controller/model before deploying; multiple
  controllers are common (`juju controllers`).
- Deploying locally built charms: `--trust`, plus
  `--resource mysql-image=<upstream-source digest from metadata.yaml>`;
  storage name comes from `metadata.yaml` (`database`); one `name=size`
  per `--storage` flag. Verify the packed charm actually contains your
  change: `unzip -p <charm-file> <path> | grep <marker>`; check its mtime.
- Record credentials **fresh** after every redeploy (they rotate).

### 7. Report

For each experiment: target state → primitive used → observed state at
each checkpoint (with timestamps) → whether the recovery matched the
designed path → deviations. Preserve models/logs until the post-mortem is
done. See the log-autopsy skill for interpreting what you captured.

## Gotchas (dead ends — do not retry blind)

| Trap | Why it wastes time |
|---|---|
| `kubectl delete pod` as "quorum loss" | StatefulSet + GR reconnect: quorate again in ~10–40s |
| `pebble stop mysqld` for *quorum-loss* tests | Graceful SIGTERM → clean GR leave → healthy shrunken group → force-quorum refuses |
| `mysqladmin shutdown` for *durable* death | Pebble restarts the enabled service — self-healing |
| `pkill -f mysqld` via `juju ssh` | `-f` matches the wrapper shell's own cmdline → exit 137 (killed its own context); the target may still be dead — the error is about the wrapper |
| Reading exit 137 as "pkill failed" | 128+9 = the executed context was SIGKILLed; check `pgrep -x mysqld` for the real outcome |
| `SET GLOBAL max_connections=1` | Locks out every client incl. root/socket; only pod restart reliably unlocks; does not affect the charm (33062) anyway |
| `SET GLOBAL admin_address=...` | Read-only variable (`ERROR 1238`) |
| Moving `/var/run/mysqld/mysqlx.sock` | Charm connects via TCP, never socket, for cluster ops |
| iptables/tc/nft inside the workload container | Not available in the image; unnecessary — process-level primitives suffice |
| Waiting for natural failures on a degraded cluster | Degraded-but-reachable is not a hard failure; error-handling paths only fire on connection-refused/timeout |
| Reaching for `group_replication_member_expel_timeout` | Expulsion is quorum-gated; irrelevant in majority loss |
| Trusting session memory about the repo/model state | Branch/checkout/model contents move under you — re-verify (`git branch --show-current`, `juju status`) before hand-off notes |

## References

- [references/gr-quorum-internals.md](references/gr-quorum-internals.md) —
  step 3: GR view/expulsion/quorum mechanics and the knob-analysis pattern.
- [references/repro-recipes.md](references/repro-recipes.md) — steps 2–5:
  worked command sequences for the common experiments.
