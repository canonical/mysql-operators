(create-a-backup)=
# How to create a backup

This guide contains recommended steps and useful commands for creating and managing backups to ensure smooth restores.

## Prerequisites

* [Configured settings for S3 storage](/how-to/back-up-and-restore/configure-s3-aws)

---

## Create a backup

Once `juju status` shows Charmed MySQL as `active` and `idle`, you can create your first backup with the `create-backup` command:

````{tab-set}
```{tab-item} VM
:sync: vm

    juju run mysql/leader create-backup
```

```{tab-item} K8s
:sync: k8s

    juju run mysql-k8s/leader create-backup
```
````

If you have a cluster of one unit, you can run the `create-backup` action on the leader (which will also be the primary unit). Otherwise, you must run the `create-backup` action on a non-primary unit. 

To find the primary, see `juju status` or run `get-cluster-status` on the leader to find the primary unit.

The `create-backup` action validates that the unit in charge of the backup is healthy, by:
- Checking that the MySQL cluster is in a valid state (`OK` or `OK_PARTIAL` from the InnoDB [cluster status](https://dev.mysql.com/doc/mysql-shell/8.0/en/monitoring-innodb-cluster.html))
- Checking that the MySQL instance is in a valid state (`ONLINE` from Replication [member states](https://dev.mysql.com/doc/refman/8.0/en/group-replication-server-states.html).

In order to override these precautions, use the `force` flag:

````{tab-set}
```{tab-item} VM
:sync: vm

    juju run mysql/leader create-backup force=True
```

```{tab-item} K8s
:sync: k8s

    juju run mysql-k8s/leader create-backup force=True
```
````

## List backups

You can list your available, failed, and in progress backups by running the `list-backups` command:

````{tab-set}
```{tab-item} VM
:sync: vm

    juju run mysql/leader list-backups
```

```{tab-item} K8s
:sync: k8s

    juju run mysql-k8s/leader list-backups
```
````