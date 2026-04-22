---
myst:
  html_meta:
    description: "Migrate MySQL data using mydumper and myloader: install tools, dump from source with serverconfig credentials, and import into Charmed MySQL."
---

(migrate-data-mydumper)=
# Migrate data via mydumper

[mydumper](https://github.com/mydumper/mydumper) is a powerful MySQL logical data-migration tool. It includes

* `mydumper` - responsible to export a consistent of MySQL databases
* `myloader` - reads the dump from mydumper, connects the to destination database and imports the data

Both tools use multi-threading capabilities and support S3 storage to write/read dumps. <!--MyDumper is Open Source and maintained by the community, it is not a Percona, MariaDB, MySQL or Canonical product.-->

```{seealso}
For data stored in legacy charms, see {ref}`migrate-data-mysqldump`
```

## Prepare

Before migrating data:

* Verify the {ref}`system-requirements`
* Verify your application's {ref}`compatibility <legacy-charm>` with Charmed MySQL

## Install `mydumper`

Install the latest version from [GitHub](https://github.com/mydumper/mydumper/releases):

```shell
wget https://github.com/mydumper/mydumper/releases/download/v0.15.1-3/mydumper_0.15.1-3.jammy_amd64.deb && \
sudo apt install ./mydumper_0.15.1-3.jammy_amd64.deb
```

## Dump database

Dump database using Charmed MySQL operator user `serverconfig`:

````{tab-set}
```{tab-item} VM
:sync: vm

    # Collect credentials
    DB_NAME=<your_db_name>
    OLD_DB_IP=$(juju show-unit mysql/0 | yq '.[].["public-address"]')
    OLD_DB_PASS=$(juju run mysql/leader get-password username=${OLD_DB_USER}| yq '.username')
    OLD_DB_PASS=$(juju run mysql/leader get-password username=${OLD_DB_USER}| yq '.password')

    # Test connection
    mysql -h ${OLD_DB_IP} -u ${OLD_DB_USER} --password=${OLD_DB_PASS} ${DB_NAME}

    # Dump database using mydumper
    mydumper -h ${OLD_DB_IP} -u ${OLD_DB_USER} -p ${OLD_DB_PASS} -B ${DB_NAME}
```

```{tab-item} K8s
:sync: k8s

    # Collect credentials
    DB_NAME=<your_db_name>
    OLD_DB_IP=$(juju show-unit mysql-k8s/0 | yq '.[].["address"]')
    OLD_DB_PASS=$(juju run mysql-k8s/leader get-password username=${OLD_DB_USER}| yq '.username')
    OLD_DB_PASS=$(juju run mysql-k8s/leader get-password username=${OLD_DB_USER}| yq '.password')

    # Test connection
    mysql -h ${OLD_DB_IP} -u ${OLD_DB_USER} --password=${OLD_DB_PASS} ${DB_NAME}

    # Dump database using mydumper
    mydumper -h ${OLD_DB_IP} -u ${OLD_DB_USER} -p ${OLD_DB_PASS} -B ${DB_NAME}
```
````

```{admonition} Juju 2.9 users
:class: tip

Remember that `juju run <action name>` becomes `juju run-action <action name> --wait`.

See also: {ref}`breaking-changes-juju`
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

## Restore

```shell
NEW_DB_IP=...
NEW_DB_USER=serverconfig
NEW_DB_PASS=...

myloader -h ${NEW_DB_IP} -u ${NEW_DB_USER} -p ${NEW_DB_PASS} --directory=export-20230927-123337 --overwrite-tables
```
