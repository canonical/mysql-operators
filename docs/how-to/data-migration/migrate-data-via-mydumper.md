---
myst:
  html_meta:
    description: "Migrate MySQL data using mydumper: install tools, dump and import into Charmed MySQL."
---

(migrate-data-mydumper)=
# Migrate database data via `mydumper`

This guide describes how to copy data from a MySQL charm to another MySQL charm, regardless of their version (8.0 / 8.4 / ...).
It does not apply to data migrations from a non charm database, or any legacy type of charm (MariaDB / Percona-cluster / ...).

```{seealso}
* {ref}`migrate-data-mysqldump`
* {ref}`migrate-data-mysqlsh`
* {ref}`migrate-data-backup-restore`
```

## Prepare

Before migrating data, verify the {ref}`system-requirements`.

```{caution}
Always perform the migration in a test environment before performing it in production!
```

## Prerequisites

- Client machine with access to deployed legacy charm
- Enough storage in the cluster to support backup/restore of the databases
- `mydumper` on client machine (install the latest version from [GitHub](https://github.com/mydumper/mydumper/releases)):

```shell
wget https://github.com/mydumper/mydumper/releases/download/v0.15.1-3/mydumper_0.15.1-3.jammy_amd64.deb && \
sudo apt install ./mydumper_0.15.1-3.jammy_amd64.deb
```

## Obtain existing database credentials

Get username, password and IP of the existing database:

````{tab-set}
```{tab-item} VM
:sync: vm

When the existing database is a MySQL 8.0 charm:

    OLD_DB_USER=$(juju run mysql-80/leader get-password username=serverconfig | yq '.username')
    OLD_DB_PASS=$(juju run mysql-80/leader get-password username=serverconfig | yq '.password')
    OLD_DB_HOST=$(juju show-unit mysql-80/0 | yq '.[] | .address')

When the existing database is a MySQL 8.4 charm:

    OLD_DB_USER=$(juju run mysql-84/leader get-password username=charmed-operator | yq '.username')
    OLD_DB_PASS=$(juju run mysql-84/leader get-password username=charmed-operator | yq '.password')
    OLD_DB_HOST=$(juju show-unit mysql-84/0 | yq '.[] | .address')
```

```{tab-item} K8s
:sync: k8s

When the existing database is a MySQL 8.0 charm:

    OLD_DB_USER=$(juju run mysql-k8s-80/leader get-password username=serverconfig | yq '.username')
    OLD_DB_PASS=$(juju run mysql-k8s-80/leader get-password username=serverconfig | yq '.password')
    OLD_DB_HOST=$(juju show-unit mysql-k8s-80/0 | yq '.[] | .address')

When the existing database is a MySQL 8.4 charm:

    OLD_DB_USER=$(juju run mysql-k8s-84/leader get-password username=charmed-operator | yq '.username')
    OLD_DB_PASS=$(juju run mysql-k8s-84/leader get-password username=charmed-operator | yq '.password')
    OLD_DB_HOST=$(juju show-unit mysql-k8s-84/0 | yq '.[] | .address')
```
````

### Deploy a new MySQL charm

This step can be skipped if the charm that the data migration will be targeting is already deployed.

To deploy a new MySQL charm database:

````{tab-set}
```{tab-item} VM
:sync: vm

    # Use any of the stable channels
    # juju deploy mysql --channel 8.0/stable -n 3
    # juju deploy mysql --channel 8.4/stable -n 3
```

```{tab-item} K8s
:sync: k8s

    # Use any of the stable channels
    # juju deploy mysql-k8s --channel 8.0/stable -n 3
    # juju deploy mysql-k8s --channel 8.4/stable -n 3
```
````

## Obtain new database credentials

Get username, password and IP of the new database:

````{tab-set}
```{tab-item} VM
:sync: vm

When the new database is a MySQL 8.0 charm:

    NEW_DB_USER=$(juju run mysql-80/leader get-password username=serverconfig | yq '.username')
    NEW_DB_PASS=$(juju run mysql-80/leader get-password username=serverconfig | yq '.password')
    NEW_DB_HOST=$(juju show-unit mysql-80/0 | yq '.[] | .address')

When the new database is a MySQL 8.4 charm:

    NEW_DB_USER=$(juju run mysql-84/leader get-password username=charmed-operator | yq '.username')
    NEW_DB_PASS=$(juju run mysql-84/leader get-password username=charmed-operator | yq '.password')
    NEW_DB_HOST=$(juju show-unit mysql-84/0 | yq '.[] | .address')
```

```{tab-item} K8s
:sync: k8s

When the new database is a MySQL 8.0 charm:

    NEW_DB_USER=$(juju run mysql-k8s-80/leader get-password username=serverconfig | yq '.username')
    NEW_DB_PASS=$(juju run mysql-k8s-80/leader get-password username=serverconfig | yq '.password')
    NEW_DB_HOST=$(juju show-unit mysql-k8s-80/0 | yq '.[] | .address')

When the new database is a MySQL 8.4 charm:

    NEW_DB_USER=$(juju run mysql-k8s-84/leader get-password username=charmed-operator | yq '.username')
    NEW_DB_PASS=$(juju run mysql-k8s-84/leader get-password username=charmed-operator | yq '.password')
    NEW_DB_HOST=$(juju show-unit mysql-k8s-84/0 | yq '.[] | .address')
```
````

## Migrate database

Dump database using the existing Charmed MySQL operator username, password and IP:

```shell
mydumper -h ${OLD_DB_HOST} -u ${OLD_DB_USER} -p ${OLD_DB_PASS} -B <your_db_name>
```

The content of the database dump is stored in a newly created folder, e.g. `export-20230927-123337` (which can be stored on S3-compatible storage):

```shell
> ls -la export-20230927-123337
drwxr-x---  2 ubuntu ubuntu   4096 Sep 27 12:33 .
drwxr-x--- 18 ubuntu ubuntu   4096 Sep 27 12:34 ..
-rw-rw-r--  1 ubuntu ubuntu    175 Sep 27 12:33 your_db_name-schema-create.sql
-rw-rw-r--  1 ubuntu ubuntu      0 Sep 27 12:33 your_db_name-schema-triggers.sql
-rw-rw-r--  1 ubuntu ubuntu    298 Sep 27 12:33 your_db_name.data-schema.sql
-rw-rw-r--  1 ubuntu ubuntu 124131 Sep 27 12:33 your_db_name.data.00000.sql
-rw-rw-r--  1 ubuntu ubuntu    314 Sep 27 12:33 your_db_name.random_data-schema.sql
-rw-rw-r--  1 ubuntu ubuntu    153 Sep 27 12:33 your_db_name.random_data.00000.sql
-rw-rw-r--  1 ubuntu ubuntu    499 Sep 27 12:33 metadata
```

Restore database using the new Charmed MySQL operator username, password and IP:

```shell
myloader -h ${NEW_DB_HOST} -u ${NEW_DB_USER} -p ${NEW_DB_PASS} --directory=export-20230927-123337 --overwrite-tables
```
