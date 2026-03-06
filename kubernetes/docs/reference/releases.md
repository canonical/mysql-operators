# Releases

This page provides high-level overviews of the dependencies and features that are supported by each revision in every stable release.

To learn more about the different release tracks and channels, see the [Juju documentation about channels](https://documentation.ubuntu.com/juju/3.6/reference/charm/#risk).

To see all releases and commits, check the [Charmed MySQL K8s Releases page on GitHub](https://github.com/canonical/mysql-k8s-operator/releases).

## Dependencies and supported features

For a given release, this table shows:
* The MySQL version packaged inside
* The minimum Juju version required to reliably operate **all** features of the release
* Support for specific features

|   Release    | MySQL version | Juju version | [TLS encryption](/how-to/enable-tls) | [COS monitoring](/how-to/monitoring-cos/enable-monitoring) | [Minor version upgrades](/how-to/refresh/single-cluster/refresh-single-cluster) | [Cluster-cluster replication](/how-to/cluster-cluster-replication/deploy) | [Point-in-time recovery](point-in-time-recovery) |
|:------------:|:-------------:|:------------:|:------------------------------------:|:----------------------------------------------------------:|:-------------------------------------------------------------------------------:|:-------------------------------------------------------------------------:|:------------------------------------------------:|

>For more details about a particular revision, refer to its dedicated Release Notes page.
For more details about each feature/interface, refer to the documentation linked in the column headers.

## Architecture and base
Several [revisions](https://documentation.ubuntu.com/juju/3.6/reference/charm/#charm-revision) are released simultaneously for different [bases](https://juju.is/docs/juju/base) using the same charm code. In other words, one release contains multiple revisions.

> If you do not specify a revision on deploy time, Juju will automatically choose the revision that matches your base and architecture. 
> 
> See: [`juju set-constraints`](https://juju.is/docs/juju/juju-set-constraints), [`juju info`](https://juju.is/docs/juju/juju-info)
