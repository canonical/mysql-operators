(legacy-charm)=
# Legacy MySQL Router charm

This page contains explanations regarding the legacy version of this charm. This includes clarification about Charmhub tracks, supported endpoints and interfaces, config options, and other important information.

---

## Charm types: "legacy" vs. "modern"

There are two types of charms stored under the same charm name `mysql-router`:

1. **Reactive** charm in the channel `latest/stable`, `8.0/stable` (called `legacy`)
2. **Ops-based** charm in the channel `dpe/candidate`, `8.4/stable` (called `modern`)

Both legacy and modern charms are **subordinated**. <!--TODO: update links to juju taxonomy-->.

The legacy charm provided SQL endpoints `shared-db` (for the interface `mysql-shared`). The modern charm provides those old endpoint and a new endpoint `database` (for the interface `mysql_client`). Read more details about the available endpoints and interfaces [here](https://github.com/canonical/mysql-router-operators/blob/8.4/edge/machines/docs/explanation/e-interfaces.md).

**Note**: Please choose one endpoint to use. No need to relate all of them simultaneously!

## Default track `latest/` vs. track `8.4/`

The [default track](https://docs.openstack.org/charm-guide/yoga/project/charm-delivery.html) will be switched from the `latest` to `8.4` soon. This is to ensure all new deployments use a modern codebase. We strongly advise against using the latest track, since a future charm upgrade may result in a MySQL Router version incompatible with an integrated application. Track `8.4/` guarantees a major router version 8.4 deployment only. The track `latest/` will be closed after all applications migrated from reactive to the ops-based charm.

## How to deploy the legacy charm

Deploy the charm using the channel `latest/stable`:

```
  mysql-router:
    charm: mysql-router
    channel: 8.0/stable
```
<!--TODO: is the channel here correct? -->

**Note**: remove Charm store prefix `cs:` from the bundle. Otherwise the modern charm will be chosen by Juju (due to the default track will be pointing to `8.4/stable` and not `latest/stable`). The common error message is: `cannot deploy application "mysql-router": unknown option "..."`.

## Features supported by the modern charm

This section goes over the key differences in feature support and functionality between the legacy and modern charm.

### Config options

The legacy charm config options were not moved to the modern charm, since the modern charm applies the best possible configuration automatically. Feel free to [contact us](https://matrix.to/#/#charmhub-data-platform:ubuntu.com) about the MySQL Router config options.

### Extensions

Both legacy and modern charms provide no plugins/extensions support.

### MySQL versions

At the moment, the modern MySQL Router charm supports relation to the modern Charmed MySQL 8.4 (based on Resolute series) only.

Please [contact us](https://matrix.to/#/#charmhub-data-platform:ubuntu.com) if you need different versions/series.

### Architectures

Currently, the modern charm supports architecture `amd64` and `arm64` only.

## Report issues

The "legacy charm" (from `latest/stable`) is stored on Launchpad. <!--TODO Report legacy charm issues [here](TODO).-->

The "modern charm" (from `8.4/edge`) is stored on [GitHub](https://github.com/canonical/mysql-router-operators). Report modern charm issues [here](https://github.com/canonical/mysql-router-operators/issues/new/choose).

Do you have questions? [Reach out](https://matrix.to/#/#charmhub-data-platform:ubuntu.com) to us!