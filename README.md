# MySQL operators
[![Charmhub](https://charmhub.io/mysql/badge.svg)](https://charmhub.io/mysql)
[![Charmhub](https://charmhub.io/mysql-k8s/badge.svg)](https://charmhub.io/mysql-k8s)
[![Release](https://github.com/canonical/mysql-operators/actions/workflows/release.yaml/badge.svg?branch=8.0/edge)](https://github.com/canonical/mysql-operators/actions/workflows/release.yaml)
[![Tests](https://github.com/canonical/mysql-operators/actions/workflows/ci.yaml/badge.svg?branch=8.0/edge)](https://github.com/canonical/mysql-operators/actions/workflows/ci.yaml)

## Description

The Charmed MySQL Server is a database operator build for the Juju framework. It can be deployed 
on bare metal (using a [LXD](https://canonical.com/lxd) controller) or 
on Kubernetes (using a [microk8s](https://canonical.com/microk8s) controller).

## Usage

Deploying this charm depends on the substrate of choice

### Kubernetes
```shell
juju add-model mysql
juju deploy mysql-k8s --channel 8.0/stable
juju status --watch 1s
```

### Bare metal
```shell
juju add-model mysql
juju deploy mysql --channel 8.0/stable
juju status --watch 1s
```

To remove the deployment, run:
```shell
juju destroy-model mysql --destroy-storage --yes
```

## Documentation

See the [official documentation](https://canonical-charmed-mysql.readthedocs-hosted.com/) for more operational guidance, such as deployment on specific clouds, TLS, monitoring, backups, and troubleshooting.

## Relations

Relations are the standard way to interconnect multiple Juju operators.
There relations are defined over well-defined interfaces, that both _requirer_ and _provider_ operators must support.

Example:
```shell
juju add-model mysql
juju deploy mysql --channel 8.0/stable
juju deploy mysql-test-app

# Relate MySQL with your application
juju relate mysql:database mysql-test-app:database
```

#### Modern interfaces:

- `mysql_client`: standard interface to connect to the database.

### Legacy interfaces

- `mysql`: popular interface used by some legacy charms.
- `mysql-router`: interface that once used the MySQL Router charm.
- `mysql-shared`: interface that allow direct access to the database cluster.

**Note:** Legacy interfaces are deprecated and will be discontinued on future releases. Usage should be avoided.

## Contributing

To build the charms:

```shell
(cd kubernetes && charmcraft pack)
(cd machines && charmcraft pack)
```

Please see the [Juju SDK docs](https://juju.is/docs/sdk) for guidelines on
enhancements to this charm following best practice guidelines, and [CONTRIBUTING.md](./CONTRIBUTING.md)
for further developer guidance.
