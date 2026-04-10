---
myst:
  html_meta:
    description: "Migrate database data using mysqlsh, with environment preparation."
---

(migrate-data-mysqlsh)=
# Migrate database data via `mysqlsh`

This guide describes how to copy data from a MySQL charm to another MySQL charm, regardless of their version (8.0 / 8.4 / ...).
It does not apply to data migrations from a non charm database, or any legacy type of charm (MariaDB / Percona-cluster / ...).

```{seealso}
* {ref}`migrate-data-mydumper`
* {ref}`migrate-data-mysqldump`
* {ref}`migrate-data-backup-restore`
```

## Prepare

Before migrating data, verify the {ref}`system-requirements`.

```{caution}
Always perform the migration in a test environment before performing it in production!
```

## Prerequisites

- Client machine with access to both deployed charms
- Enough storage in the cluster to support backup/restore of the databases
- `mysql-shell` on client machine (install by running `sudo apt install mysql-shell`)


## Obtain existing database credentials

Get username, password and IP of the existing database:

````{tab-set}
```{tab-item} VM
:sync: vm

When the existing database is a MySQL 8.0 charm:

    OLD_DB_USER=$(juju run mysql/leader get-password username=serverconfig | yq '.username')
    OLD_DB_PASS=$(juju run mysql/leader get-password username=serverconfig | yq '.password')
    OLD_DB_HOST=$(juju show-unit mysql/0 | yq '.[] | .address')

When the existing database is a MySQL 8.4 charm:

    OLD_DB_USER=$(juju run mysql/leader get-password username=charmed-operator | yq '.username')
    OLD_DB_PASS=$(juju run mysql/leader get-password username=charmed-operator | yq '.password')
    OLD_DB_HOST=$(juju show-unit mysql/0 | yq '.[] | .address')
```

```{tab-item} K8s
:sync: k8s

When the existing database is a MySQL 8.0 charm:

    OLD_DB_USER=$(juju run mysql-k8s/leader get-password username=serverconfig | yq '.username')
    OLD_DB_PASS=$(juju run mysql-k8s/leader get-password username=serverconfig | yq '.password')
    OLD_DB_HOST=$(juju show-unit mysql-k8s/0 | yq '.[] | .address')

When the existing database is a MySQL 8.4 charm:

    OLD_DB_USER=$(juju run mysql-k8s/leader get-password username=charmed-operator | yq '.username')
    OLD_DB_PASS=$(juju run mysql-k8s/leader get-password username=charmed-operator | yq '.password')
    OLD_DB_HOST=$(juju show-unit mysql-k8s/0 | yq '.[] | .address')
```
````

### Deploy a new MySQL charm

This step can be skipped if the charm that the data migration will be targeting is already deployed.

To deploy a new MySQL charm database:

````{tab-set}
```{tab-item} VM
:sync: vm

    juju deploy mysql --channel 8.4/edge -n 3
```

```{tab-item} K8s
:sync: k8s

    juju deploy mysql-k8s --channel 8.4/edge -n 3
```
````

## Obtain new database credentials

Get username, password and IP of the new database:

````{tab-set}
```{tab-item} VM
:sync: vm

When the new database is a MySQL 8.0 charm:

    NEW_DB_USER=$(juju run mysql/leader get-password username=serverconfig | yq '.username')
    NEW_DB_PASS=$(juju run mysql/leader get-password username=serverconfig | yq '.password')
    NEW_DB_HOST=$(juju show-unit mysql/0 | yq '.[] | .address')

When the new database is a MySQL 8.4 charm:

    NEW_DB_USER=$(juju run mysql/leader get-password username=charmed-operator | yq '.username')
    NEW_DB_PASS=$(juju run mysql/leader get-password username=charmed-operator | yq '.password')
    NEW_DB_HOST=$(juju show-unit mysql/0 | yq '.[] | .address')
```

```{tab-item} K8s
:sync: k8s

When the new database is a MySQL 8.0 charm:

    NEW_DB_USER=$(juju run mysql-k8s/leader get-password username=serverconfig | yq '.username')
    NEW_DB_PASS=$(juju run mysql-k8s/leader get-password username=serverconfig | yq '.password')
    NEW_DB_HOST=$(juju show-unit mysql-k8s/0 | yq '.[] | .address')

When the new database is a MySQL 8.4 charm:

    NEW_DB_USER=$(juju run mysql-k8s/leader get-password username=charmed-operator | yq '.username')
    NEW_DB_PASS=$(juju run mysql-k8s/leader get-password username=charmed-operator | yq '.password')
    NEW_DB_HOST=$(juju show-unit mysql-k8s/0 | yq '.[] | .address')
```
````

## Migrate database

The next step is to use the credentials and information obtained in previous steps to perform the database migration.
Ensure that there are no new connections are made and that database is not altered.

Connect to the old database to allow dumping files into the local file system:

```shell
mysqlsh --sql \
  --host=${OLD_DB_HOST} \
  --user=${OLD_DB_USER} \
  --password=${OLD_DB_PASS}

SET GLOBAL LOCAL_INFILE=1;
```

Connect to the old database using username, password, and unit's IP address obtained earlier; and dump the instance data.

```shell
mysqlsh --py \
  --host=${OLD_DB_HOST} \
  --user=${OLD_DB_USER} \
  --password=${OLD_DB_PASS}

util.dump_instance('mysql-data.dump', {'threads': 4, 'users': False, 'excludeSchemas': ['mysql_innodb_cluster_metadata']})
```

Connect to the new database using username, password, and unit's IP address obtained earlier; and restore the instance data.

```shell
mysqlsh --py \
  --host=${NEW_DB_HOST} \
  --user=${NEW_DB_USER} \
  --password=${NEW_DB_PASS}

util.load_dump('mysql-data.dump', {'threads': 4})
```
