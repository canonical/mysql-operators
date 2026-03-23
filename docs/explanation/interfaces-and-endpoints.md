---
myst:
  html_meta:
    description: "Reference for Charmed MySQL interfaces and endpoints, including mysql_client and legacy mysql, mysql-shared, and mysql-router interfaces."
---

(interfaces-and-endpoints)=
# Interfaces and endpoints

Charmed MySQL 8.4 supports the modern `mysql_client` interface. 

|        | Interface      | Endpoints             | VM charm | K8s charm |
|--------|----------------|-----------------------|----------|-----------|
| modern | `mysql_client` | `database`            | ![check] | ![check]  |

It does NOT support legacy `mysql`, `mysql-shared`, `mysql-router` interfaces. For information about legacy interfaces, see the [Charmed MySQL 8.0 documentation](https://canonical-charmed-mysql.readthedocs-hosted.com/8.0/explanation/interfaces-and-endpoints/)

## Modern relations

This charm provides the modern [`mysql_client`](https://github.com/canonical/charm-relation-interfaces)interface. Applications can easily connect MySQL using [`data_interfaces`](https://charmhub.io/data-platform-libs/libraries/data_interfaces) library from [`data-platform-libs`](https://github.com/canonical/data-platform-libs/).

### `mysql_client` interface, `database` endpoint

Adding a [Juju relation](https://documentation.ubuntu.com/juju/3.6/reference/relation/) is accomplished with `juju integrate` via endpoint `database`.

Example:

````{tab-set}
```{tab-item} VM
:sync: vm

    # Deploy Charmed MySQL cluster with 3 nodes
    juju deploy mysql -n 3 --channel 8.4/edge

    # Deploy the relevant charms, e.g. mysql-test-app
    juju deploy mysql-test-app

    # Relate MySQL with your application
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
    juju deploy mysql-k8s -n 3 --trust --channel 8.4/edge

    # Deploy the relevant charms, e.g. mysql-test-app
    juju deploy mysql-test-app

    # Relate MySQL with your application
    juju integrate mysql-k8s:database mysql-test-app:database

    # Check established relation (using mysql_client interface):
    juju status --relations

    # Example of the properly established relation:
    # > Relation provider      Requirer                 Interface     Type
    # > mysql-k8s:database     mysql-test-app:database  mysql_client  regular
```
````

See details about database user roles in {ref}`users`.

```{note}
In order to integrate with this charm, every table created by the integrated application must have a primary key. This is required by the [group replication plugin](https://dev.mysql.com/doc/refman/8.4/en/group-replication-requirements.html) enabled in this charm.
```

## Legacy relations

**Legacy relations are deprecated and will be discontinued** from Charmed MySQL 8.4 onward. Their usage should be avoided.

For information about legacy interfaces, see the [Charmed MySQL 8.0 documentation](https://canonical-charmed-mysql.readthedocs-hosted.com/8.0/explanation/interfaces-and-endpoints/)

<!--BADGES-->

[check]: https://img.icons8.com/color/20/checkmark--v1.png