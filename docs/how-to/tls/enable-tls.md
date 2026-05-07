---
myst:
  html_meta:
    description: "Learn how to enable TLS encryption for Charmed MySQL using the self-signed-certificates operator."
---

(enable-tls)=
# How to enable TLS

Charmed MySQL provides a secure transport layer for both **client-server** and **peer-to-peer** communication,
providing a simple way of enabling TLS encryption for both types.

Peer-to-peer
: All communication between members in the cluster will be encrypted. 

Client-to-server
: The clients can verify the server identity and provide transport security.


## Deploy a TLS provider

This guide describes how to enable TLS using the [`self-signed-certificates` operator](https://github.com/canonical/self-signed-certificates-operator).

```{caution}
**[Self-signed certificates](https://en.wikipedia.org/wiki/Self-signed_certificate) are not recommended for a production environment.**

Check [this guide](https://discourse.charmhub.io/t/11664) for an overview of the TLS certificates charms available. 
```

```shell
juju deploy self-signed-certificates --channel 1/stable
```

## Enable client-to-server encryption

Integrate the certificates charm with the Charmed MySQL application on the `client-certificates` endpoint:

````{tab-set}
```{tab-item} VM
:sync: vm

    juju integrate self-signed-certificates mysql:client-certificates
```

```{tab-item} K8s
:sync: k8s

    juju integrate self-signed-certificates mysql-k8s:client-certificates
```
````

## Enable peer-to-peer encryption

Integrate the certificates charm with the Charmed MySQL application on the `peer-certificates` endpoint:

````{tab-set}
```{tab-item} VM
:sync: vm

    juju integrate self-signed-certificates mysql:peer-certificates
```

```{tab-item} K8s
:sync: k8s

    juju integrate self-signed-certificates mysql-k8s:peer-certificates
```
````

## Certificate expiration and rotation

Charmed MySQL provides full automation of certificate rotation.

As soon as new certificates are issued by the TLS provider, Charmed MySQL will replace the expiring certificate with the
renewed one on each unit. In case of CA certificates, it will restart the units in rolling fashion to enable the updated 
CA certificate while maintaining availability during the process.
