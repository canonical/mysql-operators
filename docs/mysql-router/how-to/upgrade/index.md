(upgrade-router)=
# How to upgrade

**In-place upgrades/rollbacks are not possible for major versions.**

> Canonical is not planning to support in-place upgrades for major version changes. The new MySQL Router charm will have to be installed nearby, and the data will be copied from the old to the new installation. After announcing the next MySQL major version support, the appropriate documentation for data migration will be published.

For instructions on carrying out **minor version upgrades**, see the following guides:

* {ref}`Minor upgrade <minor-upgrade-router>`, e.g. MySQL Router 8.0.44 -> MySQL Router 8.0.45<br/>
(including charm revision bump XX -> YY).
* {ref}`Minor rollback <minor-rollback-router>`, e.g. MySQL Router 8.0.45 -> MySQL Router 8.0.44<br/>
(including charm revision return YY -> XX).

```{toctree}
:titlesonly:
:hidden:

minor-upgrade
minor-rollback
```
