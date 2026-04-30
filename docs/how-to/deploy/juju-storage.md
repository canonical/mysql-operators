---
myst:
  html_meta:
    description: "Manage storage types for your Charmed MySQL deployment using Juju storage."
---

(juju-storage)=
# Deploy on Juju storage

Charmed MySQL uses the [Juju storage](https://documentation.ubuntu.com/juju/3.6/reference/storage/) abstraction to utilise data volume provided by different [clouds](https://documentation.ubuntu.com/juju/3.6/reference/cloud/#cloud) while keeping the same UI/UX for end users.

## Check Juju storage details

Charmed MySQL 8.4 supports multiple storage types, both on [VM](https://charmhub.io/mysql?channel=8.4/edge) and [K8s](https://charmhub.io/mysql-k8s?channel=8.4/edge): `archive`, `data`, `logs` and `temp`.

Check the [`metadata.yaml`](https://github.com/canonical/mysql-operators/blob/8.4/edge/machines/metadata.yaml) to find Juju storage names and metadata:

<details><summary>Charmed MySQL 8.4 storage list</summary>

`````{tab-set}
````{tab-item} VM
:sync: vm

```text
storage:
  archive:
    type: filesystem
    description: Persistent storage for rotated logs and other archival purposes
    location: /var/snap/charmed-mysql/common/var/lib/mysql/archive
  data:
    type: filesystem
    description: Persistent storage for MySQL data
    location: /var/snap/charmed-mysql/common/var/lib/mysql/data
  logs:
    type: filesystem
    description: Persistent storage for MySQL error logs, general query logs, slow query logs, binary logs, redo logs and undo logs
    location: /var/snap/charmed-mysql/common/var/lib/mysql/logs
  temp:
    type: filesystem
    description: Persistent storage for InnoDB temporary tablespaces
    location: /var/snap/charmed-mysql/common/var/lib/mysql/temp
```
````

````{tab-item} K8s
:sync: k8s

```text
containers:
  mysql:
    ...
    mounts:
      - storage: archive
        location: /var/lib/mysql/archive
      - storage: data
        location: /var/lib/mysql/data
      - storage: logs
        location: /var/lib/mysql/logs
      - storage: temp
        location: /var/lib/mysql/temp

storage:
  archive:
    type: filesystem
    description: Persistent storage for rotated logs and other archival purposes
  data:
    type: filesystem
    description: Persistent storage for MySQL data
  temp:
    type: filesystem
    description: Persistent storage for InnoDB temporary tablespaces
  logs:
    type: filesystem
    description: Persistent storage for MySQL error logs, general query logs, slow query logs, binary logs, redo logs and undo logs
```
````
`````

</details>

## Define storage size

`````{tab-set}
````{tab-item} VM
:sync: vm

```{terminal}
:user: ubuntu
:host: my-vm

juju deploy mysql --channel 8.4/edge --storage data=10G
```

```text
> juju storage

Unit     Storage ID  Type        Pool    Size     Status    Message
...
mysql/0  data/1      filesystem  lxd     10 GiB   attached
```
````

````{tab-item} K8s
:sync: k8s

```{terminal}
:user: ubuntu
:host: my-vm

juju deploy mysql-k8s --channel 8.4/edge --storage data=10G
```

```text
> juju storage

Unit         Storage ID  Type        Pool        Size     Status    Message
...
mysql-k8s/0  data/1      filesystem  kubernetes  10 GiB   attached  Successfully provisioned volume pvc-2cad4931-...
```
````
`````

## Define storage location

Juju supports wide list of different [storage pools](https://bobcares.com/blog/lxd-create-storage-pool/):

`````{tab-set}
````{tab-item} VM
:sync: vm

```text
> juju create-storage-pool mystoragepool lxd

> juju storage-pools | grep -E "Name|mystoragepool"
Name           Provider  Attributes
mystoragepool  lxd

> juju deploy mysql --channel 8.4/edge --storage data=5G,mystoragepool

> $ juju storage | grep -E "Unit|data"
Unit     Storage ID  Type        Pool           Size     Status    Message
mysql/0  data/1      filesystem  mystoragepool  5.0 GiB  attached
```
````

````{tab-item} K8s
:sync: k8s

```text
> juju create-storage-pool mystoragepool kubernetes

> juju storage-pools | grep -E "Name|mystoragepool"
Name           Provider    Attributes
mystoragepool  kubernetes

> juju deploy mysql-k8s --channel 8.4/edge --storage data=5G,mystoragepool

> $ juju storage | grep -E "Unit|data"
Unit         Storage ID  Type        Pool           Size     Status    Message
mysql-k8s/0  data/1      filesystem  mystoragepool  5.0 GiB  attached  Successfully provisioned volume pvc-d3cde32e-...
```
````
`````
