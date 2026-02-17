(interfaces-and-endpoints)=
# Interfaces and endpoints

Charmed MySQL supports modern `mysql_client` and legacy `mysql`, `mysql-shared`, `mysql-router` interfaces (in a backward compatible mode).

|        | Interface      | Endpoints             | VM charm | K8s charm |
|--------|----------------|-----------------------|----------|-----------|
| modern | `mysql_client` | `database`            | ![check] | ![check]  |
| legacy | `mysql`        | `mysql`, `mysql-root` | ![check] | ![check]  |
| legacy | `mysql-router` | `db-router`           | ![check] |           |
| legacy | `mysql-shared` | `shared-db`           | ![check] |           |

```{caution}
Do **not** relate both modern and legacy interfaces simultaneously.
```

## Modern relations

This charm provides the modern [`mysql_client`](https://github.com/canonical/charm-relation-interfaces)interface. Applications can easily connect MySQL using [`data_interfaces`](https://charmhub.io/data-platform-libs/libraries/data_interfaces) library from [`data-platform-libs`](https://github.com/canonical/data-platform-libs/).

### Modern `mysql_client` interface (`database` endpoint)

Adding a [Juju relation](https://documentation.ubuntu.com/juju/3.6/reference/relation/) is accomplished with `juju integrate` via endpoint `database`.

Example:

````{tab-set}
```{tab-item} VM
:sync: vm

    # Deploy Charmed MySQL cluster with 3 nodes
    juju deploy mysql -n 3 --channel 8.0

    # Deploy the relevant charms, e.g. mysql-test-app
    juju deploy mysql-test-app

    # Integrate (relate) MySQL with your application
    juju integrate mysql:database mysql-test-app:database

    # Check established relation (using mysql_client interface):
    juju status --relations

    # Example of the properly established relation:
    # > Relation provider   Requirer                 Interface     Type
    # > mysql:database      mysql-test-app:database  mysql_client  regular
```

```{tab-item} K8s
:sync: k8s

    # Deploy Charmed MySQL cluster with 3 nodes
    juju deploy mysql-k8s -n 3 --trust --channel 8.0

    # Deploy the relevant charms, e.g. mysql-test-app
    juju deploy mysql-test-app

    # Relate MySQL with your application
    juju relate mysql-k8s:database mysql-test-app:database

    # Check established relation (using mysql_client interface):
    juju status --relations

    # Example of the properly established relation:
    # > Relation provider      Requirer                 Interface     Type
    # > mysql-k8s:database     mysql-test-app:database  mysql_client  regular
```
````

See details about database user roles in {ref}`users`.

```{note}
In order to integrate with this charm, every table created by the integrated application must have a primary key. This is required by the [group replication plugin](https://dev.mysql.com/doc/refman/8.0/en/group-replication-requirements.html) enabled in this charm.
```

## Legacy relations

**Legacy relations are deprecated and will be discontinued** in future releases. Their usage should be avoided. 

Check the legacy interface implementation limitations in {ref}`legacy-charm`.

This charm supports several legacy interfaces, e.g. `mysql`, `mysql-shared`, `mysql-router`. They were used in some legacy charms in [cross-model relations](https://documentation.ubuntu.com/juju/3.6/reference/relation/#cross-model-relation).

### `mysql` interface, `mysql` and `mysql-root` endpoints

It was a popular interface used by some legacy charms (e.g. [MariaDB](https://charmhub.io/mariadb), [OSM MariaDB](https://charmhub.io/charmed-osm-mariadb-k8s), [Percona Cluster](https://charmhub.io/percona-cluster) and [MySQL Innodb Cluster](https://charmhub.io/mysql-innodb-cluster)), often in [cross-model relations](https://documentation.ubuntu.com/juju/3.6/reference/relation/#cross-model-relation).

Example usage of this interface:

````{tab-set}
```{tab-item} VM
:sync: vm

    juju deploy mysql --channel 8.0
    juju config mysql mysql-interface-database=mediawiki mysql-interface-user=mediawiki
    juju deploy mediawiki
    juju integrate mysql:mysql mediawiki:db
```

```{tab-item} K8s
:sync: k8s

    juju deploy mysql-k8s --trust --channel 8.0
    juju config mysql-k8s mysql-interface-database=wordpress mysql-interface-user=wordpress
    juju deploy wordpress-k8s
    juju relate mysql-k8s:mysql wordpress-k8s:db
```
````

```{caution}
The endpoint `mysql-root` provides the same legacy interface `mysql` with MySQL root-level privileges. It is NOT recommended to use it from security point of view.
```

### `mysql-router` interface, `db-router` endpoint (VM only)

It is a relation that one uses with the [mysql router](https://charmhub.io/mysql-router) charm. 

As an example, the following commands can be executed to deploy and integrate Charmed MySQL VM to the keystone charm:

```shell
juju deploy mysql --channel 8.0
juju deploy mysql-router --series focal
juju deploy keystone --series focal
juju integrate mysql-router keystone
juju integrate mysql:db-router mysql-router:db-router
```

```{note}
Make sure to deploy identical [series/base](https://documentation.ubuntu.com/juju/3.6/reference/machine/#machine-base) for `keystone` and `mysql-router` applications.

This is necessary due to the [subordinate](https://documentation.ubuntu.com/juju/3.6/reference/charm/#subordinate-charm) charm nature of `mysql-router`.
```

### `mysql-shared` interface, `shared-db` endpoint (VM only) 

It is a relation that one uses when the application needs to connect directly to the database cluster. It is supported by various legacy charms, e.g. [mysql-innodb-cluster](https://charmhub.io/mysql-innodb-cluster). 

As an example, the following commands can be executed to deploy and integrate Charmed MySQL VM to the keystone charm:

```shell
juju deploy mysql --channel 8.0
juju deploy keystone --series focal
juju integrate keystone:shared-db mysql:shared-db
```

<!--BADGES-->

[check]: https://img.icons8.com/color/20/checkmark--v1.png