(cluster-cluster-switchover-failover)=
# Switchover / Failover

```{admonition} This feature requires Juju 3
:class: warning

The feature described in this page is **not** available on Juju 2.9.
```

This guide assumes both `Rome` and `Lisbon` Clusters are deployed using the {ref}`cluster-cluster-deploy`.

## Switchover (safe)

Assuming `Rome` is currently `Primary` and you want to promote `Lisbon` to be new primary:

```shell
juju run -m lisbon db2/leader promote-to-primary scope=cluster
```

`Rome` will be converted to `StandBy` member.

## Failover (forced)

```{danger}
This is a **dangerous** operation which can cause a split-brain situation. 

It should ONLY be executed if Primary cluster is no longer exist (i.e. it is lost). Otherwise please use the safe switchover procedure described above!
```

Assuming `Rome` was a `Primary` (before we lost the cluster `Rome`) and you want to promote `Lisbon` to be the new primary:

```shell
juju run -m lisbon db2/leader promote-to-primary scope=cluster force=True
```

```{caution}
`force=True` will cause the old primary to be invalidated.
```
