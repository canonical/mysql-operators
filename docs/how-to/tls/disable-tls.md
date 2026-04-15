---
myst:
  html_meta:
    description: "Learn how to disable TLS encryption for Charmed MySQL using the self-signed-certificates operator."
---

(disable-tls)=
# How to disable TLS

To follow this guide, you need to have a running Charmed MySQL cluster with TLS enabled.
See {ref}`enable-tls` for more information. In general, to disable encryption with TLS,
remove the relation between Charmed MySQL and the TLS provider.

````{tab-set}
```{tab-item} VM
:sync: vm

    juju status --relations

    > Integration provider                   Requirer                   Interface         Type     Message
    > mysql:database-peers                   mysql:database-peers       mysql_peers       peer
    > mysql:restart                          mysql:restart              rolling_op        peer
    > self-signed-certificates:certificates  mysql:client-certificates  tls-certificates  regular
```

```{tab-item} K8s
:sync: k8s

    juju status --relations

    > Integration provider                   Requirer                      Interface         Type     Message
    > mysql-k8s:database-peers               mysql-k8s:database-peers      mysql_peers       peer
    > mysql-k8s:restart                      mysql-k8s:restart             rolling_op        peer
    > self-signed-certificates:certificates  mysql-k8s:client-certificates tls-certificates  regular
```
````

## Disable client-to-server encryption

Separate the certificates charm and the Charmed MySQL application on the `client-certificates` endpoint:

````{tab-set}
```{tab-item} VM
:sync: vm

    juju remove-relation self-signed-certificates mysql:client-certificates
```

```{tab-item} K8s
:sync: k8s

    juju remove-relation self-signed-certificates mysql-k8s:client-certificates
```
````
