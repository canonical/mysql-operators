---
myst:
  html_meta:
    description: "Explanation for Charmed MySQL self-healing capabilities."
---

(self-healing)=
# Self-healing

Charmed MySQL has built-in self-healing capabilities for the most common failure cases. Following 
the automatic recovery cases, where the user can expect the charm to return to a functional state, 
and some cases where user intervention might be required.

## Automatic self-healing cases

These are cases where the user can expect the charm to recover automatically as long as there is no data corruption in the storage.

```{caution}
The self-healing procedures rely on the scheduled `update-status` event. Make sure your Juju model 
has this interval set to a reasonable value, otherwise self-healing may take too long or not even 
trigger if the update status event is disabled.
Check [Juju 
documentation](https://documentation.ubuntu.com/juju/3.6/reference/hook/#update-status) for more 
information.
```

### Complete outage

A complete cluster outage happens when all units go offline, e.g. a power outage. When this 
happens, the charm will wait until all units are in `OFFLINE` state, and then trigger the 
automatic recovery. The recovery ensures that the unit with the latest transaction becomes the 
primary, syncing remaining units to it's state.
 
### Offline units with active cluster

If one or more units get offline, but the cluster primary still available, offline units will keep 
trying to rejoin the cluster indefinitely. If a unit fail to rejoin, this may indicate other issues 
outside the charm control, e.g. persistent network failures.
 
### (Un)graceful unit crash

If any unit crashes ungracefully, e.g. due to a host system crash or mysqld daemon crash, or is gracefully 
restarted, the unit(s) will rejoin the cluster upon daemon restart.

If the crashed unit was the cluster primary in a high availability deployment (3+ units), primary 
failover will take place immediately among remaining mysql units.

For a single unit deployment, there's no immediate failover, but a complete outage recover once 
the unit is back (host or pod restarts).

### Primary crashes before other units are joined

On initial deployment, the Juju leader unit is set as the cluster primary. If this unit crashes 
during the setup and before joining other (secondary) units to the cluster, on unit (pod/host) 
recovery, the charm will execute a complete outage recover for this unit.

## User triggered healing cases

The following cases require user discretion for proper recovery.

### Lost of quorum

The cluster loses its quorum when the primary is lost and the remaining units cannot form a majority to re-elect a new primary.

In this case, the user must decide which of the remaining units will become the new primary.

Refer to the {ref}`Recover from quorum loss <recover-from-quorum-loss>` troubleshooting guide for
 instructions.

### Split-brain

Split-brain can happen on network partitions where the primary is isolated from the quorum and 
later rejoined. 

For example, in a high availability 3 unit deployment, when the primary is isolated 
from the group, the remaining 2 units will elect a new primary. When the old primary rejoins the 
group, still as a primary, the cluster will be in a split-brain state.
