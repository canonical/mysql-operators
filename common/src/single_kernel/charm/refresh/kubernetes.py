# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import typing

from charm_refresh import CharmSpecificKubernetes

from ...managers import Clients
from .base import BaseRefreshHandler

if typing.TYPE_CHECKING:
    from ...charm import BaseCharm


class K8sRefreshHandler(BaseRefreshHandler, CharmSpecificKubernetes):
    """Class to deal with the operator refresh."""

    charm_name = "mysql-k8s"
    workload_name = "MySQL"
    oci_resource_name = "mysql-image"

    def __init__(self, charm: BaseCharm, clients: Clients):
        """Initialize the class attributes."""
        super().__init__(charm, clients)
        super().__post_init__()
