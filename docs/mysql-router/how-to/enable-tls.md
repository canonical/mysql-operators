(enable-tls-router)=
# How to enable TLS encryption

<!--TODO: clearer breakdown between router, server, client, and traffic paths that may or may not be encrypted -->

## Encryption between a client application and MySQL Router

MySQL Router is a subordinated charm. Client applications connect to it using a local UNIX socket, therefore TLS encryption is not necessary between the client application and MySQL Router.

If your application exists outside of Juju and can therefore not be deployed alongside MySQL Router, see {ref}`external-access-router` for guidance on the recommended setup.

## Encryption between MySQL Router and MySQL Server

**TLS encryption is recommended between MySQL Router and MySQL server**. See [How to enable TLS on MySQL](../../how-to/tls/index.md).