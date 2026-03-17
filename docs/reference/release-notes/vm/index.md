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

| Revision (`amd`) | Revision (`arm`) | Revision (`s390x`) | MySQL version | Juju version |
|:----------------:|:----------------:|:------------------:|:-------------:|:------------:|
|                  |                  |                    |               |              |

\* The **TLS** column indicates support for **`v2` or higher** of the [`tls-certificates` interface](https://charmhub.io/tls-certificates-interface/libraries/tls_certificates). This means that you can integrate with [modern TLS charms](https://charmhub.io/topics/security-with-x-509-certificates).

```{toctree}
:titlesonly:
:hidden:

```


<!--BADGES-->
[check]: https://img.icons8.com/color/20/checkmark--v1.png
