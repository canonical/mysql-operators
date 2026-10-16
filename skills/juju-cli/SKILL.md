---
name: juju-cli
description: >
  Operates the Juju CLI on any cloud, model, or charm, deploys charms
  with or without trust, executes commands on unit containers, separates
  actions from shell commands, drives pebble, reads status and debug-log,
  manages models. Use before any juju or pebble command.
license: Apache-2.0
metadata:
  author: canonical-data-platform
  version: "0.12.0"
---

# Juju CLI gotchas

## Overview

The Juju CLI has several traps that silently produce the wrong outcome: a
deploy that never converges (trust race), a destroy that hangs, a kill
command that kills its own wrapper shell (exit 137), an action that looks
timed out but succeeded, and an inspection of the wrong controller. This
skill lists the working pattern for each. All commands assume a k8s
model unless noted; machines-model differences are flagged inline.

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
  Readiness for a multi-unit app = every unit with workload `active`
  AND agent `idle`; poll for that, never fixed sleeps. Wrap the whole
  wait in ONE tool call — `for i in $(seq 20); do juju status --format
  json | <readiness check> && break; sleep 30; done; juju status` —
  and report the final state. Issuing one status command per tool call
  between sleeps multiplies calls, context, and LLM turns for zero
  extra information.
- juju status healthy ≠ charm application health: verify via the
  charm's own action or protocol (e.g. a database charm exposes a
  `get-cluster-status` action), not by juju status alone —
  charm-specific inspection skills carry the interpretation.
- App status `blocked` can be normal (e.g. an app waiting for a required
  relation). Check the message before treating it as an incident.
- `juju debug-log` essentials: `-m $M --level DEBUG --include
  unit-<app>-0 --replay --ms`. For one-shot captures use `--limit N`
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
juju scale-application -m <model> app-k8s 3   # scale up 1→3
juju scale-application -m <model> app-k8s 1   # scale down 3→1 in one shot
```

- `juju add-unit app-k8s -n 2` also works for scale-up; but
  `scale-application` is the one command that covers up **and** down.
- **`juju remove-unit <unit>` does not work on k8s models.** Removing a
  single named unit fails with "k8s models do not support removing named
  units. Instead specify an application with --num-units."; passing
  multiple named units — even of the SAME application — fails with the
  misleading `ERROR only single application supported`. Do not retry
  these; scale instead.
- Working removal alternatives on k8s: `juju remove-unit app-k8s
  --num-units 1` (app-scoped count), or just `juju scale-application
  app-k8s <N>`. juju removes the highest-numbered units first — you
  cannot pick specific ordinals; scale down and add back if you must.
- Expect the cluster to re-form around scale changes: 1→3 units form a
  quorate cluster in ~2–3 min; 3→1 settles in ~1 min (removed members
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
juju add-unit -m <model> <app> -n 2       # scale up: one new machine per unit
juju remove-unit -m <model> <app>/1 <app>/2 --no-prompt
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
  ~1 min to become active for a trivial charm; data-heavy charms can
  take much longer (snap install + cluster formation) — poll
  status, don't sleep fixed durations.

## Deploy

- Deploy an **exact Charmhub revision** (e.g. to reproduce a bug report's
  charm): `juju deploy <charm> --channel <series>/stable --revision <N>
  -n 1 --trust`. On Juju 3.6 `--revision` REQUIRES `--channel` — revision alone
  fails with "specifying a revision requires a channel for future
  upgrades. Please use --channel"; pin both. **The channel must actually
  contain that revision** — e.g. pinning an 8.0-series revision with
  `--channel 8.4/edge` fails with `ERROR listing resources for charm
  "ch:amd64/mysql-k8s-423": No revision was found in the Store.` — use
  the channel the bug report/version info implies. Juju fetches the
  revision from Charmhub directly — do NOT `juju download` the .charm
  first just to deploy it (downloading a .charm is only for self-built
  charms).
  Confirm the pin in `juju status`: app row `Rev` column (JSON:
  `applications.<app>.charm-rev`); the deploy line itself already says
  "revision <N> in channel <channel>". A pinned single unit converges to
  active ~3 min after deploy (charm-dependent). To read that revision's
  source, use the charm family's source skill (`mysql-charms-source`
  covers the mysql charm family).
- **Verify every deploy converges — short polls with a failure exit.**
  Poll `juju status` a few times (~15–30s apart) after deploying. If a
  unit shows `blocked`, `error`, or `unknown`, stop and diagnose
  immediately — the unit message names the problem (for RBAC blocks see
  [Trust and RBAC](#trust-and-rbac) below); such statuses do not heal
  on their own. Never run a long "wait until success" loop without a
  failure exit — polling past the first failure burns wall time for
  nothing.

### Trust and RBAC

- **What it is**: `--trust` grants the charm's Kubernetes service
  account cluster-scoped RBAC, so the charm can access Kubernetes
  resources. A K8s charm that needs such access needs trust — without
  it the charm cannot, e.g., read nodes or patch its own statefulset.
- **Grant at deploy time**: `juju deploy <charm> --channel <channel>
  -n 3 -m <model> --trust`. Prefer this — it is the reliable path.
- **Apply afterwards**: an already-deployed app that is *not* wedged in
  error can be trusted in place: `juju trust <app> --scope=cluster
  -m <model>`. The next hook run picks it up — a **blocked** unit needs
  no nudge (`juju resolve` only applies to units in error): observed
  recovery to active within ~60s of granting trust.
- **Detect it was needed but not applied**: the charm surfaces the
  missing RBAC as a block, in one of two ways: (a) the unit sits in
  **`unknown`** right after deploy — its first hooks never got to run;
  or (b) the app reached a status but later operations fail — the unit
  message contains `... is forbidden: User
  "system:serviceaccount:<model>:<app>"`. Confirm by that forbidden
  message: the service-account string names the exact identity lacking
  the scope, and the charm container logs (`kubectl logs <pod> -n
  <model> -c charm`) carry the matching `ApiError: ... is forbidden ...
  at the cluster scope`.
- **The first-hook race gotcha**: trusting after deploy races the
  charm's first hooks, which already call the Kubernetes API; the loser
  gets **403 Forbidden** and the unit can wedge in error permanently.
  A unit wedged in error from that race is not fixed by trust —
  redeploy with `--trust`, not retries.

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
- A model left in a post-mortem state by a killed run can hang a
  *graceful* destroy forever — always pass `--force --no-wait` when the
  model's previous occupant died abnormally.

## Destroying controllers

- Working form (proven — destroyed a k8s controller in 12 s):

  ```bash
  juju destroy-controller --destroy-all-models --destroy-storage \
      --no-prompt jujuc-ck8s-40-14 --debug
  ```

  Without `--no-prompt` the confirmation prompt requires typing the
  controller name.
- The destroy **unregisters automatically** on success. Verify:
  `grep <name> ~/.local/share/juju/controllers.yaml` → gone;
  `kubectl get ns | grep controller-<name>` → gone.
- **A controller whose API is unresponsive cannot be destroyed via
  juju** — the client hangs at login before any teardown RPC. Heal the
  controller first (see [When the juju client hangs](#when-the-juju-client-hangs-sick-controller)
  below); the destroy then completes in seconds. If the API cannot be
  revived: `juju unregister <name>` (client-side only — k8s resources
  remain) plus `kubectl delete ns controller-<name>`.
- `--destroy-all-models` / `--destroy-storage` mean what they say —
  everything in the controller is lost.

## When the juju client hangs (sick controller)

Signature: fresh juju commands stall **after TCP connect** with **zero
output** — even under `JUJU_DEBUG=true` / `--verbose` — and the pattern
is **intermittent** (calls sometimes complete, which falsely exonerates
the controller). Node CPU/RAM/disk can look completely idle, and TCP
connect succeeding proves nothing (kernel accepts, app never answers).
If the wedged controller is the *current* controller, every command
hangs — even `-c <other-controller>` ones. `juju controllers` (cached)
keeps working — use it as the control.

Observed root cause: mongod inside the controller pod intermittently
unresponsive (after a night-time OOM), so the api-server's DB pool
churns and every client login queues behind it. The smoking gun is the
kubelet liveness probe failing ON the controller pod:
`kubectl get events -n controller-<name>` → `Liveness probe failed:
command timed out: "mongo --port=37017 --tls ..."`.

**The heal — restart the controller pod (worked 3/3):**

```bash
kubectl delete pod controller-0 -n controller-<name>
# back 3/3 in ~40 s; wait ~75 s for the juju agent to settle, then:
time (timeout 60 juju models -c <name> > /tmp/jm-check.txt 2>&1)
```

Observed: 90 s timeouts (zero bytes) → 0.2 s responses. State survives
(persistent volume). Model rebuilds are pointless here — it is the
controller, not the model. Full diagnosis chain, origin forensics, and
the pointer/registration hazards (a stale registration hangs later
sessions; a wedged *current* controller poisons every command; bootstrap
auto-flips the pointer): see `references/sick-controller.md`.

## Running commands in units

- `juju ssh <unit>` lands in the **charm** container. In multi-container
  k8s charms the workload runs in its own container — target it
  explicitly:
  `juju ssh -m $M --container <workload> <app-k8s>/0 "..."`.
- Never use `pkill -f <pattern>` through any exec-with-shell channel (juju
  ssh, kubectl exec) — or on the host from a tool call: the pattern matches
  the wrapper shell / the tool call's own command line, which SIGKILLs
  its own exec context — exit **137** (or 143) before doing what you
  asked. Use exact-name matches: `pkill -x <process> --signal SIGKILL`.
- k8s units have no systemd: services run under **pebble** (see the
  Pebble section above), and above pebble the k8s StatefulSet recreates
  deleted pods. Durable process death means defeating both layers. On
  machines models it is systemd instead — check which.
- Alternate channel when juju transport is flaky: `kubectl exec` into the
  pod (name `<app>-<n>`, in the model's namespace). On
  controller-hosted rigs bare `kubectl` may not exist — try `sudo k8s
  kubectl` (the k8s snap), not microk8s.
- CLI invocation rules: juju options go *before* the target (`juju ssh
  --container <workload> <app-k8s>/0 "<cmd>"`); pass remote commands as ONE
  quoted string (arg splitting mangles pipes/redirects); juju is a snap
  and cannot read/write `/tmp` — keep bundles/downloads in the project
  dir or `$HOME`.
- Batch related probes into ONE exec: a single
  `juju ssh --container <c> <app>/0 "cmd1; echo ===; cmd2; echo ===; cmd3"`
  with separators beats three separate ssh calls — one round-trip, one
  context block, one LLM turn. Reserve separate calls for probes whose
  result changes what you probe next.
- `juju exec --unit <unit>` runs in the **charm container** with
  hook-like env (`CHARM_DIR`, `JUJU_UNIT_NAME`); it cannot run python
  heredocs or multi-line `-c` payloads — one-liners only, or `juju ssh`.
- Bulk-writing files into a workload container (e.g. synthesizing log
  history for an aging experiment): do it with ONE in-container
  `python3 -c` script, not from the host. Host→container stdin is
  unreliable — `sudo k8s kubectl exec -i ... < filelist` delivered
  zero bytes inside the container (observed twice) — and the
  container's `/bin/sh` is dash, which aborts on bash-isms in
  arithmetic (`10#00`, `08`/`09` octal), silently skipping loop
  iterations. python3 ships in most rocks (charms need it) and avoids
  both traps. If you must use shell, pass paths as arguments in
  chunks, never via stdin.
- Pebble CLI details: see "Pebble: services and the plan" above.

## Actions vs shell commands

- Discover what a charm can do with `juju actions <app-name> [--format
  json]` — it lists the application's supported actions with their params
  (e.g. a database charm's actions: `get-password`,
  `get-cluster-status`, `create-backup`, ...). `juju actions` with no
  app lists for the current model's apps.
- `juju run <unit> <action> [params]` runs a **charm action** only.
  Assume nothing about the action set: an obvious-sounding action may
  not exist (observed: no `get-credentials` — consumers got credentials
  via a relation instead; on-unit admin access went through a
  `get-password`-style action). Discover with `juju actions` first.
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
  Leftover experiment models accumulate real cost (each unit ≈ 2GiB
  RAM, charm-dependent).
- `JUJU_MODEL` env var sets the default model for all juju commands;
  `juju switch` changes it persistently; explicit `-m <model>` beats both.
  Always pass `-m` in scripts.
- Multiple controllers exist on this box (k8s and VM). If observations look
  wrong, run `juju controllers` and `juju models` before trusting anything.
- Check `grep current-controller ~/.local/share/juju/controllers.yaml`
  after any `juju bootstrap` — bootstrap auto-switches the current
  controller. A wedged *current* controller makes every juju command
  hang, even `-c` calls targeting healthy controllers; `juju switch
  <healthy>` is instant client-side first aid.
- Unregister or destroy dead controller registrations promptly — later
  sessions discover them in `controllers.yaml`, investigate, and hang on
  their dead APIs (see `references/sick-controller.md`).
- Bound any background sampling loop (timeout, max iterations) and `wait`
  for it in the same script — daemonized `while true; do ...; juju status;
  sleep 5; done` loops outlive sessions and add constant CPU/controller
  churn. They also survive process-group kills when launched via `setsid` —
  see `references/cleanup-and-controller.md` for the sweep patterns.

## Sampling over time: inline loops vs background processes

Measuring a trend (CPU, file counts, memory) across several tool calls
has a launch trap: `nohup script.sh &` is NOT reliably detached — in
one observed run the tool call that launched the sampler self-terminated
(SIGTERM from a self-matching `pkill -f`), the sampler never wrote a
line, and ~5 calls were burned on relaunch attempts. Working forms,
best first:

- **Inline loop in one call** when the window fits the tool timeout:
  `for i in $(seq 10); do sample >>/tmp/data.csv; sleep 30; done` —
  nothing to keep alive, nothing to clean up. A bare `sleep N` as its
  own tool call is always a bug — sleep inside a measuring call.
- **Perturb-and-measure experiments: one call per rung, rungs stacked
  per call.** Each rung = perturbation → wait → sample, in a single
  call; stack multiple rungs into one call while the tool timeout
  allows (`inject 600; sleep 60; sample; inject +2400; sleep 60;
  sample; ...`), echoing a compact summary line per rung (files,
  ticks, rate) so the transcript stays readable. Every extra
  round-trip re-sends the whole experiment context to the model — the
  largest avoidable cost in long experiments.
- **`setsid bash /tmp/sampler.sh >/tmp/sampler.log 2>&1 < /dev/null &`**
  for longer windows: `setsid` gives the loop its own session, which
  survives tool-call process-group kills. Invoke via `bash <script>`
  (or `chmod +x` first) — `setsid` cannot exec a non-executable file
  ("failed to execute /tmp/sampler.sh: Permission denied"). Verify it
  is alive from a separate call; note `pgrep -f sampler` matches the
  calling wrapper's own command line too — match on something absent
  from your own command (or read `ps` output for a PID that is not
  your own).

Bound and kill any background sampler before finishing (Model hygiene
above; sweep patterns in `references/cleanup-and-controller.md`).

## Logs, logging levels, logging config

```bash
juju debug-log -m <model> --ms --level DEBUG --replay [--no-tail / --tail]
```

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
  juju model-config -m <model> 'logging-config=<root>=WARNING;unit=INFO;unit.<app>=DEBUG' # DEBUG scoped to one app
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
- Every hook process starts with `ops <version> up and running.` — use as
  a process-start marker when correlating.
- On controllers where kubectl works, `kubectl logs <pod> -c charm` gives
  the same content fresher (but is lost on container restart); `juju
  debug-log` survives restarts (model logging config permitting — check
  `juju model-config logging-config`).

## Do not

- Do not deploy k8s charms without `--trust`, or trust them post-deploy.
- Do not use `pkill -f` / broad `grep` patterns inside exec-with-shell
  channels (`juju ssh`, `kubectl exec`) — they match the wrapper and exit 137.
- Do not treat a `juju run` client-side timeout as action failure.
- Do not assume juju status reflects application-level cluster health
  (the charm's own health action is the truth).
- Do not destroy a model without `--destroy-storage --no-prompt --force`
  when it is broken, and never destroy without confirming you can lose the
  data.
- Do not leave scratch models or background sampler loops behind.
- Do not leave dead controller registrations in `controllers.yaml` —
  they hang later sessions that investigate them.
- Do not destroy a controller whose API is unresponsive — heal it first
  (restart the controller pod; see "When the juju client hangs" and
  `references/sick-controller.md`), then destroy.
- Do not debug a sick model piecemeal — re-create the model (see
  reference file below) and re-baseline. If the *controller* is sick
  (every juju command hangs with no output), a model rebuild is
  pointless — restart the controller pod instead.

## References

- `references/cleanup-and-controller.md` — orphaned-process sweeps, AppArmor
  SIGKILL limits and the cgroup-kill workaround, host-saturation symptoms,
  and the rebuild-the-model playbook.
- `references/status-json-shape.md` — annotated `juju status --format json`
  example with the parsing traps (nested units, scoped queries,
  self-relations, storage).
