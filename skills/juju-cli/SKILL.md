---
name: juju-cli
description: >
  Operational reference for driving the Juju CLI correctly against Charmed
  MySQL (k8s and machines deployments): deploy with trust, destroy broken
  models, run commands in the right unit container, charm actions vs shell
  commands, reading status correctly, and model hygiene. Use when running
  or debugging juju commands — especially juju deploy/destroy-model, juju
  ssh/exec into mysql-k8s units, charm actions whose client-side wait times
  out, units wedged in error with 403/Forbidden right after deploy,
  unexpected exit 137 from a kill command, confusion about which
  controller/model is being inspected, or background status-sampler loops
  left behind by an earlier session. Covers k8s-specific flags (--trust,
  --container) and pebble supervision. Not for MySQL/Group Replication
  semantics (use charmed-mysql-juju-inspect / charmed-mysql-fault-injection)
  or log analysis (charmed-mysql-log-autopsy).
license: Apache-2.0
metadata:
  author: canonical-data-platform
  version: "0.1.0"
  upstream-repo: canonical/mysql-operators
---

# Juju CLI gotchas for Charmed MySQL operations

## Overview

The Juju CLI has several traps that silently produce the wrong outcome: a
deploy that never converges (trust race), a destroy that hangs, a kill
command that kills its own wrapper shell (exit 137), an action that looks
timed out but succeeded, and an inspection of the wrong controller. This
skill lists the working pattern for each. All commands assume k8s
(mysql-k8s) unless noted; machines-model differences are flagged inline.

## Deploy: trust at deploy time, never after

- Deploy with trust up front: `juju deploy mysql-k8s --channel 8.0/stable
  -n 3 -m <model> --trust`. `--trust` grants cluster-scoped RBAC (k8s).
- Do NOT plan to `juju trust <app> --scope=cluster` afterwards: it races
  the charm's first hooks, which already call `nodes get`; the loser gets
  **403 Forbidden** and the unit can wedge in error permanently.
- Symptom: units erroring with RBAC/Forbidden messages immediately after
  deploy = trust race lost. Fix by redeploying with `--trust`, not retries.

## Destroying models

- Plain `juju destroy-model <name>` hangs on broken or half-provisioned
  models. Use: `juju destroy-model <name> --destroy-storage --no-prompt
  --force` (~1–2 min for a 3-unit k8s model).
- `--destroy-storage` deletes PVCs — **all data in the model is lost**.
- Reconciling a stale scratch model from a crashed run: run the force-destroy
  first, unconditionally — it is a no-op if the model no longer exists.

## Running commands in units

- `juju ssh <unit>` lands in the **charm** container. The workload (mysqld,
  pebble, mysql client) is in the `mysql` container:
  `juju ssh -m $M --container mysql mysql-k8s/0 "..."`.
- Never use `pkill -f <pattern>` through any exec-with-shell channel (juju
  ssh, kubectl exec): the pattern matches the wrapper shell, which SIGKILLs
  its own exec context — exit **137** before doing what you asked. Use
  exact-name matches: `pkill -x mysqld --signal SIGKILL`.
- k8s units have no systemd: services run under **pebble**
  (`pebble services|stop|start <svc>`), and above pebble the k8s
  StatefulSet recreates deleted pods. Durable process death means defeating
  both layers. On machines models it is systemd instead — check which.
- Alternate channel when juju transport is flaky: `kubectl exec` into the
  pod (name `mysql-k8s-<n>`, in the model's namespace).

## Actions vs shell commands

- Discover what a charm can do with `juju actions <app-name> [--format
  json]` — it lists the application's supported actions with their params
  (e.g. `juju actions mysql-k8s` → `get-password`, `get-cluster-status`,
  `create-backup`, ...). `juju actions` with no app lists for the current
  model's apps.
- `juju run <unit> <action> [params]` runs a **charm action** only.
  There is no `get-credentials` action on mysql-k8s — consumers get
  credentials via the `database` relation; on-unit access uses
  `get-password` (supports `username=serverconfig` for the non-root admin).
- `juju run` waits **60s client-side by default**. A client timeout does NOT
  mean the action failed — fetch the result with `juju operations` /
  `juju show-task` (long actions routinely finish after 60s).
- Arbitrary shell in a unit: `juju ssh` (interactive) or `juju exec`
  (non-interactive). `juju scp` for file transfer (finicky — verify exit).

## Reading status

- Read the three columns separately: app status, unit workload-status, unit
  agent-status. Workload `active` + agent not idle = still converging. The
  unit `message` carries the primary marker for mysql-k8s.
- Use `--format json` (units map keyed `app/0`, ...). Readiness for a 3-unit
  cluster = 3 units with workload `active` AND agent `idle`; poll for that,
  never fixed sleeps.
- `juju debug-log` essentials: `-m $M --level DEBUG --include
  unit-mysql-k8s-0 --replay --ms`.
- juju status healthy ≠ Group Replication healthy: verify with the
  `get-cluster-status` action (leader unit) or `replication_group_members`
  SQL on the admin port 33062 as `serverconfig`.
- App status `blocked` can be normal (e.g. an app waiting for a required
  relation). Check the message before treating it as an incident.

## Model hygiene and the right model

- Every scratch model you create must be destroyed by you before finishing.
  Leftover experiment models accumulate real cost (each mysqld ≈ 2GiB RAM).
- `JUJU_MODEL` env var sets the default model for all juju commands;
  `juju switch` changes it persistently; explicit `-m <model>` beats both.
  Always pass `-m` in scripts.
- Multiple controllers exist on this box (k8s and VM). If observations look
  wrong, run `juju controllers` and `juju models` before trusting anything.
- Bound any background sampling loop (timeout, max iterations) and `wait`
  for it in the same script — daemonized `while true; do ...; juju status;
  sleep 5; done` loops outlive sessions and add constant CPU/controller
  churn. They also survive process-group kills when launched via `setsid` —
  see `references/cleanup-and-controller.md` for the sweep patterns.

## Do not

- Do not deploy k8s charms without `--trust`, or trust them post-deploy.
- Do not use `pkill -f` / broad `grep` patterns inside exec-with-shell
  channels (`juju ssh`, `kubectl exec`) — they match the wrapper and exit 137.
- Do not treat a `juju run` client-side timeout as action failure.
- Do not assume juju status reflects Group Replication health.
- Do not destroy a model without `--destroy-storage --no-prompt --force`
  when it is broken, and never destroy without confirming you can lose the
  data.
- Do not leave scratch models or background sampler loops behind.
- Do not debug a sick controller piecemeal — re-create the model (see
  reference file below) and re-baseline.

## References

- `references/cleanup-and-controller.md` — orphaned-process sweeps, AppArmor
  SIGKILL limits and the cgroup-kill workaround, host-saturation symptoms,
  and the rebuild-the-model playbook.
