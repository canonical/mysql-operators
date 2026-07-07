# MySQL operators
[![Charmhub](https://charmhub.io/mysql/badge.svg?channel=8.4/edge)](https://charmhub.io/mysql)
[![Charmhub](https://charmhub.io/mysql-k8s/badge.svg?channel=8.4/edge)](https://charmhub.io/mysql-k8s)
[![Release](https://github.com/canonical/mysql-operators/actions/workflows/release.yaml/badge.svg?branch=8.4/edge)](https://github.com/canonical/mysql-operators/actions/workflows/release.yaml)
[![Tests](https://github.com/canonical/mysql-operators/actions/workflows/ci.yaml/badge.svg?branch=8.4/edge)](https://github.com/canonical/mysql-operators/actions/workflows/ci.yaml)

## Description

The Charmed MySQL Server is a database operator built for the [Juju](https://canonical.com/juju) orchestrator. It can be deployed 

* on bare metal (using a [machine cloud](https://canonical.com/juju/docs/juju-cli/3.6/reference/cloud/), for instance [LXD](https://canonical.com/juju/docs/juju-cli/3.6/reference/cloud/list-of-supported-clouds/lxd/#cloud-lxd)), or 
* on Kubernetes (using a [K8s cloud](https://canonical.com/juju/docs/juju-cli/3.6/reference/cloud/), for instance [microk8s](https://canonical.com/juju/docs/juju-cli/3.6/reference/cloud/list-of-supported-clouds/microk8s/#cloud-kubernetes-microk8s) or [Canonical K8s](https://canonical.com/juju/docs/juju-cli/3.6/reference/cloud/list-of-supported-clouds/canonical-kubernetes/#cloud-canonical-k8s)).

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

See the [official documentation](https://canonical-charmed-mysql.readthedocs-hosted.com/8.4) for more operational guidance, such as deployment on specific clouds, TLS, monitoring, backups, and troubleshooting.

## Relations

Relations are the standard way to interconnect multiple Juju operators.
These relations are defined over well-defined interfaces, that both _requirer_ and _provider_ operators must support.

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
(cd kubernetes && charmcraftlocal pack)
(cd machines && charmcraftlocal pack)
```

Please see the [Juju SDK docs](https://juju.is/docs/sdk) for guidelines on
enhancements to this charm following best practice guidelines, and [CONTRIBUTING.md](./CONTRIBUTING.md)
for further developer guidance.
