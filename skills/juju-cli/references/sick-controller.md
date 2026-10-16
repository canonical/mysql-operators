# The sick controller: client hangs with no output

Companion to the `juju-cli` SKILL.md. Distilled from the 2026-10-14/15
controller incidents on this repo's host (three controllers affected over
two days; all healed the same way); the mechanics are generally
applicable to juju 3.6.x k8s controllers. This is about the **controller**
being sick — for a sick *model*, see `cleanup-and-controller.md`.

## Signature

Fresh juju client connections stall **after TCP connect** — TLS/login
never completes — with **zero output**, including under `JUJU_DEBUG=true`
or `--verbose` (the hang happens before the client logs anything).
Defining properties:

- **Intermittent.** Calls sometimes complete in seconds, which falsely
  exonerates the controller. Judge by repeated timed calls, not one.
- **Poisons everything when the sick controller is the *current*
  controller** — every juju command hangs, even `-c <healthy-controller>`
  ones targeting other controllers (the client contacts the current
  controller during startup).
- `juju controllers` (cached listing) still works — useful as a control.
- Established connections (unit agents, long-polls) and `kubectl` to the
  node's API server are unaffected — the wedge is inside the controller
  pod's api-server/mongodb, not the network.

## Misleading signs (do not be talked out of the diagnosis)

- Node CPU/RAM idle, `iostat` %util ~1%, conntrack far below max, no
  proxy env — **idle host metrics do not exonerate the controller.**
- `echo > /dev/tcp/<api-endpoint>` succeeds — the kernel accepts the
  connection into backlog; the app never answers. TCP reachability
  proves nothing about API health.
- The k8s control plane is a *different* service: `kubectl` works fine
  while juju is dead.

## Diagnosis chain (all read-only)

```bash
# 1. The smoking gun: liveness probe failures on the controller pod
kubectl get events -n controller-<name> --sort-by=.lastTimestamp | grep -E 'Liveness|Unhealthy'
#    observed: Liveness probe failed: command timed out: "mongo --port=37017 --tls ..."
#    (mongod failing against ITSELF on localhost)

# 2. Connection churn: api-server -> mongo reconnect loop
kubectl logs -n controller-<name> controller-0 -c mongodb --since=5m | grep -c 'Client connecting'
#    observed: ~60 in 5 min, loopback, "Client connecting with server's own TLS"

# 3. Client-side reconnect storms from unit agents
kubectl logs -n controller-<name> controller-0 -c api-server --since=30m | grep -i 'TLS handshake'

# 4. Origin check: was the pod OOM-hit? (exit 137 = OOM-killed)
kubectl get pod -n controller-<name> controller-0 -o jsonpath='{range .status.containerStatuses[*]}{.name}={.restartCount} {.lastState.terminated.exitCode} {.lastState.terminated.finishedAt}{"\n"}{end}'
dmesg | grep -i oom
```

Observed origin: a night-time node memory squeeze OOM-killed the charm
container (exit 137) and left mongod internally wedged; the wedge
persisted for hours after the pod came back "Running". A crash-looping
controller (repeated 137s) is the chronic form — its API can be
unresponsive for a day or more.

## The heal: restart the controller pod (worked 3/3)

```bash
kubectl delete pod controller-0 -n controller-<name>
# pod back 3/3 in ~40 s; then wait ~75 s for the juju agent to settle:
time (timeout 60 juju models -c <name> > /tmp/jm-check.txt 2>&1)
echo $?   # juju's OWN exit code — see gotcha below
```

Observed: 90 s timeouts (zero bytes) → 0.185–0.25 s responses, twice in
a row. Model state survives (mongo data is on a persistent volume); the
harness model re-registers "just now". Choose the restart window when
nothing depends on the controller (no in-flight juju calls from agents
or scripts).

**If the API cannot be revived**, destroying via juju is impossible (the
client hangs at login before any teardown RPC). Manual teardown:
`juju unregister <name>` (client-side only — k8s resources remain) +
`kubectl delete ns controller-<name>`.

## Gotchas that cost time

- **Pipeline exit codes lie**: in `juju models -c X | tail`, `$?` is
  *tail's* exit code, not juju's. Capture to a file and check juju's own
  exit status.
- **A pointer flip is not the fix (usually).** With `current-controller`
  pointing at the wedged controller every command hangs — `juju switch
  <healthy>` is instant client-side first aid and worth doing — but a
  hang that *persists* after the switch means the wedge is server-side
  (see the heal above). Proven in the incident: a scratch-HOME probe
  with a corrected pointer succeeded while the real HOME still hung on
  an unrelated-looking path; only the pod restart fixed it.
- **Stale controller registrations are a trap for later sessions.** An
  agent (or a colleague, or future-you) will discover an unused
  registration in `controllers.yaml`, investigate it, and hang on its
  dead API — possibly auto-flipping the pointer behind its own
  bootstrap. Unregister or destroy dead controllers promptly; do not
  leave them "for later".
- **Anything run through agent shell tools uses the real `$HOME`** —
  only the tool's own config is sandboxed. An agent-side `juju
  bootstrap` therefore writes the host's `controllers.yaml` AND
  auto-flips `current-controller` to the new controller. Check it after
  any agent juju activity:
  `grep current-controller ~/.local/share/juju/controllers.yaml`
- A controller pod that OOM-crash-loops (restartCount climbing, exit
  137) will not heal by waiting — restart the pod, and if wedges recur,
  look at host memory pressure history first.
