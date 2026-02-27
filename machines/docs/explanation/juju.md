# Juju 

[Juju](https://juju.is/) is an open source orchestration engine for software operators that enables the deployment, integration and lifecycle management of applications at any scale, on any infrastructure using charms.

This [charm](https://charmhub.io/mysql) is an operator - business logic encapsulated in reusable software packages that automate every aspect of an application's life. Charms are shared via [CharmHub](https://charmhub.io/).

See also:

* [Juju Documentation](https://juju.is/docs/juju) and [Blog](https://ubuntu.com/blog/tag/juju)
* [Charm SDK](https://juju.is/docs/sdk)

This page aims to provide some context on some of the inner workings of Juju that affect this charm.

## Juju  upgrades

Newly released charm revisions might require a new Juju version. This is usually because the new revision requires new Juju features, e.g. [Juju secrets](https://juju.is/docs/juju/secret).

Information about Juju requirements will be clearly indicated in the charm's [release notes](/reference/releases) and in the repository's [metadata.yaml](https://github.com/canonical/mysql-operator/blob/14c06ff88c4e564cd6d098aa213bd03e78e84b52/metadata.yaml#L72-L80) file.

When upgrading your database charm with <code>juju refresh</code>, Juju checks that its version is compatible with the target revision. If not, it stops the upgrade and prevents further changes to keep the installation safe. 

```shell
~$ juju refresh mysql

Added charm-hub charm "mysql", revision XX in channel 8.4/edge, to the model
ERROR Charm feature requirements cannot be met:
    - charm requires all of the following:
      - charm requires feature "juju" (version >= 3.6.0) but model currently supports version 3.5.0
```

You must then [upgrade to the required Juju version](/how-to/refresh/upgrade-juju) before proceeding with the charm upgrade.
