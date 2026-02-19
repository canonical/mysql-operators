(enable-tls)=
# How to enable TLS encryption

This guide describes how to enable TLS using the [`self-signed-certificates` operator](https://github.com/canonical/self-signed-certificates-operator) as an example.

```{caution}
**[Self-signed certificates](https://en.wikipedia.org/wiki/Self-signed_certificate) are not recommended for a production environment.**

Check [this guide](https://discourse.charmhub.io/t/11664) for an overview of the TLS certificates charms available. 
```

## Enable TLS

First, deploy the TLS charm:

```shell
juju deploy self-signed-certificates
```

To enable TLS, integrate it with your MySQL application:

````{tab-set}
```{tab-item} VM
:sync: vm

    juju relate self-signed-certificates mysql
```

```{tab-item} K8s
:sync: k8s

    juju relate self-signed-certificates mysql-k8s
```
````

## Manage keys

Updates to private keys for certificate signing requests (CSR) can be made via the `set-tls-private-key` action. Note that passing keys to external/internal keys should *only be done with* `base64 -w0`, *not* `cat`.

With three replicas, the following schema should be followed.

Generate a shared internal (private) key:

```shell
openssl genrsa -out internal-key.pem 3072
```

Apply the newly generated internal key on each `juju` unit:

````{tab-set}
```{tab-item} VM
:sync: vm

    juju run mysql/0 set-tls-private-key "internal-key=$(base64 -w0 internal-key.pem)"
    juju run mysql/1 set-tls-private-key "internal-key=$(base64 -w0 internal-key.pem)"
    juju run mysql/2 set-tls-private-key "internal-key=$(base64 -w0 internal-key.pem)"

```

```{tab-item} K8s
:sync: k8s

    juju run mysql-k8s/0 set-tls-private-key "internal-key=$(base64 -w0 internal-key.pem)"
    juju run mysql-k8s/1 set-tls-private-key "internal-key=$(base64 -w0 internal-key.pem)"
    juju run mysql-k8s/2 set-tls-private-key "internal-key=$(base64 -w0 internal-key.pem)"
```
````

```{admonition} Juju 2.9 users
:class: tip

Remember that `juju run <action name>` becomes `juju run-action <action name> --wait`.

See also: {ref}`breaking-changes-juju`
```

Updates can also be done with auto-generated keys:

````{tab-set}
```{tab-item} VM
:sync: vm

    juju run mysql/0 set-tls-private-key
    juju run mysql/1 set-tls-private-key
    juju run mysql/2 set-tls-private-key
```

```{tab-item} K8s
:sync: k8s

    juju run mysql-k8s/0 set-tls-private-key
    juju run mysql-k8s/1 set-tls-private-key
    juju run mysql-k8s/2 set-tls-private-key
```
````

## Disable TLS

Disable TLS by removing the integration:

````{tab-set}
```{tab-item} VM
:sync: vm

    juju remove-relation self-signed-certificates mysql
```

```{tab-item} K8s
:sync: k8s

    juju remove-relation self-signed-certificates mysql-k8s
```
````

