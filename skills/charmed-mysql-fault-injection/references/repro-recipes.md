# Repro recipes — worked experiment sequences

Reference for `charmed-mysql-fault-injection`. Each recipe: goal → target
state → commands → expected observations → restore. All assume k8s charm
`mysql-k8s` in model `<m>`; adapt app names/units. For the VM charm, swap
pebble for snap/systemd (see juju-inspect machines-topology).

## Recipe 1 — Control-plane failure for error-path/log verification

**Goal**: force `get-cluster-status` (or any charm↔mysqld path) to hard-fail
and verify the charm's error logging/retry behavior.
**Target state**: connection refused on admin port 33062 everywhere;
self-healing afterwards (acceptable — you only need the failure window).

```bash
M=<model>
PW=$(juju run -m $M mysql-k8s/0 get-password username=serverconfig --format json | jq -r '.["password"] // .password')  # adapt to your jq of the result

# 1. Shut down mysqld on ALL units in parallel (admin port; FQDN host)
for n in 0 1 2; do
  juju ssh -m $M --container mysql mysql-k8s/$n \
    "mysqladmin --user=serverconfig --password='$PW' \
     --host=mysql-k8s-$n.mysql-k8s-endpoints.$M.svc.cluster.local --port=33062 shutdown" &
done; wait
sleep 0.5

# 2. Trigger the code path under test
juju run -m $M mysql-k8s/0 get-cluster-status      # expect action failure

# 3. Read the charm logs (charm container)
juju ssh -m $M mysql-k8s/0 "true"                  # (charm container is default)
juju debug-log -m $M --ms --level DEBUG --include unit-mysql-k8s-0 --replay --no-tail \
  | grep -E "Failed|ERROR|ops .* up and running"
```

Timing notes: the failure surfaces after mysqlsh's connect timeout (~3.5s)
— give it a moment. Shutdown on **all** units: the action roams to any
reachable member. Pebble restarts mysqld automatically; verify recovery:

```bash
juju ssh -m $M --container mysql mysql-k8s/0 "/charm/bin/pebble services"
```

Do **not** delete pods to stop mysqld: the pod death kills the charm
process mid-action (no logs, lost kubectl history).

## Recipe 2 — Stable quorum loss (NO_QUORUM)

**Goal**: cluster in genuine, stable `no_quorum` to test quorum-loss
recovery / `promote-to-primary force=true`.
**Target state**: 2 of 3 members killed abruptly and kept down.

```bash
M=<model>
for n in 1 2; do
  # abrupt death: SIGKILL, exact process-name match (NOT -f!)
  juju ssh -m $M --container mysql mysql-k8s/$n "pkill -x mysqld --signal SIGKILL"
  # immediately suppress pebble's auto-restart
  juju ssh -m $M --container mysql mysql-k8s/$n "pebble stop mysqld"
  # verify once, fail fast (no retry loops)
  juju ssh -m $M --container mysql mysql-k8s/$n "pgrep -x mysqld" && echo "STILL ALIVE" || echo "down"
done
sleep 10

# assert the target state BEFORE firing the action (self-diagnosing test)
juju run -m $M mysql-k8s/0 get-cluster-status     # expect: fails, or no_quorum payload

juju run -m $M mysql-k8s/0 promote-to-primary scope=unit force=true   # expect success (~70s)

# restore
juju ssh -m $M --container mysql mysql-k8s/1 "pebble start mysqld"
juju ssh -m $M --container mysql mysql-k8s/2 "pebble start mysqld"
juju status -m $M   # all units rejoin against the new primary
```

Checkpoint timeline from a real run: kills T+0/T+1, action fires T+12,
returns OK T+82, both units rejoin after `pebble start` T+96 — the force
action itself takes ~70s; don't use short `juju run --wait`.

Anti-checks: if you instead see a *healthy* single-member group
(`ok_no_tolerance`), your kill was graceful (a SIGTERM slipped through) —
redo with SIGKILL + `pebble stop`. If the force action fails with "cluster
has quorum", the cluster healed — your injection didn't stick.

## Recipe 3 — Deterministic relation-setup poisoning

**Goal**: reproduce "provider active, requirer waiting forever" without
chasing the original DNS race.
**Target state**: K8s Services missing at relation time → guaranteed
NXDOMAIN in the provider's endpoint resolution.

```bash
M=<model>
# 0. Slow update-status so you can SEE the intermediate blocked state
juju model-config -m $M update-status-hook-interval=5m    # remember to restore!

# 1. Deploy provider + client app; wait for provider active
juju deploy -m $M ./mysql-k8s.charm target --trust \
  --num-units 1 --resource mysql-image=ghcr.io/canonical/charmed-mysql@sha256:<digest>
juju deploy -m $M mysql-test-app

# 2. Delete the endpoint Services (nothing recreates them until charm restart)
juju ssh -m $M --container mysql target/0 "true"   # (k8s access needed; or use
#   a controller-hosted kubectl: sudo k8s kubectl -n $M delete svc target-primary target-replicas)

# 3. Relate → the failure chain runs deterministically:
juju relate -m $M target:database mysql-test-app
#    hook exit 1 (resolve RuntimeError) → rollback → retry → CREATE USER 1396
#    → blocked status (clean exit) → snapshot+wrong-password secret committed
#    → update-status masks to active → requirer waits forever
```

Expected evidence: requirer stuck "Incorrect/incomplete data"; provider
`get-password`-less relation data in `db-dump.yaml` (databag `r#<id>#target`
without credentials); secret `create-time` == retry commit time.
Restore: `juju remove-relation`, `juju model-config update-status-hook-interval=<orig>`.

Alternative trigger without kubectl: marker-file fault injection —
edit the deployed charm's `utils.py::get_k8s_fqdn` to
`raise RuntimeError("injected")` when `/tmp/inject-fqdn` exists, create the
file, relate, observe, remove file.

## Recipe 4 — Observing status masking

**Goal**: watch a blocked status get overwritten by update-status.
**Target state**: any transient blocked status + fast update-status.

```bash
juju model-config -m <model> update-status-hook-interval=15s
# trigger any blocked status (e.g. Recipe 3, or a TLS/broken-relation block)
# watch status-log / juju-status snapshots: blocked → active within ~15-30s
juju model-config -m <model> update-status-hook-interval=5m   # restore default
```

Trade-off: a *slow* interval lets you observe the blocked state between
updates; a *fast* interval demonstrates the masking itself. Pick per goal.

## Recipe 5 — A/B protocol (same code, two environments)

**Goal**: prove a behavior difference is structural, not environmental.

```bash
# capture from t0 (replays full history, then follows)
setsid juju debug-log -m <model> -i unit-app-0 -n 0 > t0.log 2>&1 < /dev/null &
# sample status every 10s for N minutes
while true; do date >> samples.log; juju status -m <model> --format json >> samples.log; sleep 10; done &
```

Then analyze the uniter lifecycle from `t0.log` with the log-autopsy
skill's `scripts/parse_uniter_ops.py` (durations, gaps, busy fraction).
Compare per-operation durations between environments before concluding —
durations scale with the rig, cadence does not.

## Post-experiment checklist

- [ ] Restore `update-status-hook-interval`.
- [ ] `pebble start mysqld` everywhere it was stopped (or accept model destruction).
- [ ] Models preserved until post-mortem; then
      `juju destroy-model <m> --destroy-storage --no-prompt --force`.
- [ ] Credentials re-fetched if anything was refreshed.
- [ ] Marker-file injections removed from deployed charm sources.
- [ ] Evidence (logs, status samples, action outputs) archived with the
      experiment notes.
