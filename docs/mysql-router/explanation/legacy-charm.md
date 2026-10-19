(legacy-charm-router)=
# Legacy charm

This page contains explanations regarding the legacy version of this charm. This includes clarification about Charmhub tracks, supported endpoints and interfaces, config options, and other important information.

## Charm types: "legacy" vs. "modern"

There are [two types of charms](https://juju.is/docs/sdk/charm-taxonomy#heading--charm-types-by-generation) stored under the same charm name `mysql-router`:

1. [Reactive](https://juju.is/docs/sdk/charm-taxonomy#heading--reactive)  charm in the channel `latest/stable`, `8.0/stable`, `8.0.19/stable` (called `legacy`)
2. [Ops-based](https://juju.is/docs/sdk/ops) charm in the channel `dpe/candidate`, `8.4/edge` (called `modern`)

Both legacy and modern charms are [**subordinated**](https://juju.is/docs/sdk/charm-taxonomy#heading--subordinate-charms).

The legacy charm provided SQL endpoints `shared-db` (for the interface `mysql-shared`). The modern charm provides those old endpoint and a new endpoint `database` (for the interface `mysql_client`). See: {ref}`interfaces-router`.

**Note**: Please choose one endpoint to use. No need to relate all of them simultaneously!

## Default track `latest/` vs. track `8.4/`

The [default track](https://docs.openstack.org/charm-guide/yoga/project/charm-delivery.html) will be switched from the `latest` to `8.4` soon. This is to ensure all new deployments use a modern codebase. We strongly advise against using the latest track, since a future charm upgrade may result in a MySQL Router version incompatible with an integrated application. Track `8.4/` guarantees a major router version 8.4 deployment only. The track `latest/` will be closed after all applications migrated from reactive to the ops-based charm.

## How to migrate to the modern charm

The modern charm provides temporary support for the legacy interfaces:

**Quick try**: relate the current application with new charm using endpoint `shared-db` (set the channel to `dpe/candidate`). No extra changes necessary:

```
  mysql-router:
    charm: mysql-router
    channel: dpe/candidate
```

**Proper migration**: migrate the application to the new interface [`mysql_client`](https://github.com/canonical/charm-relation-interfaces). The application will connect MySQl Router using the [data_interfaces](https://charmhub.io/data-platform-libs/libraries/data_interfaces) library from [data-platform-libs](https://github.com/canonical/data-platform-libs/) via the endpoint `database`.

```{caution}
**In-place upgrades are NOT possible!**

The reactive charm cannot be upgraded to the operator-framework-based one. The second/modern charm application must be launched nearby and relations should be switched from the legacy application to the modern one.
```

## How to deploy the legacy charm

Deploy the charm using the channel `latest/stable`:

```
  mysql-router:
    charm: mysql-router
    channel: 8.0/stable
```

```{note}
Remove Charm store prefix `cs:` from the bundle. Otherwise the modern charm will be chosen by Juju (due to the default track will be pointing to `8.4/stable` and not `latest/stable`). The common error message is: `cannot deploy application "mysql-router": unknown option "..."`.
```

## Features supported by the modern charm
This section goes over the key differences in feature support and functionality between the legacy and modern charm.

### Config options

The legacy charm config options were not moved to the modern charm, since the modern charm applies the best possible configuration automatically. Feel free to [contact us](https://matrix.to/#/#charmhub-data-platform:ubuntu.com) about the MySQl Router config options.

### Extensions

Both legacy and modern charms provide no plugins/extensions support.

### MySQL versions

At the moment, the modern MySQL Router charm supports relation to the modern Charmed MySQL 8.0 (based on Jammy/22.04 series) only.
Please [contact us](https://matrix.to/#/#charmhub-data-platform:ubuntu.com) if you need different versions/series.

### Architectures

Currently, the modern charm supports:

* `amd64`
* `arm64`
* `s390x` <!--TODO: specify revisions -->

### Report issues

The "legacy charm" (from `latest/stable`) is stored on Launchpad.

The "modern charm" (from `dpe/candidate`) is stored on [GitHub](https://github.com/canonical/mysql-router-operator). Report modern charm issues [here](https://github.com/canonical/mysql-router-operator/issues/new/choose).

Do you have questions? [Reach out](https://matrix.to/#/#charmhub-data-platform:ubuntu.com) to us!
