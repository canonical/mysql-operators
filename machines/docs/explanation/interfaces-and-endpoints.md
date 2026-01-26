# Interfaces and endpoints

Charmed MySQL VM supports the modern `mysql_client` interface (in a backward compatible mode).

## Modern relations

This charm provides the modern [`mysql_client`](https://github.com/canonical/charm-relation-interfaces)interface. Applications can easily connect MySQL using [`data_interfaces`](https://charmhub.io/data-platform-libs/libraries/data_interfaces) library from [`data-platform-libs`](https://github.com/canonical/data-platform-libs/).

### Modern `mysql_client` interface (`database` endpoint)

Adding a [Juju relation](https://documentation.ubuntu.com/juju/3.6/reference/relation/) is accomplished with `juju integrate` via endpoint `database`.

Example:

```shell
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

See details about database user roles in [](/explanation/users).

```{note}
In order to integrate with this charm, every table created by the integrated application must have a primary key. This is required by the [group replication plugin](https://dev.mysql.com/doc/refman/8.0/en/group-replication-requirements.html) enabled in this charm.
```
