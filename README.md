# MySQL operators
[![Charmhub](https://charmhub.io/mysql/badge.svg?channel=8.4/edge)](https://charmhub.io/mysql)
[![Charmhub](https://charmhub.io/mysql-k8s/badge.svg?channel=8.4/edge)](https://charmhub.io/mysql-k8s)
[![Release](https://github.com/canonical/mysql-operators/actions/workflows/release.yaml/badge.svg?branch=8.4/edge)](https://github.com/canonical/mysql-operators/actions/workflows/release.yaml)
[![Tests](https://github.com/canonical/mysql-operators/actions/workflows/ci.yaml/badge.svg?branch=8.4/edge)](https://github.com/canonical/mysql-operators/actions/workflows/ci.yaml)

## Description

The Charmed MySQL Server is a database operator build for the Juju framework. It can be deployed 
on bare metal (using a [LXD](https://canonical.com/lxd) controller) or 
on Kubernetes (using a [microk8s](https://canonical.com/microk8s) controller).

## Usage

Deploying this charm depends on the substrate of choice

### Kubernetes
```shell
juju add-model mysql
juju deploy mysql-k8s --channel 8.4/stable
juju status --watch 1s
```

### Bare metal
```shell
juju add-model mysql
juju deploy mysql --channel 8.4/stable
juju status --watch 1s
```

To remove the deployment, run:
```shell
juju destroy-model mysql --destroy-storage --yes
```

## Documentation

Please follow the tutorial guide ([K8s](https://canonical-charmed-mysql-k8s.readthedocs-hosted.com/tutorial/) or [VM](https://canonical-charmed-mysql.readthedocs-hosted.com/tutorial/)) 
with detailed explanation how to access DB, configure cluster, change credentials and/or enable TLS.

## Relations

Relations are the standard way to interconnect multiple Juju operators.
There relations are defined over well-defined interfaces, that both _requirer_ and _provider_ operators must support.

Example:
```shell
juju add-model mysql
juju deploy mysql --channel 8.4/stable
juju deploy mysql-test-app

# Relate MySQL with your application
juju relate mysql:database mysql-test-app:database
```

#### Interfaces:

- `mysql_client`: standard interface to connect to the database.

## Contributing

To build the charms:

```shell
(cd kubernetes && charmcraft pack)
(cd machines && charmcraft pack)
```

Please see the [Juju SDK docs](https://juju.is/docs/sdk) for guidelines on
enhancements to this charm following best practice guidelines, and [CONTRIBUTING.md](./CONTRIBUTING.md)
for further developer guidance.
