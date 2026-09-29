# Cleanup mechanics and controller recovery

Companion to the `juju-cli` SKILL.md. These are the deeper items: orphaned
process sweeps, what the sandbox can and cannot kill, host-saturation
symptoms, and the playbook for a sick controller. Written for this repo's
host (single machine running the k8s controller + models); the mechanics are
generally applicable.

## Orphaned process sweeps

Evaluated agent sessions leave two kinds of debris behind:

1. **Background status-sampler loops** —
   `while true; do ...; juju status --format json ...; sleep 5; done`
   wrappers, sometimes via `setsid`, sometimes standalone script files
   (`sampler.sh`, `sample-status.sh`), writing to `status-samples.log` /
   `samples.log`. Each spawns a fresh `juju status` every 5–10s: measurable
   CPU load and controller churn.
2. **Stray juju client processes** from crashed sessions (`juju status`,
   `juju run` that never returned).

Sweep patterns (proven working; `2>/dev/null || true` to stay quiet on
no-match):

```bash
pkill -9 -f "while true.*juju (status|run)"
pkill -9 -f "[s]ampler\.sh|[s]ample-status\.sh|status-samples"
pkill -9 -f "bin/juju (status|run)"
```

Notes:

- The `[s]` bracket trick prevents the pkill pattern from matching the pkill
  process itself. Verify the sweep matched nothing you need:
  `ps aux | grep -E "[j]uju (status|run)|[w]hile true.*juju"`.
- **`setsid` escapes process-group kills.** Killing the parent's PGID does
  not reap loops that called `setsid` internally — sweep by pattern, not by
  process group.
- Verify afterwards that only the expected mysqlds remain on the host:
  `pgrep -c mysqld` (3 for a healthy 3-unit `testing` model). More than that
  = leftover experiment models; reconcile with force-destroys, not by
  killing mysqld directly.

## What can and cannot be killed from the agent sandbox

- **SIGKILL from the pi sandbox is blocked** by AppArmor signal mediation
  (`cri-containerd.apparmor.d` refuses SIGKILL from
  `snap.pi-coding-agent.pi`). SIGTERM and killing your own process-group
  children do work.
- Kernel-side workaround when you have sudo — cgroup-v2 kill switch:

  ```bash
  echo 1 > /sys/fs/cgroup/<pod-cgroup>/cgroup.kill
  ```

- **SIGKILLed runners do not run their EXIT traps.** Any cleanup logic
  (destroy scratch model, sweep debris) must therefore be idempotent and
  re-runnable: on every resume, reconcile leftover state first (force-destroy
  the known scratch-model name, sweep debris) instead of assuming a clean
  slate. See `eval/run-matrix.sh` `fi_pre`/`fi_cleanup` for the pattern.
- Bounds beat watchdogs: prefer giving background work explicit timeouts and
  iteration caps so it dies by itself rather than needing to be hunted.

## Host saturation symptoms vs Juju faults

Under host CPU/RAM saturation, juju's connection to the k8s API degrades
*before* anything juju-specific misbehaves:

- `juju status` fails with `ERROR starting proxy for api connection:
  connecting k8s proxy: ... TLS handshake timeout` — to `127.0.0.1:6443`,
  i.e. the loopback controller.
- Action tasks stall far past their usual durations; agent hooks queue.

If loopback TLS handshakes are timing out, **suspect the host first**:
check `uptime` (load vs cores), `free -h`, and stray processes (`pgrep -c
mysqld`, the sweep patterns above). Don't debug juju or redeploy while the
host is thrashing — fix load, then re-verify.

## Rebuilding a sick model (and when to)

After aggressive model cleanup the controller's state can be left
inconsistent; debugging controller internals (mongod, pebble, jujud) is
rarely worth it compared to:

```bash
juju destroy-model <model> --destroy-storage --no-prompt --force
juju add-model <model>
juju deploy mysql-k8s --channel 8.0/stable -n 3 --trust
```

Then **re-baseline**: the fresh deployment is the new known-state baseline
(no prior state, no prior experiments). Verify before use: 3/3 units
active+idle, `get-cluster-status` → all members online, single-primary
topology, and `get-password` works (this also proves charm RBAC via
`--trust` is in place).

Rebuild (instead of repair) is the right call when: models were destroyed
out from under running hooks, the controller lost models it still lists, or
units wedge in states that survive `juju resolved`/retry cycles. Repair is
only worth attempting for single-unit, well-understood breakage.
