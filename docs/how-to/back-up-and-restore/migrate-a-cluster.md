(migrate-a-cluster)=
# How to migrate a cluster

This guide describes how to restore a backup that was made from a different cluster, (i.e. cluster migration via restore).

```{seealso}
To perform a basic restore from a *local* backup, see {ref}`restore-a-backup`.
```

## Prerequisites

* A MySQL deployment {ref}`scaled down <scale>` to one unit (scale it up after the backup is restored)
* A {ref}`backup <create-a-backup>` from the previous cluster in your S3 storage
* Passwords from your previous cluster

## Set cluster passwords

When you restore a backup from an old cluster, it will restore the password from the previous cluster to your current cluster.

Set the password of your current cluster to the previous cluster’s password:

````{tab-set}
```{tab-item} VM
:sync: vm

    juju run mysql/leader set-password username=root password=<previous cluster password>
    juju run mysql/leader set-password username=clusteradmin password=<previous cluster password>
    juju run mysql/leader set-password username=serverconfig password=<previous cluster password>
```

```{tab-item} K8s
:sync: k8s

    juju run mysql-k8s/leader set-password username=root password=<previous cluster password>
    juju run mysql-k8s/leader set-password username=clusteradmin password=<previous cluster password>
    juju run mysql-k8s/leader set-password username=serverconfig password=<previous cluster password>
```
````

## Restore cluster

To view the available backups to restore you can enter the command `list-backups`:

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

Take note of the `backup-id` that corresponds to the previous cluster.

Run the `restore` command with your `backup-id`:

````{tab-set}
```{tab-item} VM
:sync: vm

    juju run mysql/leader restore backup-id=YYYY-MM-DDTHH:MM:SSZ
```

```{tab-item} K8s
:sync: k8s

    juju run mysql-k8s/leader restore backup-id=YYYY-MM-DDTHH:MM:SSZ
```
````
Your restore will then be in progress, once it is complete your cluster will represent the state of the previous cluster.

