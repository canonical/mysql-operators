---
myst:
  html_meta:
    description: "Upgrade a Charmed MySQL ClusterSet by refreshing each cluster starting with standbys and ending with the primary to minimize disruption."
---

(refresh-multi-cluster)=
# How to refresh a multi-cluster deployment

A MySQL multi-cluster deployment (also known as a cluster set) can be upgraded by performing a refresh of each cluster individually.

This guide goes over the steps and important considerations before refreshing multiple MySQL clusters.

## Determine cluster order

To upgrade a multi-cluster deployment, each cluster must be refreshed one by one - starting with the standby clusters.

**The primary cluster must be the last one to get refreshed.**

This ensures that availability is not affected if there are any issues with the upgrade. Refreshing all the standbys first also minimizes the cost of the leader re-election process.

To identify the primary cluster, run

````{tab-set}
```{tab-item} VM
:sync: vm

    juju run mysql/<n> get-cluster-status cluster-set=true
```

```{tab-item} K8s
:sync: k8s

    juju run mysql-k8s/<n> get-cluster-status cluster-set=true
```
````

```{admonition} Juju 2.9 users
:class: tip

Remember that `juju run <action name>` becomes `juju run-action <action name> --wait`.

See also: {ref}`breaking-changes-juju`
```

## Refresh each cluster

For each cluster, follow the instructions in {ref}`refresh-single-cluster`.

**Perform a health check before proceeding to the next cluster.**

Use the `get-cluster-status` Juju action to check that everything is healthy after refreshing a cluster.

## Roll back

If something goes wrong, roll back the cluster. See: {ref}`roll-back-single-cluster`.
