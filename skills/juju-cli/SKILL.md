---
name: juju-cli
description: >
  Operates the Juju CLI correctly against Charmed MySQL (k8s and machines)
  deployments: deploys with trust, destroys broken models, runs commands in
  the right unit container, distinguishes charm actions from shell
  commands, reads juju status and debug-log, drives pebble services, and
  manages models. Use when running or debugging juju or pebble commands —
  deploys, scales, destroys, ssh/exec into units, charm actions, status
  checks, or background sampling loops.
license: Apache-2.0
metadata:
  author: canonical-data-platform
  version: "0.9.0"
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

## Reading juju status

- Call pattern: `juju status -m <model>` for the human view, `juju status
  -m <model> --format json` for parsing.
- Read the three columns separately: app status, unit workload-status,
  unit agent-status. Workload `active` + agent not idle = still
  converging.
- JSON keying: the units map is keyed `app/0`, ...; agent status lives at
  `applications.<app>.units.<unit>.juju-status.current` (**not**
  `agent-status`); workload status at `workload-status.current`.
  Full annotated JSON example and parsing traps (nested `units`, scoped
  queries, self-relations, storage): see `references/status-json-shape.md`.
- Agent-state semantics: agent `executing` continuously while the
  workload is `active` usually means scheduled out-of-band dispatches
  (update-status & co) — healthy workload, busy agent, not a hang.
- The unit `message` is free text set by whichever hook last ran — not
  structured data.
- Statuses lag reality by up to the update-status interval (default 5m;
  dial it with `juju model-config update-status-hook-interval`).
  Readiness for a 3-unit cluster = 3 units with workload `active` AND
  agent `idle`; poll for that, never fixed sleeps.
- juju status healthy ≠ Group Replication healthy: verify with the
  `get-cluster-status` action or `replication_group_members` SQL on the
  admin port 33062 as `serverconfig` (interpretation in the
  `charmed-mysql-juju-inspect` skill).
- App status `blocked` can be normal (e.g. an app waiting for a required
  relation). Check the message before treating it as an incident.
- `juju debug-log` essentials: `-m $M --level DEBUG --include
  unit-mysql-k8s-0 --replay --ms`. For one-shot captures use `--limit N`
  (last N lines, then exit) or `--replay --no-tail` (everything so far,
  then exit); bare `-n N` implies `--tail` — it prints the last N lines
  and then FOLLOWS FOREVER; `--no-tail` combined with `-n` errors out
  ("ERROR setting --no-tail and --lines not valid"). It takes no `-c`;
  `-m <controller>:<model>` works, bare `-m <model>` resolves on the
  current controller only.

## Pebble: services and the plan (k8s)

- `pebble services` lists services with their startup config and current
  runtime state; `pebble plan` prints the effective merged layer
  configuration (command, startup, overrides) — ground truth vs the
  charm's layer code.
- Startup config and runtime state are different axes: `enabled`/
  `disabled` is what pebble starts on boot; runtime `active` means
  running now. `pebble stop <svc>` stops the service **and disables its
  startup config** — it stays down across restarts (that property is the
  deliberate-death primitive; the full kill-primitive taxonomy is in the
  `charmed-mysql-fault-injection` skill).
- Runtime states seen in `pebble services`: `active` (running),
  `backoff`/`backoff-stop` (exited, being restarted with a growing
  back-off delay), `error` (failed to start or gave up restarting).
  When behavior doesn't match the plan, look here first.
- k8s units have no systemd: services run under pebble, and above
  pebble the k8s StatefulSet recreates deleted pods. Durable process
  death means defeating both layers.

## Scaling k8s applications (up and down)

On k8s (CAAS) models, scale with `juju scale-application <app> <N>` — it
works in both directions and is idempotent (scaling to the current count
is a no-op):

```bash
juju scale-application -m <model> mysql-k8s 3   # scale up 1→3
juju scale-application -m <model> mysql-k8s 1   # scale down 3→1 in one shot
```

- `juju add-unit mysql-k8s -n 2` also works for scale-up; but
  `scale-application` is the one command that covers up **and** down.
- **`juju remove-unit <unit>` does not work on k8s models.** Removing a
  single named unit fails with "k8s models do not support removing named
  units. Instead specify an application with --num-units."; passing
  multiple named units — even of the SAME application — fails with the
  misleading `ERROR only single application supported`. Do not retry
  these; scale instead.
- Working removal alternatives on k8s: `juju remove-unit mysql-k8s
  --num-units 1` (app-scoped count), or just `juju scale-application
  mysql-k8s <N>`. juju removes the highest-numbered units first — you
  cannot pick specific ordinals; scale down and add back if you must.
- Expect the cluster to re-form around scale changes: 1→3 units form a
  quorate GR group in ~2–3 min; 3→1 settles in ~1 min (removed members
  leave the view gracefully). Poll status for readiness — never sleep a
  fixed duration.
- `scale-application` is k8s-only (its own help: "Set the desired number
  of k8s application units"). For machines models, see "Scaling machines
  applications" below — named-unit removal is supported there.

## Scaling machines applications (up and down)

On machines models, scale up with `juju add-unit <app> -n N` and scale
**down** with `juju remove-unit <unit> [...]` — named-unit removal IS
supported here (unlike k8s), including several units of the same
application in one invocation:

```bash
juju add-unit -m <model> mysql -n 2      # scale up: one new machine per unit
juju remove-unit -m <model> mysql/1 mysql/2 --no-prompt
```

- `remove-unit` asks for confirmation ("Continue [y/N]?") — in scripts
  pass `--no-prompt`, otherwise it aborts with "unit removal: aborted".
  Also takes `--destroy-storage` (deletes the units' storage) and
  `--no-wait` (don't block until removal completes).
- You choose the exact ordinals to remove — there is no "highest first"
  logic like k8s scale-down.
- `scale-application` does NOT exist here: on machines it fails with
  `ERROR Juju command "scale-application" only supported on k8s container
  models`.
- Each unit is a fresh machine (an LXD instance on localhost clouds):
  ~1 min to become active for a trivial charm; data-plane charms like
  `mysql` take much longer (snap install + cluster formation) — poll
  status, don't sleep fixed durations.

## Deploy: trust at deploy time, never after

- Deploy with trust up front: `juju deploy mysql-k8s --channel 8.0/stable
  -n 3 -m <model> --trust`. `--trust` grants cluster-scoped RBAC (k8s).
- Deploy an **exact Charmhub revision** (e.g. to reproduce a bug report's
  charm): `juju deploy mysql-k8s --channel 8.0/stable --revision 423 -n 1
  --trust`. On Juju 3.6 `--revision` REQUIRES `--channel` — revision alone
  fails with "specifying a revision requires a channel for future
  upgrades. Please use --channel"; pin both. **The channel must actually
  contain that revision** — e.g. pinning rev423 (an 8.0 revision) with
  `--channel 8.4/edge` fails with `ERROR listing resources for charm
  "ch:amd64/mysql-k8s-423": No revision was found in the Store.` — use
  the channel the bug report/version info implies. Juju fetches the
  revision from Charmhub directly — do NOT `juju download` the .charm
  first just to deploy it (downloading a .charm is only for self-built
  charms).
  Confirm the pin in `juju status`: app row `Rev` column (JSON:
  `applications.<app>.charm-rev`); the deploy line itself already says
  "revision 423 in channel 8.0/stable". A pinned single unit reaches
  active/Primary ~3 min after deploy. To read that revision's source, use
  the `mysql-operators-source` skill.
- Do NOT plan to `juju trust <app> --scope=cluster` afterwards: it races
  the charm's first hooks, which already call `nodes get`; the loser gets
  **403 Forbidden** and the unit can wedge in error permanently.
- Symptom: the unit sits in **`unknown`** status (hooks never get to run —
  the charm service account has no RBAC) or errors with RBAC/Forbidden
  messages immediately after deploy = trust race lost. The smoking gun is
  in the charm container logs (`kubectl logs <pod> -n <model> -c charm`):
  `ApiError: nodes "<node>" is forbidden: User "system:serviceaccount:<model>:<app>"
  cannot get resource "nodes" in API group "" at the cluster scope`.
  Fix by redeploying with `--trust`, not retries.

## Destroying models

- `juju destroy-model <controller>:<model>` takes the model
  **positionally** — it has no `-m` flag ("ERROR option provided but not
  defined: -m").
- A model with persistent storage (k8s PVCs) REFUSES to destroy without
  `--destroy-storage`: rc=1, "The model has persistent storage remaining:
  N volume(s)". This also applies to healthy single-unit models — one
  deployed charm is enough to trip it.
- Broken or half-provisioned models additionally hang without
  `--force`. Working form: `juju destroy-model <controller>:<model>
  --destroy-storage --no-prompt --force` (~1–2 min for a 3-unit k8s
  model).
- Do not pipe the destroy command through `tail` and trust the exit
  status — the pipe masks the real rc. Run it bare, and confirm with
  `juju models -c <controller>` (listing may lag a few seconds after a
  successful destroy).
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
- k8s units have no systemd: services run under **pebble** (see the
  Pebble section above), and above pebble the k8s StatefulSet recreates
  deleted pods. Durable process death means defeating both layers. On
  machines models it is systemd instead — check which.
- Alternate channel when juju transport is flaky: `kubectl exec` into the
  pod (name `mysql-k8s-<n>`, in the model's namespace). On
  controller-hosted rigs bare `kubectl` may not exist — try `sudo k8s
  kubectl` (the k8s snap), not microk8s.
- CLI invocation rules: juju options go *before* the target (`juju ssh
  --container mysql mysql-k8s/0 "<cmd>"`); pass remote commands as ONE
  quoted string (arg splitting mangles pipes/redirects); juju is a snap
  and cannot read/write `/tmp` — keep bundles/downloads in the project
  dir or `$HOME`.
- `juju exec --unit <unit>` runs in the **charm container** with
  hook-like env (`CHARM_DIR`, `JUJU_UNIT_NAME`); it cannot run python
  heredocs or multi-line `-c` payloads — one-liners only, or `juju ssh`.
- Pebble CLI details: see "Pebble: services and the plan" above.

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

## Charm config: discover keys before setting

- Never guess a charm's config key names — the key sets are per charm,
  per variant (k8s vs machine), and per revision. A guessed key fails
  with rc=1 and an error that is easy to miss in scrolling output
  (a bare `{}` line precedes it):
  - set form (`juju config <app> key=value`):
    `ERROR parsing settings for application: unknown option "k"`
  - query form (`juju config <app> k`):
    `ERROR key "k" not found in "<app>" application config or charm settings.`
- List the valid keys first: `juju config <app>` with no key arguments
  prints the full YAML. Charm options live under the top-level
  `settings:` mapping — each entry shows `default`, `value`, `source`,
  `type`, and `description`.
- Do not confuse `settings:` with `application-config:` in that output:
  `application-config` holds juju-level keys (ingress, exposure), not
  charm options; setting those on a charm app is also an error.
- `juju show-application <app>` does NOT list charm config options on
  juju 3.6 — `juju config <app>` is the reliable discovery command.

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

## Model logging levels (logging-config)

The `juju debug-log` stream contains what the agents *forward* per the
model's `logging-config` — DEBUG spam there is a config state, not a
noise problem; the dial is model config, not debug-log flags.

- **Read first** (controllers may carry non-stock defaults):
  `juju model-config -m <model> logging-config`. Stock default is empty
  (effectively WARNING for root, INFO for units); this box's k8s
  controller sets `<root>=INFO; unit=DEBUG` at controller level (visible
  via `juju model-defaults -c <controller> logging-config`) — which is
  why unit DEBUG lines flood debug-log here.
- **Set** — each segment is `<logger>=<LEVEL>`; quote the whole value as
  ONE shell word (a bare `;` would split your shell command):

  ```bash
  juju model-config -m <model> 'logging-config=<root>=WARNING;unit=INFO'                      # quiet
  juju model-config -m <model> 'logging-config=<root>=WARNING;unit=INFO;unit.mysql-k8s=DEBUG' # DEBUG scoped to one app
  juju model-config -m <model> 'logging-config=<root>=WARNING;unit=WARNING'                   # near-silent
  ```

  Logger scopes: `<root>` = everything, `unit` = all unit agents,
  `unit.<app>` = one app's units. juju echoes the stored value back
  compact (`;`-joined, no spaces) — compare against that, not what you
  typed.
- **Juju 3.x syntax trap**: the legacy Juju 2.x form with a nested
  `<root>` (`unit=<root>=INFO`) is INVALID on 3.6 — even correctly
  quoted it fails with `ERROR unknown severity level "<root>=INFO"`.
  One `=` per segment: `unit=INFO`, never `unit=<root>=INFO`.
- **Quoting trap**: if the command passes through another quoting layer
  (e.g. inside `bash -c "…"`), literal `"` characters can leak into the
  value — the error then echoes them back
  (`unknown severity level "<root>=INFO\""`) — that tell means quoting,
  not syntax, is at fault. Single-quote the outer layer.
- **Restore** after experiments: `juju model-config -m <model> --reset
  logging-config` (returns to the controller default). Changes apply to
  new log lines immediately; existing entries are not rewritten.

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
- `references/status-json-shape.md` — annotated `juju status --format json`
  example with the parsing traps (nested units, scoped queries,
  self-relations, storage).
