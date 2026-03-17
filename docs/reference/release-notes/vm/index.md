---
myst:
  html_meta:
    description: "Overview of all stable Charmed MySQL VM charm revisions with MySQL versions, Juju requirements, and supported features per release."
---

(release-notes-vm)=
# Release notes (VM)

This page provides a high-level overview of the dependencies and features that are supported by each revision in every stable release of the [MySQL charm for machines/VM](https://charmhub.io/mysql).

To learn more about the different release tracks and channels, see the [Juju documentation about channels](https://documentation.ubuntu.com/juju/3.6/reference/charm/#risk).

To see all releases and commits, see [Charmed MySQL on GitHub](https://github.com/canonical/mysql-operators).

## Dependencies and supported features

Several [revisions](https://documentation.ubuntu.com/juju/3.6/reference/charm/#charm-revision) are released simultaneously for different [bases/series](https://juju.is/docs/juju/base) using the same charm code. In other words, one release contains multiple revisions.

If you do not specify a revision on deploy time, Juju will automatically choose the revision that matches your base and architecture.

All revisions of MySQL described below are built for *Ubuntu 22.04 LTS (Jammy)*.

| Revision (`amd`) | Revision (`arm`) | Revision (`s390x`) | MySQL version | Juju version | {ref}`TLS <enable-tls>`* | {ref}`Monitoring <enable-monitoring>` | {ref}`In-place upgrades <refresh-single-cluster>`| {ref}`Cluster-cluster replication <cluster-cluster-replication>` |
|:-----:|:-----:|:-----:|:-----:|:---------:|:--------:|:--------:|:--------:|:--------:|
| [444] | [442] | [443] |8.0.44 | `3.4.3+`  | ![check] | ![check] | ![check] | ![check] |
| [366] | [367] |       |8.0.41 | `3.4.3+`  | ![check] | ![check] | ![check] | ![check] |
| [313] | [312] |       |8.0.39 | `3.4.3+`  | ![check] | ![check] | ![check] | ![check] |
| [240] |       |       |8.0.36 | `3.4.3+`  | ![check] | ![check] | ![check] | ![check] |
| [196] |       |       |8.0.34 | `3.1.6+`  |          | ![check] | ![check] |          |
| [151] |       |       |8.0.32 | `2.9.32+` |          | ![check] | ![check] |          |

\* The **TLS** column indicates support for **`v2` or higher** of the [`tls-certificates` interface](https://charmhub.io/tls-certificates-interface/libraries/tls_certificates). This means that you can integrate with [modern TLS charms](https://charmhub.io/topics/security-with-x-509-certificates).

```{toctree}
:titlesonly:
:hidden:

Revisions 442-444 <revisions-442-444>
Revisions 366-367 <revisions-366-367>
Revisions 312-313 <revisions-312-313>
Revision 240 <revision-240>
Revision 196 <revision-196>
Revision 151 <revision-151>
```

<!-- LINKS -->
[444]: revisions-442-444.md
[443]: revisions-442-444.md
[442]: revisions-442-444.md
[367]: revisions-366-367.md
[366]: revisions-366-367.md
[313]: revisions-312-313.md
[312]: revisions-312-313.md
[240]: revision-240.md
[196]: revision-196.md
[151]: revision-151.md

<!--BADGES-->
[check]: https://img.icons8.com/color/20/checkmark--v1.png
