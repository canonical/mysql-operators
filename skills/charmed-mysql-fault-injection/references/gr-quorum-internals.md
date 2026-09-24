# Group Replication quorum internals

Reference for `charmed-mysql-fault-injection` step 3. Why NO_QUORUM is
stable, what can and cannot end it, and how to analyze any GR knob before
using it.

## Membership, failure detection, expulsion

- GR maintains a membership view of all members (regardless of health).
  Failure detection runs on a ~5s period; a suspect member is listed
  `UNREACHABLE` but **stays in the membership list**.
- **Expelling a suspect is a group reconfiguration, and reconfiguration
  requires consensus (majority).** With a majority unreachable, the
  surviving minority cannot expel, cannot shrink the view, and cannot
  elect — by protocol design, not by charm bug.
- `group_replication_unreachable_majority_timeout` (self-exit of a
  minority member after losing majority) defaults to 0 = **disabled**,
  and the charm sets no expel/unreachable-majority variables by default.
- Therefore the only events that can end NO_QUORUM:
  1. Enough dead members come back **reachable** (rejoin attempts then
     find a majority of the view — note a *rejoining* member itself needs
     a majority of the view to be accepted, so a lone survivor plus
     returning members can still be stuck depending on order).
  2. The operator: `promote-to-primary force=true` →
     `forceQuorumUsingPartitionOf()` on a survivor — declares the
     surviving partition authoritative, shrinks the view, elects the
     target primary.

Consequence for test design: you don't need to win a race against GR
timers. You need mysqld killed **abruptly** (no clean leave) and **kept
down**. Everything else — expulsion, view shrink, self-heal — is
structurally blocked by the absence of majority.

## Graceful vs abrupt exit, precisely

- `pebble stop mysqld` sends SIGTERM; mysqld's shutdown path stops Group
  Replication cleanly → the group performs a *planned* reconfiguration
  (view shrinks with consensus) → remaining members form a healthy
  (if zero-tolerance) group. Observable as `OK_NO_TOLERANCE` with the
  survivor PRIMARY.
- SIGKILL (or `SIGSTOP` freeze) skips the shutdown path → members go
  `UNREACHABLE` in the survivors' view → with majority gone, the state
  is frozen. The survivors' status payloads (via
  `get-cluster-status` from a survivor) show `no_quorum` — or the action
  fails outright because `cluster.status()` needs quorum.

## Force-quorum: the contract

`forceQuorumUsingPartitionOf('<this instance>')`:

- Declares the surviving partition authoritative; **shrinks the group
  view**; elects the target primary. Destructive and view-altering.
- **Refuses to run when the cluster has quorum**, verbatim:
  ```
  Cluster.force_quorum_using_partition_of: The cluster has quorum according to
  instance '<fqdn>:3306'
  ```
  and in the JSON stream:
  ```
  Cannot perform operation on an healthy cluster because it can only be used
  to restore a cluster from quorum loss.
  ```
- The refusal is the safety feature that keeps the destructive operation
  from running on a merely-degraded cluster. Any charm-side "fall back to
  switchover when the cluster looks OK" wrapper around it **redefines the
  action's contract** and masks operator error — rejected in real review.
- After a successful force, restarted members rejoin against the new
  primary (the charm's manual-rejoin path works once an ONLINE peer
  exists).

State matrix to memorize:

| Cluster state at action time | `promote-to-primary force=true` | Correct? |
|---|---|---|
| `ok` / any `ok_*` (quorate) | Fails with the refusal | Yes — feature |
| `no_quorum` (stable minority) | Succeeds; view shrinks; members rejoin | Yes — the purpose |

## The knob-analysis pattern (before adding any GR variable)

When a fix or test idea requires a new GR knob or SQL poke, ground it in
the manual first (two minutes vs a wasted charm knob):

1. **Scope & mutability**: global? dynamic (`SET GLOBAL`) or read-only at
   runtime? (e.g. `admin_address` is read-only → dead end immediately).
2. **Default & version**: defaults changed across 8.0.x point releases
   (e.g. `member_expel_timeout` 0 → 5 at 8.0.21).
3. **Semantics**: what exactly happens at expiry — and critically,
   **who acts on it, and does that actor need quorum?**
   - `group_replication_member_expel_timeout`: adds a waiting period
     before a *quorate group* expels a suspect. Its real job is
     tolerating transient blips so returning members re-enter ONLINE
     without intervention. **In majority loss the knob is never
     consulted** — no quorum exists to expel with.
   - `group_replication_unreachable_majority_timeout`: minority member
     self-exit; default 0 (disabled); relevant only if you *want* the
     survivor to leave the group on its own (usually you don't).
4. **Does the charm already set it?** (grep the repo; historically: no.)

## Version caveat

The semantic model above matches charms before the 8.4 "safe auto-recover
from no_quorum" work (#354-era and later). Newer charms add a designed
recovery path: no_quorum → offline → reboot-from-outage when all nodes
become reachable. Before trusting the "only force-quorum can end it" rule
on a given deployment, check the deployed charm for the recovery path
(`reboot_from_complete_outage` handling in `_handle_potential_cluster_
crash_scenario`-equivalent code) — the *kill* taxonomy still applies, but
the post-kill dynamics may include an automatic recovery once reachability
is restored.
