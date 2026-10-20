(minor-rollback-router)=
# How to perform a minor rollback

**Example**:  MySQL Router 8.0.34 -> MySQL Router 8.0.33 (including simple charm revision bump: from revision YY to revision XX)

```{important}
**Do not trigger a rollback during an upgrade!**

It may cause unpredictable MySQL Cluster and/or MySQL Router state.
```

## Minor rollback steps

The rollback is NOT necessary if a `sacrificial unit` is created before the upgrade, just remove it using scale-down the application. Otherwise perform the rollback:

1. **Rollback**. Perform the charm rollback using `juju refresh`. The unit with the maximal ordinal will be rolled-back first and rollback continues for entire application.
2. **Check**. Make sure the charm and cluster are in healthy state again.

## Manual rollback

After a `juju refresh`, case there any version incompatibilities in charm revisions or it dependencies, or any other unexpected failure in the upgrade process, the upgrade process will be halted an enter a failure state.

Although the underlying MySQL Cluster and MySQL Router continue to work, it’s important to rollback the charm to previous revision so an update can be later attempted after a further inspection of the failure.

<!-- TODO: review the revisions here 
```{caution}
Rolling back is only possible between revisions that implement the same refresh behavior.

On VM, you can roll back versions between
*  
*  

On K8s, you can roll back versions between
* Revisions 69 to 813 OR
* Revisions 814 and above
```
-->

To execute a rollback we take the same procedure as the upgrade, the difference being the charm revision to upgrade to. In this example, we refresh the charm back to revision `88`:

When using charm from charmhub:

````{tab-set}
```{tab-item} VM
:sync: vm

    juju refresh mysql-router --revision=88

If deploying from local charm file, one need to have the previous revision charm file and the `mysql-image` resource, then run:

    juju refresh mysql-router --path=<path_to_charm_file>

The biggest ordinal unit will be rolled out and should rejoin the cluster after settling down. After the refresh command, the juju controller revision for the application will be back in sync with the running MySQL Router revision.
```
```{tab-item} K8s
:sync: k8s

    juju refresh mysql-router-k8s --revision=88 --trust

When deploying from a local charm file, you need to have the previous revision's `.charm` file and the `mysql-image` resource. Then, run:

    juju refresh mysql-router-k8s --trust --path=<path_to_charm_file> --resource mysql-router-image=<image>

The resource reference can be found under the `upstream-source` key in the charm's `metadata.yaml` file. You can access this file by:

* Simply unpacking the `.charm` file
* Finding the corresponding [release](https://github.com/canonical/mysql-router-k8s-operator/releases) in the charm's GitHub repository and navigating to `metadata.yaml`.
```
````

Check `juju status` to make sure the cluster state is OK.
