(release-notes-k8s)=
# Release notes (K8s)

This page provides a high-level overview of the dependencies and features that are supported by each revision in every stable release of the [MySQL charm for Kubernetes](https://charmhub.io/mysql-k8s).

To learn more about the different release tracks and channels, see the [Juju documentation about channels](https://documentation.ubuntu.com/juju/3.6/reference/charm/#risk).

To see all releases and commits, see [Charmed MySQL on GitHub](https://github.com/canonical/mysql-operators).

## Dependencies and supported features

Several [revisions](https://documentation.ubuntu.com/juju/3.6/reference/charm/#charm-revision) are released simultaneously for different [bases/series](https://juju.is/docs/juju/base) using the same charm code. In other words, one release contains multiple revisions.

If you do not specify a revision on deploy time, Juju will automatically choose the revision that matches your base and architecture.

All revisions of MySQL described below are built for *Ubuntu 22.04 LTS (Jammy)*.

| Revision (`amd`) | Revision (`arm`) | Revision (`s390x`) | MySQL version | Juju version | {ref}`TLS <enable-tls>`* | {ref}`Monitoring <enable-monitoring>` | {ref}`In-place upgrades <refresh-single-cluster>`| {ref}`Cluster-cluster replication <cluster-cluster-replication>` |
|:---:|:---:|:----:|:---:|:---:|:---:|:---:|:---:|:---:|
| [343] | [344] | [342] | 8.0.44 | `3.5.4+` | ![check] | ![check] | ![check] | ![check] |
| [255] | [254] |       | 8.0.41 | `3.5.4+` | ![check] | ![check] | ![check] | ![check] | ![check] |
| [240] | [241] |       | 8.0.41 | `3.5.4+` | ![check] | ![check] | ![check] | ![check] | |
| [210] | [211] |       | 8.0.39 | `3.5.4+` | ![check] | ![check] | ![check] | ![check] | |
| [180] | [181] |       | 8.0.37 | `3.4.3+` | ![check] | ![check] | ![check] | ![check] | |
| [153] |       |       | 8.0.36 | `3.4.3+` | ![check] | ![check] | ![check] | ![check] | |
| [127] |       |       | 8.0.35 | `3.1.6+` |  | ![check] | ![check] |  | |
| [113] |       |       | 8.0.34 | `3.1.6+` |  | ![check] | ![check] |  | |
| [99]  |       |       | 8.0.34 | `3.1.6+` |  | ![check] | ![check] |  | |
| [75]  |       |       | 8.0.32 | `2.9.32+` |  | ![check] | ![check] |  | |

\* The **TLS** column indicates support for **`v2` or higher** of the [`tls-certificates` interface](https://charmhub.io/tls-certificates-interface/libraries/tls_certificates). This means that you can integrate with [modern TLS charms](https://charmhub.io/topics/security-with-x-509-certificates).

```{toctree}
:titlesonly:
:hidden:

Revisions 342-344 <revisions-342-344>
Revisions 254-255 <revisions-254-255>
Revisions 240-241 <revisions-240-241>
Revisions 210-211 <revisions-210-211>
Revisions 180-181 <revisions-180-181>
Revision 153 <revision-153>
Revision 127 <revision-127>
Revision 113 <revision-113>
Revision 99  <revision-99>
Revision 75  <revision-75>
```

<!-- LINKS -->
[342]: revisions-342-344.md
[343]: revisions-342-344.md
[344]: revisions-342-344.md
[255]: revisions-254-255.md
[254]: revisions-254-255.md
[240]: revisions-240-241.md
[241]: revisions-240-241.md
[210]: revisions-210-211.md
[211]: revisions-210-211.md
[180]: revisions-180-181.md
[181]: revisions-180-181.md
[153]: revision-153.md
[127]: revision-127.md
[113]: revision-113.md
[99]: revision-99.md
[75]: revision-75.md

<!--BADGES-->
[check]: https://img.icons8.com/color/20/checkmark--v1.png
