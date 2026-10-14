(upgrade)=
# How to upgrade

**In-place upgrades/rollbacks are not possible for major versions.**

> Canonical is not planning to support in-place upgrades for major version changes. The new MySQL Router K8s charm will have to be installed nearby, and the data will be copied from the old to the new installation. After announcing the next MySQL major version support, the appropriate documentation for data migration will be published.

For instructions on carrying out **minor version upgrades**, see the following guides:

* {ref}`Minor upgrade <minor-upgrade>`, e.g. MySQL Router 8.4.7 -> MySQL Router 8.4.8<br/>
(including charm revision bump XX -> YY).
* {ref}`Minor rollback <minor-rollback>`, e.g. MySQL Router 8.4.8 -> MySQL Router 8.4.7<br/>
(including charm revision return YY -> XX).

```{toctree}
:titlesonly:
:hidden:

minor-upgrade
minor-rollback
```