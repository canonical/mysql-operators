---
myst:
  html_meta:
    description: "Roll back a Charmed MySQL multi-cluster deployment by applying the single-cluster rollback procedure to each upgraded cluster in the set."
---

# Roll back a multi-cluster deployment

A multi-cluster rollback is the same as a single-cluster rollback, but repeated for each cluster that was fully or partially upgraded.

```{include} ../single-cluster/roll-back-single-cluster.md
    :start-after: "How to roll back a single cluster"
```