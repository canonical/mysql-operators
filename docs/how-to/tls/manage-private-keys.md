---
myst:
  html_meta:
    description: "Learn how to manage TLS private keys for Charmed MySQL using the self-signed-certificates operator."
---

# How to manage private keys

You can manage private keys used by the charm to generate the certificate signing requests (CSR) by storing the private key in a [juju secret](https://canonical.com/juju/docs/juju-cli/latest/reference/secret/) and then referencing the secret in the [charm configuration](https://canonical.com/juju/docs/juju-cli/latest/howto/manage-applications/#configure-an-application). The keys need to be PEM formatted, base64 encoded and at least 2048 bits long.

## Store the private key in a Juju secret

To store the private key in a juju secret, run the following command:

```shell
juju add-secret tls-client-private-key private-key=$(base64 -w0 private-key.key)
juju add-secret tls-peer-private-key private-key=$(base64 -w0 private-key.key)
```

## Reference the secret in the charm configuration

You can use the secret ID from the output to reference the secret in the charm configuration.
Now that the secret is stored, you can grant the secret to the application using the following commands:

````{tab-set}
```{tab-item} VM
:sync: vm

    juju grant-secret tls-client-private-key mysql
    juju config mysql tls-client-private-key=<SECRET_ID>
```

```{tab-item} K8s
:sync: k8s

    juju grant-secret tls-client-private-key mysql-k8s
    juju config mysql-k8s tls-client-private-key=<SECRET_ID>
```
````

Setting the private key for the peer-to-peer communication is similar to the client-to-server communication:

````{tab-set}
```{tab-item} VM
:sync: vm

    juju grant-secret tls-peer-private-key mysql
    juju config mysql tls-peer-private-key=<SECRET_ID>
```

```{tab-item} K8s
:sync: k8s

    juju grant-secret tls-peer-private-key mysql-k8s
    juju config mysql-k8s tls-peer-private-key=<SECRET_ID>
```
````

Once the configuration is set, the charm will use the private key stored in the secret to generate new certificate signing requests (CSR) to acquire new certificates from the TLS provider.
