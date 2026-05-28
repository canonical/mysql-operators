---
myst:
  html_meta:
    description: "Migrate database data using mysqldump, with environment preparation and migration checks."
---

(migrate-data-mysqldump)=
# Migrate database data via `mysqldump`

This guide describes how to copy data from a MySQL charm to another MySQL charm, regardless of their version (8.0 / 8.4 / ...).
It does not apply to data migrations from a non charm database, or any legacy type of charm (MariaDB / Percona-cluster / ...).

Note that this guide describes how to migrate database **data** only.

```{seealso}
* {ref}`migrate-data-mydumper`
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
- `mysql-client` on client machine (install by running `sudo apt install mysql-client`)

(mysqldump-obtain-existing-credentials)=
## Obtain existing database credentials

Get username, password and IP of the existing database:

````{tab-set}
```{tab-item} VM
:sync: vm

When the existing database is a MySQL 8.0 charm:

    OLD_DB_USER=$(juju run mysql/leader get-password username=serverconfig | yq '.username')
    OLD_DB_PASS=$(juju run mysql/leader get-password username=serverconfig | yq '.password')
    OLD_DB_HOST=$(juju show-unit mysql/0 | yq '.[].["public-address"]')

When the existing database is a MySQL 8.4 charm:

    OLD_DB_USER=$(juju run mysql/leader get-password username=charmed-operator | yq '.username')
    OLD_DB_PASS=$(juju run mysql/leader get-password username=charmed-operator | yq '.password')
    OLD_DB_HOST=$(juju show-unit mysql/0 | yq '.[].["public-address"]')
```

```{tab-item} K8s
:sync: k8s

When the existing database is a MySQL 8.0 charm:

    OLD_DB_USER=$(juju run mysql-k8s/leader get-password username=serverconfig | yq '.username')
    OLD_DB_PASS=$(juju run mysql-k8s/leader get-password username=serverconfig | yq '.password')
    OLD_DB_HOST=$(juju show-unit mysql-k8s/0 | yq '.[].["address"]')

When the existing database is a MySQL 8.4 charm:

    OLD_DB_USER=$(juju run mysql-k8s/leader get-password username=charmed-operator | yq '.username')
    OLD_DB_PASS=$(juju run mysql-k8s/leader get-password username=charmed-operator | yq '.password')
    OLD_DB_HOST=$(juju show-unit mysql-k8s/0 | yq '.[].["address"]')
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
    NEW_DB_HOST=$(juju show-unit mysql/0 | yq '.[].["public-address"]')

When the new database is a MySQL 8.4 charm:

    NEW_DB_USER=$(juju run mysql/leader get-password username=charmed-operator | yq '.username')
    NEW_DB_PASS=$(juju run mysql/leader get-password username=charmed-operator | yq '.password')
    NEW_DB_HOST=$(juju show-unit mysql/0 | yq '.[].["public-address"]')
```

```{tab-item} K8s
:sync: k8s

When the new database is a MySQL 8.0 charm:

    NEW_DB_USER=$(juju run mysql-k8s/leader get-password username=serverconfig | yq '.username')
    NEW_DB_PASS=$(juju run mysql-k8s/leader get-password username=serverconfig | yq '.password')
    NEW_DB_HOST=$(juju show-unit mysql-k8s/0 | yq '.[].["address"]')

When the new database is a MySQL 8.4 charm:

    NEW_DB_USER=$(juju run mysql-k8s/leader get-password username=charmed-operator | yq '.username')
    NEW_DB_PASS=$(juju run mysql-k8s/leader get-password username=charmed-operator | yq '.password')
    NEW_DB_HOST=$(juju show-unit mysql-k8s/0 | yq '.[].["address"]')
```
````

## Migrate database

The next step is to use the credentials and information obtained in previous steps to perform the database migration.
Ensure that there are no new connections are made and that database is not altered.

Connect to the legacy database to verify the connection:

```shell
mysql \
  --host=${OLD_DB_HOST} \
  --user=${OLD_DB_USER} \
  --password=${OLD_DB_PASS} \
  -e "show databases"
```

Choose which databases to dump/migrate to the new charm (one by one!)

```shell
DB_NAME=< e.g. wordpress >
```

Create a backup of each database file using the `mysqldump` utility, username, password, and unit's IP address, obtained earlier. This will create a dump that can be used to restore the database.

```shell
OLD_DB_DUMP="legacy-mysql-${DB_NAME}.sql"

mysqldump \
  --host=${OLD_DB_HOST} \
  --user=${OLD_DB_USER} \
  --password=${OLD_DB_PASS} \
  --column-statistics=0 \
  --databases ${OLD_DB_NAME} \
  > "${OLD_DB_DUMP}"
```

Connect to the new database using username, password, and unit's IP address, and restore database from backup:

```shell
mysql \
  --host=${NEW_DB_HOST} \
  --user=${NEW_DB_USER} \
  --password=${NEW_DB_PASS} \
  < "${OLD_DB_DUMP}"
```

## Integrate with modern charm

Integrate your application and new MySQL database charm (using the `database` endpoint):

````{tab-set}
```{tab-item} VM
:sync: vm

    juju integrate <your_application> mysql:database
```

```{tab-item} K8s
:sync: k8s

    juju integrate <your_application> mysql-k8s:database
```
````

## Verify database migration

Create a dump for the new MySQL database and compare it to the backup created earlier:

```shell
NEW_DB_DUMP="new-mysql-${DB_NAME}.sql"
mysqldump \
  --host=${NEW_DB_HOST} \
  --user=${NEW_DB_USER} \
  --password=${NEW_DB_PASS} \
  --column-statistics=0 \
  --databases ${DB_NAME} \
  > "${NEW_DB_DUMP}"

diff "${OLD_DB_DUMP}" "${NEW_DB_DUMP}"
```

The difference between two SQL backup files should be limited to server versions, IP addresses, timestamps and other non data related information. 

````{dropdown} Example

```shell
diff "${OLD_DB_DUMP}" "${NEW_DB_DUMP}"
```

Output:

```text
< -- Host: 10.1.45.226 Database: katib
---
> -- Host: 10.1.46.40 Database: katib
5c5
< -- Server version 5.5.5-10.3.17-MariaDB-1:10.3.17+maria~bionic
---
> -- Server version 8.4.7-0ubuntu0.26.04.1
16a17,26
> SET @MYSQLDUMP_TEMP_LOG_BIN = @@SESSION.SQL_LOG_BIN;
> SET @@SESSION.SQL_LOG_BIN= 0;
>
> --
> -- GTID state at the beginning of the backup
> --
>
> SET @@GLOBAL.GTID_PURGED=/*!80000 '+'*/ '0d3210b9-587f-11ee-acf3-b26305f815ec:1-4,
> 34442d83-587f-11ee-84f5-b26305f815ec:1-85,
> 34444583-587f-11ee-84f5-b26305f815ec:1';
22c32
< CREATE DATABASE /*!32312 IF NOT EXISTS*/ `katib` /*!40100 DEFAULT CHARACTER SET latin1 */;
---
> CREATE DATABASE /*!32312 IF NOT EXISTS*/ `katib` /*!40100 DEFAULT CHARACTER SET latin1 */ /*!80016 DEFAULT ENCRYPTION='N' */;
34c44
< `id` int(11) NOT NULL,
---
> `id` int NOT NULL,
60c70
< `id` int(11) NOT NULL AUTO_INCREMENT,
---
> `id` int NOT NULL AUTO_INCREMENT,
75a86
> SET @@SESSION.SQL_LOG_BIN = @MYSQLDUMP_TEMP_LOG_BIN;
86c97
< -- Dump completed on 2023-09-21 17:05:54
---
> -- Dump completed on 2023-09-21 17:09:40
```
````

## Remove old databases

Test your application and if you are happy with a data migration, do not forget to remove legacy charms to keep the house clean:

```shell
juju remove-application --destroy-storage <old_charm>
```
