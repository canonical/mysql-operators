---
myst:
  html_meta:
    description: "Roll back a failed Charmed MySQL upgrade to a previous revision using prepare, rollback, and post-rollback health check steps."
---

(roll-back-single-cluster)=
# How to roll back a single cluster

After a `juju refresh`, if there are any version incompatibilities in charm revisions, its dependencies, or any other unexpected failure in the refresh process, the process will be halted and enter a failure state.

Even if the underlying MySQL cluster continues to work, it’s important to roll back the charm to a previous revision so that an update can be attempted after further inspection of the failure.

```{warning}
Do NOT trigger `rollback` during a running `refresh` action! It may cause an  unpredictable MySQL cluster state!
```

This guide covers rollbacks for single cluster MySQL deployments. Before rolling back a **multi-cluster** refresh, see {ref}`refresh-multi-cluster`.

## Summary of the rollback steps

1. **Prepare** the Charmed MySQL application for the in-place rollback.
2. **Roll back**. Once started, all units in a cluster will be executed sequentially. The rollback will be aborted (paused) if the unit rollback has failed.
3. **Check**. Make sure the charm and cluster are in healthy state again.

## Step 1: Prepare

To execute a rollback, we use a similar procedure to the refresh. The difference is the charm revision to refresh to. In this guide's example, we will refresh the charm back to revision `312`.

It is necessary to re-run `pre-upgrade-check` action on the leader unit in order to enter the refresh recovery state:

````{tab-set}
```{tab-item} VM
:sync: vm

    juju run mysql/leader pre-upgrade-check
```

```{tab-item} K8s
:sync: k8s

    juju run mysql-k8s/leader pre-upgrade-check
```
````


## Step 2: Rollback

````{tab-set}
```{tab-item} VM
:sync: vm

When refreshing a charm from **Charmhub**:

    juju refresh mysql --revision=<revision_number>

When deploying from a **local charm file**, one must have the previous revision charm file and run the following command:

    juju refresh mysql --path=./mysql_ubuntu-22.04-amd64.charm

where `mysql_ubuntu-22.04-amd64.charm` is the previous revision charm file.
```

```{tab-item} K8s
:sync: k8s

When refreshing a charm from **Charmhub**:

    juju refresh mysql-k8s --revision=<revision_number>

When deploying from a **local charm file**, one must have the previous revision charm file and the `mysql-image` resource, then run:

    juju refresh mysql-k8s --path=<path to charm file> --resource mysql-image=<image URL>

For example:

    juju refresh mysql-k8s --path=./mysql-k8s_ubuntu-22.04-amd64.charm \
        --resource mysql-image=ghcr.io/canonical/charmed-mysql@sha256:753477ce39712221f008955b746fcf01a215785a215fe3de56f525380d14ad97

where `mysql-k8s_ubuntu-22.04-amd64.charm` is the previous revision charm file.

The reference for the resource for a given revision can be found in the [`metadata.yaml`](https://github.com/canonical/mysql-operators/blob/218fc72c49156c0de979f55ff1928de41eb42708/kubernetes/metadata.yaml#L34) file in the charm's repository under the key `upstream-source`.
```
````

The first unit will be rolled out and should rejoin the cluster after settling down. After the `refresh` command, the juju controller revision for the application will be back in sync with the running Charmed MySQL revision.

## Step 3: Check

Check `juju status` to make sure the cluster {ref}`charm-statuses` is OK.
