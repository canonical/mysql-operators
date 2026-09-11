# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

import socketserver
import unittest
from unittest.mock import MagicMock, patch

import tenacity
from lightkube.core.exceptions import ApiError
from lightkube.models.core_v1 import ServicePort, ServiceSpec
from lightkube.models.meta_v1 import ObjectMeta
from lightkube.resources.core_v1 import Pod, Service
from ops.charm import CharmBase
from ops.model import Unit
from ops.testing import Harness
from parameterized import parameterized

from k8s_helpers import KubernetesClientError, KubernetesHelpers


class _FakeCharm(CharmBase):
    def __init__(self, *args):
        super().__init__(*args)
        self.app_peer_data = {"cluster-name": "test-cluster"}

    @staticmethod
    def get_unit_label(unit: Unit) -> str:
        """Return unit label."""
        return unit.name.replace("/", "-")


class TestK8sHelpers(unittest.TestCase):
    def setUp(self) -> None:
        # mock generic sync client to avoid search to ~/.kube/config
        self.patcher = patch("lightkube.core.client.GenericSyncClient")
        self.mock_k8s_client = self.patcher.start()
        self.harness = Harness(_FakeCharm, meta="name: test-charm")
        self.harness.begin()
        self.k8s_helpers = KubernetesHelpers(self.harness.charm)

    def tearDown(self) -> None:
        # stop patching
        self.patcher.stop()

    @patch("lightkube.Client.create")
    def test_create_endpoint_service(self, _create):
        self.k8s_helpers.create_endpoint_services(["role1"])
        _create.assert_called_once_with(
            Service(
                apiVersion="v1",
                kind="Service",
                metadata=ObjectMeta(
                    namespace=self.harness.charm.model.name,
                    name=f"{self.harness.charm.model.app.name}-role1",
                    ownerReferences=self.mock_k8s_client.return_value.request.return_value.metadata.ownerReferences,
                ),
                spec=ServiceSpec(
                    selector={
                        "cluster-name": self.harness.charm.app_peer_data.get("cluster-name"),
                        "application-name": self.harness.charm.model.app.name,
                        "role": "role1",
                    },
                    ports=[ServicePort(port=3306, targetPort=3306)],
                    type="ClusterIP",
                ),
            )
        )

    @patch("lightkube.Client.get")
    @patch("lightkube.Client.patch")
    def test_label_pod(self, _patch, _get):
        pod = MagicMock()
        pod.name = self.harness.charm.unit.name.replace("/", "-")
        _get.return_value = pod
        self.k8s_helpers.label_pod("role1")
        _patch.assert_called_once_with(Pod, pod.name, pod)

    @staticmethod
    def _make_api_error(code: int) -> ApiError:
        mock_response = MagicMock()
        mock_response.json.return_value = {"code": code, "message": f"error {code}"}
        return ApiError(response=mock_response)

    @parameterized.expand([
        ("not_found_404", 404, False),
        ("conflict_409", 409, False),
        ("forbidden_403", 403, True),
        ("other_500", 500, True),
    ])
    @patch("lightkube.Client.get")
    @patch("lightkube.Client.patch")
    def test_label_pod_api_errors(self, name, status_code, expect_raises, _patch, _get):
        _patch.side_effect = self._make_api_error(status_code)
        if expect_raises:
            with self.assertRaises(KubernetesClientError):
                self.k8s_helpers.label_pod("role1")
        else:
            self.k8s_helpers.label_pod("role1")
        _patch.assert_called_once()

    @patch("lightkube.Client.get")
    @patch("lightkube.Client.patch")
    def test_label_pod_skips_when_role_unchanged(self, _patch, _get):
        pod = MagicMock()
        pod.metadata.labels = {"role": "primary"}
        _get.return_value = pod
        self.k8s_helpers.label_pod("primary")
        _patch.assert_not_called()

    @parameterized.expand([
        ("memory", {"memory": "2Gi"}),
        ("cpu", {"cpu": "2"}),
        ("empty", {}),
    ])
    @patch("lightkube.Client.get")
    def test_get_resources_limit(self, name, limits, _get):
        pod = MagicMock()
        container = MagicMock()
        container.resources.limits = limits
        container.name = "mysql"
        pod.spec.containers = [container]
        _get.return_value = pod
        self.assertEqual(self.k8s_helpers.get_resources_limits(container_name="mysql"), limits)

    @patch("lightkube.Client.get")
    def test_get_resources_limit_container_not_found(self, _get):
        pod = MagicMock()
        container = MagicMock()
        container.name = "other"
        pod.spec.containers = [container]
        _get.return_value = pod
        self.assertEqual(self.k8s_helpers.get_resources_limits(container_name="mysql"), {})

    @patch("lightkube.Client.get")
    def test_get_resources_limit_api_error(self, _get):
        _get.side_effect = self._make_api_error(500)
        with self.assertRaises(KubernetesClientError):
            self.k8s_helpers.get_resources_limits(container_name="mysql")

    def test_wait_service_ready(self):
        server = socketserver.ForkingTCPServer(("localhost", 9999), MyTCPHandler)
        server.server_activate()
        self.k8s_helpers.wait_service_ready(("localhost", 9999))

        server.server_close()
        self.k8s_helpers.wait_service_ready.retry.retry = tenacity.retry_if_not_result(
            lambda x: True
        )
        with self.assertRaises(TimeoutError):
            self.k8s_helpers.wait_service_ready(("localhost", 9999))


class MyTCPHandler(socketserver.BaseRequestHandler):
    def handle(self):
        pass
