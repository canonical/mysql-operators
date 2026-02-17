(restore-a-backup)=
# How to restore a local backup

This is a guide for performing a basic restore (restoring a locally made backup).

To restore a backup that was made from the a *different* cluster, (i.e. cluster migration via restore), see [](/how-to/back-up-and-restore/migrate-a-cluster).

## Prerequisites

- A MySQL deployment {ref}`scaled down <scale>` to one unit (scale it up after the backup is restored)
- [A backup in your S3 storage](/how-to/back-up-and-restore/create-a-backup)
- {ref}`point-in-time-recovery` recovery requires the following MySQL charm revisions:
  * VM charm
    * rev368+ for `amd64`
    * rev369+ for `arm64`
  * K8s charm
    * rev249+ for `amd64`
    * rev248+ for `arm64`

---

## List backups

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

This should show your available backups
```shell
backups: |-
  backup-id             | backup-type  | backup-status
  ----------------------------------------------------
  YYYY-MM-DDTHH:MM:SSZ  | physical     | finished
```

## Restore a backup

To restore a backup from that list, run the `restore` command and pass the `backup-id` to restore:

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

Your restore will then be in progress.

(point-in-time-recovery)=
## Point-in-time recovery

Point-in-time recovery (PITR) is a MySQL feature that enables restorations to the database state at specific points in time. The feature is enabled by default when there's a working relation with S3 storage.

To restore to a specific point in time between different backups (e.g. to restore only specific transactions made between those backups), use the `restore-to-time` parameter to pass a timestamp:

````{tab-set}
```{tab-item} VM
:sync: vm

    juju run mysql/leader restore restore-to-time="YYYY-MM-DD HH:MM:SS"
```

```{tab-item} K8s
:sync: k8s

    juju run mysql-k8s/leader restore restore-to-time="YYYY-MM-DD HH:MM:SS"
```
````

Your restore will then be in progress.

It’s also possible to restore to the latest point from a specific timeline by passing the ID of a backup taken on that timeline and `restore-to-time=latest` when requesting a restore:

````{tab-set}
```{tab-item} VM
:sync: vm

    juju run mysql/leader restore restore-to-time=latest
```

```{tab-item} K8s
:sync: k8s

    juju run mysql-k8s/leader restore restore-to-time=latest
```
````

