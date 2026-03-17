---
myst:
  html_meta:
    description: "Perform a primary switchover in Charmed MySQL by promoting a chosen unit to primary using the promote-to-primary Juju action."
---

(primary-switchover)=
# How to do a primary switchover

A user may want to change the primary in a MySQL cluster to improve performance, enable maintenance, recover from failure, or balance load across nodes.

On a healthy cluster, the primary can be changed by running the `promote-to-primary` action with parameter `scope` set to `unit` on the unit that should become the new primary.

````{tab-set}
```{tab-item} VM
:sync: vm

    juju run mysql/1 promote-to-primary scope=unit

In this example, the unit `mysql/1` will become the new primary. The previous primary will become a secondary.
```

```{tab-item} K8s
:sync: k8s

    juju run mysql-k8s/1 promote-to-primary scope=unit

In this example, the unit `mysql-k8s/1` will become the new primary. The previous primary will become a secondary.
```
````

```{caution}
The `promote-to-primary` action can be used in cluster scope, when using cluster-cluster replication.

See {ref}`cluster-cluster-switchover-failover` for more information.
```