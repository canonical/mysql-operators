#!/usr/bin/env python3
# Copyright 2021 Canonical Ltd.
# See LICENSE file for licensing details.

"""Charm for MySQL."""

from charms.mysql.v0.architecture import WrongArchitectureWarningCharm, is_wrong_architecture
from ops.main import main

if is_wrong_architecture() and __name__ == "__main__":
    main(WrongArchitectureWarningCharm)

import logging
import random
import socket
from time import sleep

import charm_refresh
import ops
from charmlibs.pathops import LocalPath
from charmlibs.rollingops import OperationResult, RollingOpsManager
from charms.data_platform_libs.v1.data_models import TypedCharmBase
from charms.grafana_k8s.v0.grafana_dashboard import GrafanaDashboardProvider
from charms.loki_k8s.v0.loki_push_api import LogProxyConsumer
from charms.mysql.v0.async_replication import (
    MySQLAsyncReplicationConsumer,
    MySQLAsyncReplicationOffer,
)
from charms.mysql.v0.backups import S3_INTEGRATOR_RELATION_NAME, MySQLBackups
from charms.mysql.v0.mysql import (
    BYTES_1MB,
    UNIT_ADD_LOCKNAME,
    InstanceRole,
    InstanceState,
    MySQLAddInstanceToClusterError,
    MySQLCharmBase,
    MySQLConfigureInstanceError,
    MySQLConfigureMySQLRolesError,
    MySQLConfigureMySQLUsersError,
    MySQLCreateClusterError,
    MySQLCreateClusterSetError,
    MySQLDropRootUserError,
    MySQLGetClusterPrimaryAddressError,
    MySQLInitializeJujuOperationsTableError,
    MySQLLockAcquisitionError,
    MySQLRebootFromCompleteOutageError,
    MySQLRejoinInstanceToClusterError,
    MySQLServiceNotRunningError,
    MySQLSetClusterPrimaryError,
    MySQLUnableToGetMemberStateError,
)
from charms.prometheus_k8s.v0.prometheus_scrape import MetricsEndpointProvider
from object_storage import S3Requirer
from ops import EventBase, ModelError, RelationBrokenEvent, RelationCreatedEvent
from ops.charm import RelationChangedEvent, RelationDepartedEvent, UpdateStatusEvent
from ops.model import (
    ActiveStatus,
    BlockedStatus,
    Container,
    MaintenanceStatus,
    Unit,
    WaitingStatus,
)
from ops.pebble import ChangeError, Layer
from ops_tracing import Tracing
from tenacity import (
    RetryError,
    Retrying,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    stop_after_delay,
    wait_fixed,
)

from config import CharmConfig, MySQLConfig
from constants import (
    BACKUPS_PASSWORD_KEY,
    BACKUPS_USERNAME,
    CONTAINER_NAME,
    COS_AGENT_RELATION_NAME,
    DEFAULT_PASSWORD_LENGTH,
    GR_MAX_MEMBERS,
    MONITORING_PASSWORD_KEY,
    MONITORING_USERNAME,
    MYSQL_BINLOGS_COLLECTOR_SERVICE,
    MYSQL_DATA_DIR,
    MYSQL_LOG_ERROR,
    MYSQL_LOG_FILES,
    MYSQL_LOG_SERVICE,
    MYSQL_SYSTEM_GROUP,
    MYSQL_SYSTEM_USER,
    MYSQLD_CONFIG_FILE,
    MYSQLD_EXPORTER_PORT,
    MYSQLD_EXPORTER_SERVICE,
    MYSQLD_LOCATION,
    MYSQLD_SERVICE,
    OPERATOR_PASSWORD_KEY,
    OPERATOR_USERNAME,
    PEER,
    REPLICATION_PASSWORD_KEY,
    REPLICATION_USERNAME,
)
from k8s_helpers import KubernetesHelpers
from log_rotation_setup import LogRotationSetup
from mysql_k8s_helpers import MySQL, MySQLInitialiseMySQLDError
from refresh import KubernetesMySQLRefresh
from relations.mysql_provider import MySQLProvider
from relations.tls import TLS
from services.events import CharmServicesEvents
from services.managers import LogRotateManager, SelfHealingManager
from services.observers import RotateMySQLLogsObserver, SelfHealingMySQLObserver
from utils import compare_dictionaries, dotappend, generate_random_password, get_k8s_fqdn

logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


class MySQLOperatorCharm(MySQLCharmBase, TypedCharmBase[CharmConfig]):
    """Operator framework charm for MySQL."""

    config_type = CharmConfig
    on = CharmServicesEvents()

    def __init__(self, *args):
        super().__init__(*args)

        # Show logger name (module name) in logs
        root_logger = logging.getLogger()
        for handler in root_logger.handlers:
            if isinstance(handler, ops.log.JujuLogHandler):
                handler.setFormatter(logging.Formatter("{name}:{message}", style="{"))

        # Lifecycle events
        self.framework.observe(self.on.mysql_pebble_ready, self._on_mysql_pebble_ready)
        self.framework.observe(self.on.leader_elected, self._on_leader_elected)
        self.framework.observe(self.on.config_changed, self._on_config_changed)
        self.framework.observe(self.on.update_status, self._on_update_status)

        self.framework.observe(self.on.archive_storage_detaching, self._on_storage_detaching)
        self.framework.observe(self.on.data_storage_detaching, self._on_storage_detaching)
        self.framework.observe(self.on.logs_storage_detaching, self._on_storage_detaching)
        self.framework.observe(self.on.temp_storage_detaching, self._on_storage_detaching)

        self.framework.observe(self.on[PEER].relation_joined, self._on_peer_relation_joined)
        self.framework.observe(self.on[PEER].relation_changed, self._on_peer_relation_changed)
        self.framework.observe(self.on[PEER].relation_departed, self._on_peer_relation_departed)

        self.framework.observe(
            self.on[COS_AGENT_RELATION_NAME].relation_created, self._reconcile_mysqld_exporter
        )
        self.framework.observe(
            self.on[COS_AGENT_RELATION_NAME].relation_broken, self._reconcile_mysqld_exporter
        )

        self.mysql_config = MySQLConfig()
        self.k8s_helpers = KubernetesHelpers(self)
        self.database_relation = MySQLProvider(self)
        self.tls = TLS(self)
        self.s3_integrator = S3Requirer(self, S3_INTEGRATOR_RELATION_NAME)
        self.backups = MySQLBackups(self, self.s3_integrator)
        self.grafana_dashboards = GrafanaDashboardProvider(self)
        self.metrics_endpoint = MetricsEndpointProvider(
            self,
            jobs=[{"static_configs": [{"targets": [f"*:{MYSQLD_EXPORTER_PORT}"]}]}],
            alert_rules_path="./src/alert_rules/prometheus",
            refresh_event=self.on.start,
        )
        self.loki_push = LogProxyConsumer(
            self,
            log_files=MYSQL_LOG_FILES,
            relation_name="logging",
            container_name="mysql",
        )

        try:
            self._refresh = charm_refresh.Kubernetes(
                KubernetesMySQLRefresh(
                    workload_name="MySQL",
                    charm_name="mysql-k8s",
                    oci_resource_name="mysql-image",
                    _charm=self,
                )
            )
        except charm_refresh.KubernetesJujuAppNotTrusted:
            self._refresh = None
        except charm_refresh.PeerRelationNotReady:
            self.unit.status = MaintenanceStatus("Waiting for peer relation")
            self._refresh = None
        except charm_refresh.UnitTearingDown:
            self.unit.status = MaintenanceStatus("Tearing down")
            self._refresh = None
        else:
            if self._refresh.workload_allowed_to_start:
                self._refresh.next_unit_allowed_to_refresh = True

        self.rolling_ops = RollingOpsManager(
            charm=self,
            base_dir=LocalPath("/var/lib/juju/rollingops"),
            peer_relation_name="rolling-ops",
            callback_targets={
                "replication": self._restart_group_replication,
                "restart": self._restart,
            },
        )

        self.log_rotate_manager = LogRotateManager(self)
        self.log_rotate_manager.start_log_rotate_manager()
        self.self_healing_manager = SelfHealingManager(self)
        self.self_healing_manager.start_self_healing_manager()

        self.log_rotate_setup = LogRotationSetup(self)
        self.log_rotate_observer = RotateMySQLLogsObserver(self)
        self.self_healing_observer = SelfHealingMySQLObserver(self)

        self.replication_offer = MySQLAsyncReplicationOffer(self)
        self.replication_consumer = MySQLAsyncReplicationConsumer(self)

        self.tracing = Tracing(self, tracing_relation_name="tracing")

    @property
    def _mysql(self) -> MySQL:
        """Returns an instance of the MySQL object from mysql_k8s_helpers."""
        return MySQL(
            self.unit_address,
            self.app_peer_data["cluster-name"],
            self.app_peer_data["cluster-set-domain-name"],
            OPERATOR_USERNAME,
            self.get_secret("app", OPERATOR_PASSWORD_KEY),  # pyright: ignore [reportArgumentType]
            REPLICATION_USERNAME,
            self.get_secret("app", REPLICATION_PASSWORD_KEY),  # pyright: ignore [reportArgumentType]
            MONITORING_USERNAME,
            self.get_secret("app", MONITORING_PASSWORD_KEY),  # pyright: ignore [reportArgumentType]
            BACKUPS_USERNAME,
            self.get_secret("app", BACKUPS_PASSWORD_KEY),  # pyright: ignore [reportArgumentType]
            self.unit.get_container(CONTAINER_NAME),
            self.k8s_helpers,
            self,
        )

    @property
    def refresh(self) -> charm_refresh.Kubernetes | None:
        """Return the Kubernetes refresh instance."""
        return self._refresh

    @property
    def _pebble_layer(self) -> Layer:
        """Return a layer for the mysqld pebble service."""
        mysqld_cmd = [
            MYSQLD_LOCATION,
            "--basedir=/usr",
            f"--datadir={MYSQL_DATA_DIR}",
            "--plugin-dir=/usr/lib/mysql/plugin",
            f"--log-error={MYSQL_LOG_ERROR}",
            f"--pid-file={self.unit_label}.pid",
        ]

        layer = {
            "summary": "mysqld services layer",
            "description": "pebble config layer for mysqld safe and exporter",
            "services": {
                MYSQLD_SERVICE: {
                    "override": "replace",
                    "summary": "mysql daemon",
                    "command": " ".join(mysqld_cmd),
                    "startup": "enabled",
                    "user": MYSQL_SYSTEM_USER,
                    "group": MYSQL_SYSTEM_GROUP,
                    "kill-delay": "24h",
                    "environment": {
                        "MYSQLD_PARENT_PID": 1,
                    },
                    "requires": [MYSQL_LOG_SERVICE],
                    "after": [MYSQL_LOG_SERVICE],
                },
                MYSQL_LOG_SERVICE: {
                    "override": "replace",
                    "summary": "tail log",
                    "command": f"tail -F {MYSQL_LOG_ERROR}",
                    "startup": "enabled",
                },
                MYSQLD_EXPORTER_SERVICE: {
                    "override": "replace",
                    "summary": "mysqld exporter",
                    "command": "/start-mysqld-exporter.sh",
                    "startup": "enabled" if self.has_cos_relation else "disabled",
                    "user": MYSQL_SYSTEM_USER,
                    "group": MYSQL_SYSTEM_GROUP,
                    "environment": {
                        "EXPORTER_USER": MONITORING_USERNAME,
                        "EXPORTER_PASS": self.get_secret("app", MONITORING_PASSWORD_KEY),
                    },
                },
                MYSQL_BINLOGS_COLLECTOR_SERVICE: {
                    "override": "replace",
                    "summary": "mysql-pitr-helper binlogs collector",
                    "command": "/start-mysql-pitr-helper-collector.sh",
                    "startup": "enabled"
                    if ("binlogs-collecting" in self.app_peer_data and self.unit.is_leader())
                    else "disabled",
                    "user": MYSQL_SYSTEM_USER,
                    "group": MYSQL_SYSTEM_GROUP,
                    "environment": self.backups.get_binlogs_collector_config()
                    if ("binlogs-collecting" in self.app_peer_data and self.unit.is_leader())
                    else {},
                },
            },
        }
        return Layer(layer)  # pyright: ignore [reportArgumentType]

    @property
    def unit_address(self) -> str:
        """Return the address of this unit."""
        return self.get_unit_address(self.unit)

    @property
    def is_unit_primary(self) -> bool:
        """Return True if this unit is a primary unit."""
        return self._mysql.get_primary_label() == self.unit_label

    @property
    def is_new_unit(self) -> bool:
        """Return whether the unit is a clean state.

        e.g. scaling from zero units
        """
        _default_unit_data_keys = {
            "egress-subnets",
            "ingress-address",
            "private-address",
        }
        return self.unit_peer_data.keys() == _default_unit_data_keys

    @property
    def text_logs(self) -> list:
        """Enabled text logs."""
        # slow logs isn't enabled by default
        text_logs = ["error"]

        if self.config.plugin_audit_enabled:
            text_logs.append("audit")

        return text_logs

    def unit_initialized(self, raise_exceptions: bool = False) -> bool:
        """Return whether a unit is started.

        Override parent class method to include container accessibility check.
        """
        container = self.unit.get_container(CONTAINER_NAME)
        if container.can_connect():
            return super().unit_initialized(raise_exceptions)
        else:
            return False

    def get_unit_hostname(self, unit_name: str | None = None) -> str:
        """Get the hostname.localdomain for a unit.

        Translate juju unit name to hostname.localdomain, necessary
        for correct name resolution under k8s.

        Args:
            unit_name: unit name
        Returns:
            A string representing the hostname.localdomain of the unit.
        """
        unit_name = unit_name or self.unit.name
        return f"{unit_name.replace('/', '-')}.{self.app.name}-endpoints"

    @retry(
        reraise=True,
        retry=retry_if_exception_type(RuntimeError),
        stop=stop_after_delay(120),
        wait=wait_fixed(2),
    )
    def get_unit_address(self, unit: Unit, relation_name: str = PEER) -> str:
        """Get fqdn/address for a unit.

        Translate the Juju unit name to a resolvable hostname
        and return the fully qualified domain name (with a trailing dot).
        Raises ``RuntimeError`` if the FQDN still cannot be resolved.
        """
        unit_hostname = self.get_unit_hostname(unit.name)
        try:
            unit_dns_domain = get_k8s_fqdn(unit_hostname)
        except RuntimeError:
            logger.warning("Unit DNS domain name is not propagated yet")
            raise

        # When fully propagated, DNS domain name should contain unit hostname.
        # For example:
        # Hostname: mysql-k8s-0.mysql-k8s-endpoints
        # Fully propagated: mysql-k8s-0.mysql-k8s-endpoints.dev.svc.cluster.local
        # Not propagated yet: 10-1-142-191.mysql-k8s.dev.svc.cluster.local
        if unit_hostname not in unit_dns_domain:
            logger.warning("Unit DNS domain name is not fully propagated yet.")
            raise RuntimeError("unit DNS domain name is not fully propagated yet")
        if unit_dns_domain == unit_hostname:
            logger.warning("Can't get fully qualified domain name for unit")
            raise RuntimeError("Can't get fully qualified domain name for unit")

        return dotappend(unit_dns_domain)

    def _all_peers_reachable(self) -> bool:
        """Return True if all peer units respond on MySQL port 3306.

        Quorum recovery must not run when peers are unreachable — that scenario
        indicates a network partition where the remote side may still be healthy.
        """
        for unit in self.peers.units:
            address = self.get_unit_address(unit)
            try:
                with socket.create_connection((address, 3306), timeout=2):
                    pass
            except OSError:
                return False
        return True

    def is_unit_busy(self) -> bool:
        """Returns whether the unit is busy."""
        return self._is_cluster_blocked()

    def _create_cluster(self) -> None:
        try:
            # Create the cluster when is the leader unit
            logger.info(f"Creating cluster {self.app_peer_data['cluster-name']}")
            self.create_cluster()
            self.unit.set_ports(3306, 33060)
            self.set_unit_status(self.build_unit_workload_status())
        except (
            MySQLCreateClusterError,
            MySQLCreateClusterSetError,
            MySQLInitializeJujuOperationsTableError,
            MySQLUnableToGetMemberStateError,
        ):
            logger.exception("Failed to initialize primary")
            raise

    def _get_primary_from_online_peer(self) -> str | None:
        """Get the primary address from an online peer."""
        for unit in self.peers.units:
            if self.peers.data[unit].get("member-state") == InstanceState.ONLINE:
                try:
                    return self._mysql.get_cluster_primary_address(
                        from_instance=self.get_unit_address(unit),
                    )
                except MySQLGetClusterPrimaryAddressError:
                    # try next unit
                    continue

    def _is_unit_waiting_to_join_cluster(self) -> bool:
        """Return if the unit is waiting to join the cluster."""
        # check base conditions for join a unit to the cluster
        # - workload accessible
        # - unit waiting flag set
        # - unit configured (users created/unit set to be a cluster node)
        # - unit not node of this cluster or cluster does not report this unit as member
        # - cluster is initialized on any unit
        return (
            self.unit.get_container(CONTAINER_NAME).can_connect()
            and self.unit_peer_data.get("member-state") == "waiting"
            and self.unit_configured
            and (
                not self.unit_initialized()
                or not self._mysql.is_instance_in_cluster(self.unit_label)
            )
            and self.cluster_initialized
        )

    def join_unit_to_cluster(self) -> None:
        """Join the unit to the cluster.

        Try to join the unit from the primary unit.
        """
        instance_label = self.get_unit_label(self.unit)
        instance_address = self.get_unit_address(self.unit)

        if not self._mysql.is_instance_in_cluster(instance_label):
            # Add new instance to the cluster
            try:
                cluster_primary = self._get_primary_from_online_peer()
                if not cluster_primary:
                    self.set_unit_status(WaitingStatus("waiting to get cluster primary from peer"))
                    logger.info("waiting: unable to retrieve the cluster primary from peer")
                    return

                from_instance = cluster_primary
                lock_instance = cluster_primary

                if self._mysql.get_cluster_node_count(from_instance) == GR_MAX_MEMBERS:
                    message = f"Cluster reached max size of {GR_MAX_MEMBERS} units. Standby."
                    self.set_unit_status(WaitingStatus(message))
                    logger.warning(message)
                    return

                # If instance is part of a replica cluster, locks are managed by
                # the primary cluster primary (i.e. cluster set global primary)
                if self._mysql.is_cluster_replica(from_instance):
                    lock_instance = self._mysql.get_cluster_global_primary_address(from_instance)

                # add random delay to mitigate collisions when multiple units are joining
                # due the difference between the time we test for locks and acquire them
                # Not used for cryptographic purpose
                sleep(random.uniform(0, 1.5))  # noqa: S311

                if self._mysql.are_locks_acquired(lock_instance, UNIT_ADD_LOCKNAME):
                    self.set_unit_status(WaitingStatus("waiting to join the cluster"))
                    logger.info("waiting: cluster lock is held")
                    return

                self.set_unit_status(MaintenanceStatus("joining the cluster"))

                # Stop GR for cases where the instance was previously part of the cluster
                # harmless otherwise
                self._mysql.stop_group_replication()

                # If instance already in cluster, before adding instance to cluster,
                # remove the instance from the cluster and call rescan_cluster()
                # without adding/removing instances to clean up stale users
                cluster_status = self._mysql.get_cluster_status(from_instance)
                if instance_label in cluster_status["defaultReplicaSet"]["topology"]:
                    self._mysql.remove_instance(
                        unit_label=instance_label,
                        from_instance=from_instance,
                        auto_dissolve=False,
                    )
                    self._mysql.rescan_cluster(
                        from_instance=from_instance,
                    )

                self._mysql.add_instance_to_cluster(
                    instance_address=instance_address,
                    instance_unit_label=instance_label,
                    from_instance=from_instance,
                    lock_instance=lock_instance,
                )
            except MySQLAddInstanceToClusterError:
                logger.info(f"Unable to add instance {instance_address} to cluster.")
                return
            except MySQLLockAcquisitionError:
                self.set_unit_status(WaitingStatus("waiting to join the cluster"))
                logger.info("waiting: failed to acquire lock when adding instance to cluster")
                return

        self.unit_peer_data["member-state"] = InstanceState.ONLINE.value
        self.set_unit_status(self.build_unit_workload_status())
        logger.info(f"Instance {instance_label} added to cluster")

    def _reconcile_pebble_layer(self, container: Container) -> None:
        """Reconcile pebble layer."""
        current_layer = container.get_plan()
        new_layer = self._pebble_layer

        if new_layer.services != current_layer.services:
            logger.info("Reconciling the pebble layer")

            container.add_layer(MYSQLD_SERVICE, new_layer, combine=True)
            # Do not wait for all services to successfully start as binlogs collector may restart several times
            # (pebble failure restart) until MySQL is ready
            container._pebble.replan_services(timeout=0)
            self._mysql.wait_until_mysql_connection()

            if (
                not self.has_cos_relation
                and container.get_services(MYSQLD_EXPORTER_SERVICE)[
                    MYSQLD_EXPORTER_SERVICE
                ].is_running()
            ):
                container.stop(MYSQLD_EXPORTER_SERVICE)

    def recover_unit_after_restart(self) -> None:
        """Wait for unit recovery/rejoin after restart."""
        recovery_attempts = 30
        logger.info("Recovering unit")
        if self.app.planned_units() == 1:
            self._mysql.reboot_from_complete_outage()
        else:
            try:
                for attempt in Retrying(
                    stop=stop_after_attempt(recovery_attempts), wait=wait_fixed(15)
                ):
                    with attempt:
                        self._mysql.hold_if_recovering()
                        if not self._mysql.is_instance_in_cluster(self.unit_label):
                            logger.debug(
                                "Instance not yet back in the cluster."
                                f" Retry {attempt.retry_state.attempt_number}/{recovery_attempts}"
                            )
                            raise Exception
            except RetryError:
                raise

    def _restart_group_replication(self) -> OperationResult:
        """Restarts Group replication on the instance."""
        relation = self.model.get_relation("rolling-ops")
        if not relation:
            logger.info("Skipping group replication restart")
            return OperationResult.RETRY_RELEASE

        ongoing_ops = [
            self.rolling_ops.is_waiting_callback("replication", unit.name)
            for unit in self.peers.units
        ]

        if self.is_unit_primary and any(ongoing_ops):
            logger.info("Skipping group replication restart")
            return OperationResult.RETRY_RELEASE

        if self.is_unit_primary and self.app.planned_units() > 1:
            try:
                new_primary = self.get_unit_address(self.peers.units.pop())
                logger.debug(f"Switching primary to {new_primary}")
                self._mysql.set_cluster_primary(new_primary)
            except MySQLSetClusterPrimaryError:
                logger.warning("Changing primary failed")
                return OperationResult.RETRY_HOLD

        cluster_primary = self._mysql.get_cluster_primary_address()
        if not cluster_primary:
            logger.warning("Getting primary failed")
            return OperationResult.RETRY_HOLD

        logger.info("Recreating group replication")
        self._mysql.rejoin_instance_to_cluster(
            unit_address=self.unit_address,
            unit_label=self.unit_label,
            from_instance=cluster_primary,
        )

        self._on_update_status(None)
        return OperationResult.RELEASE

    def _restart(self) -> OperationResult:
        """Restart the service."""
        container = self.unit.get_container(CONTAINER_NAME)
        if not container.can_connect():
            return OperationResult.RETRY_HOLD

        if not self.unit_initialized():
            logger.debug("Restarting standalone mysqld")
            container.restart(MYSQLD_SERVICE)
            return OperationResult.RETRY_HOLD

        if self.app.planned_units() > 1 and self.is_unit_primary:
            try:
                new_primary = self.get_unit_address(self.peers.units.pop())
                logger.debug(f"Switching primary to {new_primary}")
                self._mysql.set_cluster_primary(new_primary)
            except MySQLSetClusterPrimaryError:
                logger.warning("Changing primary failed")

        logger.debug("Restarting mysqld")
        self.set_unit_status(MaintenanceStatus("restarting MySQL"))
        container.pebble.restart_services([MYSQLD_SERVICE], timeout=3600)
        self.set_unit_status(MaintenanceStatus("recovering unit after restart"))
        sleep(10)
        self.recover_unit_after_restart()

        self._on_update_status(None)
        return OperationResult.RELEASE

    # =========================================================================
    # Charm event handlers
    # =========================================================================

    def _reconcile_mysqld_exporter(
        self, event: RelationCreatedEvent | RelationBrokenEvent
    ) -> None:
        """Handle a COS relation created or broken event."""
        if not self._is_peer_data_set:
            logger.debug("Unit not yet ready to reconcile mysqld exporter. Waiting...")
            return

        container = self.unit.get_container(CONTAINER_NAME)
        if not container.can_connect():
            # reconciliation is done on pebble ready
            logger.debug("Skip reconcile mysqld exporter: container not ready")
            return

        if not container.pebble.get_plan():
            # reconciliation is done on pebble ready
            logger.debug("Skip reconcile mysqld exporter: empty pebble layer")
            return

        if not self._mysql.is_data_dir_initialised():
            logger.debug("Skip reconcile mysqld exporter: mysql not initialised")
            return

        if self.is_new_unit:
            # scaling up from zero, treatment done on pebble-ready
            return

        self.current_event = event
        self._reconcile_pebble_layer(container)

    def _rotate_private_keys(self) -> None:
        """Rotates either of the TLS private keys if the config values are new."""
        new_client_private_key = self.config.tls_client_private_key
        old_client_private_key = self.app_peer_data.get("client-private-key", None)

        if new_client_private_key != old_client_private_key:
            self.tls.client_certificates_refresh_event.emit()
            if self.unit.is_leader():
                self.app_peer_data["client-private-key"] = new_client_private_key

        new_peer_private_key = self.config.tls_peer_private_key
        old_peer_private_key = self.app_peer_data.get("peer-private-key", None)

        if new_peer_private_key != old_peer_private_key:
            self.tls.peer_certificates_refresh_event.emit()
            if self.unit.is_leader():
                self.app_peer_data["peer-private-key"] = new_peer_private_key

    def _on_peer_relation_joined(self, _) -> None:
        """Handle the peer relation joined event."""
        # set some initial unit data
        self.unit_peer_data.setdefault("member-role", "UNKNOWN")
        self.unit_peer_data.setdefault("member-state", "waiting")

    def _on_config_changed(self, _: EventBase) -> None:
        """Handle the config changed event."""
        container = self.unit.get_container(CONTAINER_NAME)
        if not container.can_connect():
            # configuration also take places on pebble ready handler
            return

        if not self._is_peer_data_set:
            # skip when not initialized
            return

        if self._refresh is None:
            logger.warning("Refresh could be in progress")
        if self._refresh and self._refresh.in_progress:
            logger.debug("Refresh in progress")
            return

        config_content = self._mysql.read_file_content(MYSQLD_CONFIG_FILE)
        if not config_content:
            return

        logger.info("Persisting configuration changes to file")
        old_config = self.mysql_config.get_custom_config(config_content)
        new_config = self._write_mysqld_configuration()
        changed_config = compare_dictionaries(old_config, new_config)

        # Override log rotation
        self.log_rotate_setup.setup()

        # Rotate TLS keys
        self._rotate_private_keys()

        if (
            self.mysql_config.keys_requires_restart(changed_config)
            and self._mysql.is_mysqld_running()
        ):
            logger.info("Configuration change requires restart")
            self.rolling_ops.request_async_lock(callback_id="restart")
            return

        if dynamic_config := self.mysql_config.filter_static_keys(changed_config):
            # if only dynamic config changed, apply it
            logger.info("Configuration does not requires restart")
            for config in dynamic_config:
                self._mysql.set_dynamic_variable(config.removeprefix("loose-"), new_config[config])

    def _on_leader_elected(self, _) -> None:
        """Handle the leader elected event.

        Set config values in the peer relation databag if not already set.
        """
        # Set required passwords if not already set
        required_passwords = [
            OPERATOR_PASSWORD_KEY,
            REPLICATION_PASSWORD_KEY,
            MONITORING_PASSWORD_KEY,
            BACKUPS_PASSWORD_KEY,
        ]

        logger.info("Generating internal user credentials")
        for required_password in required_passwords:
            if not self.get_secret("app", required_password):
                self.set_secret(
                    "app", required_password, generate_random_password(DEFAULT_PASSWORD_LENGTH)
                )

        # Create and set cluster and cluster-set names in the peer relation databag
        common_hash = self.generate_random_hash()
        self.app_peer_data.setdefault(
            "cluster-name", self.config.cluster_name or f"cluster-{common_hash}"
        )
        self.app_peer_data.setdefault(
            "cluster-set-domain-name", self.config.cluster_set_name or f"cluster-set-{common_hash}"
        )

    def _write_mysqld_configuration(self) -> dict:
        """Write the mysqld configuration to the file."""
        memory_limit_bytes = (self.config.profile_limit_memory or 0) * BYTES_1MB
        new_config_content, new_config_dict = self._mysql.render_mysqld_configuration(
            profile=self.config.profile,
            audit_log_enabled=self.config.plugin_audit_enabled,
            audit_log_strategy=self.config.plugin_audit_strategy,
            audit_log_policy=self.config.logs_audit_policy,
            memory_limit=memory_limit_bytes,
            experimental_max_connections=self.config.experimental_max_connections,
            binlog_retention_days=self.config.binlog_retention_days,
        )
        self._mysql.write_content_to_file(path=MYSQLD_CONFIG_FILE, content=new_config_content)
        return new_config_dict

    def _configure_instance(self, container) -> None:
        """Configure the instance for use in Group Replication."""
        # Run mysqld for the first time to
        # bootstrap the data directory and users
        logger.info("Initializing mysqld")
        try:
            self._mysql.initialise_mysqld()

            # Add the pebble layer
            logger.info("Adding pebble layer")
            container.add_layer(MYSQLD_SERVICE, self._pebble_layer, combine=True)
            container.restart(MYSQLD_SERVICE)

            logger.info("Waiting for instance to be ready")
            self._mysql.wait_until_mysql_connection(check_port=False)

            logger.info("Set operator user and restart mysqld")
            self._mysql.set_operator_user_and_start_mysqld()

            logger.info("Configuring initialized mysqld")
            # Configure all base users and revoke privileges from the root users
            self._mysql.configure_mysql_router_roles()
            self._mysql.configure_mysql_system_roles()
            self._mysql.configure_mysql_system_users()
            self._mysql.drop_root_user()

            default_components = ["binlog_utils_udf", "validate_password"]
            optional_components = []
            if self.config.plugin_audit_enabled:
                optional_components.append("audit_log_filter")

            self._mysql.install_components([
                *default_components,
                *optional_components,
            ])

            # Configure instance as a cluster node
            self._mysql.configure_instance()
            self._mysql.wait_until_mysql_connection()
        except (
            MySQLInitialiseMySQLDError,
            MySQLServiceNotRunningError,
            MySQLConfigureMySQLRolesError,
            MySQLConfigureMySQLUsersError,
            MySQLConfigureInstanceError,
            MySQLDropRootUserError,
            ChangeError,
            TimeoutError,
            ModelError,
        ):
            # On any error, reset the data directory so hook is retried
            # on empty data directory
            # https://github.com/canonical/mysql-k8s-operator/issues/447
            self._mysql.reset_data_dir()
            raise

        if self.has_cos_relation:
            if container.get_services(MYSQLD_EXPORTER_SERVICE)[
                MYSQLD_EXPORTER_SERVICE
            ].is_running():
                # Restart exporter service after configuration
                container.restart(MYSQLD_EXPORTER_SERVICE)
            else:
                container.start(MYSQLD_EXPORTER_SERVICE)

    def _mysql_pebble_ready_checks(self, event) -> bool:
        """Executes some checks to see if it is safe to execute the pebble ready handler."""
        if not self._is_peer_data_set:
            self.set_unit_status(WaitingStatus("Waiting for leader election."))
            logger.debug("Leader not ready yet, waiting...")
            return True

        container = event.workload
        if not container.can_connect():
            logger.debug("Pebble in container not ready, waiting...")
            return True

        return False

    def _on_mysql_pebble_ready(self, event) -> None:
        """Pebble ready handler.

        Define and start a pebble service and bootstrap instance.
        """
        if self._mysql_pebble_ready_checks(event):
            event.defer()
            return

        if self._refresh is None:
            logger.warning("Refresh could be in progress")
        if self._refresh and self._refresh.in_progress:  # noqa: SIM102
            if not self._refresh.workload_allowed_to_start:
                logger.debug("Refresh in progress")
                event.defer()
                return

        container = event.workload
        self._write_mysqld_configuration()

        self.log_rotate_setup.setup()

        if self._mysql.is_data_dir_initialised():
            # Data directory is already initialised, skip configuration
            self.set_unit_status(MaintenanceStatus("Starting mysqld"))
            logger.info("Data directory is already initialised, skipping configuration")
            self._reconcile_pebble_layer(container)
            if self.is_new_unit:
                # when unit is new and has data, it means the app is scaling out
                # from zero units
                logger.info("Scaling out from zero units")
                if self.unit.is_leader():
                    # create the cluster due it being dissolved on scale-down
                    self.create_cluster()
                    self._on_update_status(None)
                else:
                    # Non-leader units try to join cluster
                    self.set_unit_status(WaitingStatus("Waiting for instance to join the cluster"))
                    self.unit_peer_data.update({
                        "member-role": InstanceRole.SECONDARY.value,
                        "member-state": "waiting",
                    })
            return

        self.set_unit_status(MaintenanceStatus("Initialising mysqld"))

        # First run setup
        self._configure_instance(container)

        # We consider cluster initialized only if a primary already exists
        # (as there can be metadata in the database but no primary if pod
        # crashes while cluster is being created)
        if not self.unit.is_leader() or (
            self.cluster_initialized and self._get_primary_from_online_peer()
        ):
            # Non-leader units try to join cluster
            self.set_unit_status(WaitingStatus("Waiting for instance to join the cluster"))
            self.unit_peer_data.update({
                "member-role": InstanceRole.SECONDARY.value,
                "member-state": "waiting",
            })
            self.join_unit_to_cluster()
            return

        self._create_cluster()
        self._mysql.reconcile_binlogs_collection(force_restart=True)

    def _handle_potential_cluster_crash_scenario(self, state: str) -> bool:  # noqa: C901
        """Handle potential full cluster crash scenarios.

        Returns:
            bool
                False if the handling worked correctly and the caller can continue,
                True otherwise.

        """
        single_node_cluster = self.only_one_cluster_node_thats_uninitialized
        if not single_node_cluster and not self.cluster_initialized:
            return True

        # A surviving member can stay ONLINE in its local view while the
        # cluster has lost quorum (majority UNREACHABLE). The reboot-from-
        # complete-outage path below only fires on state == OFFLINE, so
        # without this the leader stays stuck and the cluster never recovers.
        if state == InstanceState.ONLINE and self._mysql.is_cluster_in_no_quorum():
            logger.warning("Cluster has no quorum")
            if self.peers.units and not self._all_peers_reachable():
                logger.warning("Skipping quorum recovery: not all peers reachable")
                return True
            try:
                # reboot_cluster_from_complete_outage rejects an instance whose
                # GR is still running; drop it to OFFLINE first.
                self._mysql.stop_group_replication()
                if self.unit.is_leader():
                    # run on leader only for coordinate recovery
                    logger.warning("Attempting reboot from complete outage")
                    self._mysql.reboot_from_complete_outage()
                    return False
            except MySQLRebootFromCompleteOutageError:
                logger.error("Failed to reboot cluster from complete outage")
                self.set_unit_status(BlockedStatus("failed to recover cluster"))
            return True

        if state == InstanceState.RECOVERING:
            return True

        if state == InstanceState.OFFLINE:
            # Group Replication is active but the member does not belong to any group
            all_states = {
                self.peers.data[unit].get("member-state", "UNKNOWN") for unit in self.peers.units
            }

            if (all_states | {state} == {state} and self.unit.is_leader()) or (
                single_node_cluster and all_states == {"waiting"}
            ):
                # All instance are off, reboot cluster from outage from the leader unit
                logger.info("Attempting reboot from complete outage.")
                try:
                    # Need condition to avoid rebooting on all units of application
                    if self.unit.is_leader() or single_node_cluster:
                        self._mysql.reboot_from_complete_outage()
                except MySQLRebootFromCompleteOutageError:
                    logger.error("Failed to reboot cluster from complete outage.")

                    if single_node_cluster and all_states == {"waiting"}:
                        self._mysql.drop_group_replication_metadata_schema()
                        self.create_cluster()
                        self.set_unit_status(self.build_unit_workload_status())
                    else:
                        self.set_unit_status(BlockedStatus("failed to recover cluster."))
                return True

            if self._mysql.is_cluster_auto_rejoin_ongoing():
                logger.info("Cluster auto-rejoin attempts are still ongoing.")
            else:
                logger.info("Cluster auto-rejoin attempts are exhausted. Attempting manual rejoin")
                self._execute_manual_rejoin()

            return True

        return False

    def _execute_manual_rejoin(self) -> None:
        """Executes an instance manual rejoin.

        It is supposed to be called when the MySQL auto-rejoin attempts have been exhausted,
        on an OFFLINE replica that still belongs to the cluster
        """
        if not self._mysql.instance_belongs_to_cluster(self.unit_label):
            logger.warning("Instance does not belong to the cluster. Cannot perform manual rejoin")
            return

        cluster_primary = self._get_primary_from_online_peer()
        if not cluster_primary:
            logger.warning("Instance does not have ONLINE peers. Cannot perform manual rejoin")
            return

        # add random delay to mitigate collisions when multiple units are rejoining
        # due the difference between the time we test for locks and acquire them
        # Not used for cryptographic purpose
        sleep(random.uniform(0, 1.5))  # noqa: S311

        if self._mysql.are_locks_acquired(cluster_primary, UNIT_ADD_LOCKNAME):
            logger.info("waiting: cluster lock is held")
            return
        try:
            self._mysql.rejoin_instance_to_cluster(
                unit_address=self.unit_address,
                unit_label=self.unit_label,
                from_instance=cluster_primary,
            )
            return
        except MySQLRejoinInstanceToClusterError:
            logger.warning("Can't rejoin instance to cluster. Falling back to remove and add.")

        self._mysql.remove_instance(
            unit_label=self.unit_label,
            from_instance=cluster_primary,
            auto_dissolve=False,
        )
        self._mysql.add_instance_to_cluster(
            instance_address=self.unit_address,
            instance_unit_label=self.unit_label,
            from_instance=cluster_primary,
        )

    def update_endpoints(self) -> None:
        """Update the endpoints for the database relation."""
        self.database_relation._configure_endpoints(None)
        self._on_update_status(None)

    def _is_cluster_blocked(self) -> bool:
        """Performs cluster state checks for the update-status handler.

        Returns: a boolean indicating whether the update-status (caller) should
            no-op and return.
        """
        # We need to query member state from the server since member state would
        # be 'offline' if pod rescheduled during cluster creation, however
        # member-state in the unit peer databag will be 'waiting'
        try:
            member_state = self._mysql.get_member_state()
        except MySQLUnableToGetMemberStateError:
            logger.error("Error getting member state while checking if cluster is blocked")
            self.set_unit_status(MaintenanceStatus("Unable to get member state"))
            return True

        if member_state == "UNKNOWN" or member_state == InstanceState.RECOVERING:
            # avoid changing status while tls is being set up or charm is being initialized
            logger.info(f"Unit {member_state=}")
            return True

        # only assert for async replication state when online
        if member_state == InstanceState.ONLINE and not (
            self.replication_consumer.idle and self.replication_offer.idle
        ):
            logger.info("Skip status update when setting async replication")
            return True

        return False

    def _on_update_status(self, _: UpdateStatusEvent | None) -> None:
        """Handle the update status event."""
        if self._refresh is None:
            logger.debug("Refresh could be in progress")
            return
        if self._refresh and self._refresh.in_progress:
            logger.debug("Refresh in progress")
            return

        if not self.unit.is_leader() and self._is_unit_waiting_to_join_cluster():
            # join cluster test takes precedence over blocked test
            # due to matching criteria
            logger.info("Attempting to join cluster")
            self.join_unit_to_cluster()
            return

        if self._is_cluster_blocked():
            logger.info("Cluster is blocked. Skipping.")
            return

        if not self._mysql.is_mysqld_running():
            logger.info("Cannot connect to pebble in the mysql container")
            return

        # retrieve and persist state for every unit
        try:
            role = self._mysql.get_member_role()
            state = self._mysql.get_member_state()
        except MySQLUnableToGetMemberStateError:
            logger.error("Error getting member state. Avoiding potential cluster crash recovery")
            self.set_unit_status(MaintenanceStatus("Unable to get member state"))
            return

        logger.info(f"Unit workload member-state is {state} with member-role {role}")
        self.unit_peer_data["member-role"] = role
        self.unit_peer_data["member-state"] = state
        self.set_unit_status(self.build_unit_workload_status())

        # TODO: Logic here is almost the opposite as the machines charm, but not quite
        # We should review and fix it
        if not self._handle_potential_cluster_crash_scenario(state):
            self._set_app_status(state)

    def _set_app_status(self, state: str) -> None:
        """Set the application status based on the cluster state."""
        if not self.unit.is_leader() or state != InstanceState.ONLINE:
            return

        block_message = self.app_peer_data.get("s3-block-message")
        if block_message:
            self.app.status = BlockedStatus(block_message)
            return

        self.app.status = self.build_app_workload_status()

    def set_unit_status(self, status: ops.StatusBase):
        """Set unit status without overriding higher priority refresh status."""
        if self._refresh is None:
            self.unit.status = status
            return

        if self._refresh.unit_status_higher_priority:
            return

        refresh_status = self._refresh.unit_status_lower_priority()
        if refresh_status and isinstance(status, ActiveStatus):
            status = refresh_status

        self.unit.status = status

    def _on_peer_relation_changed(self, event: RelationChangedEvent) -> None:
        """Handle the relation changed event."""
        # This handler is only taking care of setting
        # active status for secondary units
        if not self._is_peer_data_set:
            # Avoid running too early
            event.defer()
            return

        if self._is_unit_waiting_to_join_cluster():
            self.join_unit_to_cluster()

        if not self._mysql.reconcile_binlogs_collection(force_restart=True):
            logger.error("Failed to reconcile binlogs collection during peer relation event")

    def _on_peer_relation_departed(self, event: RelationDepartedEvent) -> None:
        if not self._mysql.reconcile_binlogs_collection(force_restart=True):
            logger.error("Failed to reconcile binlogs collection during peer departed event")

    def _on_storage_detaching(self, _) -> None:
        """Handle the database storage detaching event."""
        # Only executes if the unit was initialised
        if not self.unit_initialized():
            return

        # No need to remove the instance from the cluster if it is not a member of the cluster
        if not self._mysql.is_instance_in_cluster(self.unit_label):
            return

        if self.is_unit_primary and self.unit.name.split("/")[1] != "0":
            # Preemptively switch primary to unit 0
            logger.info("Switching primary to unit 0")
            try:
                self._mysql.set_cluster_primary(
                    new_primary_address=get_k8s_fqdn(self.get_unit_hostname(f"{self.app.name}/0"))
                )
            except MySQLSetClusterPrimaryError:
                logger.warning("Failed to switch primary to unit 0")

        # If instance is part of a replica cluster, locks are managed by
        # the primary cluster primary (i.e. cluster set global primary)
        from_instance = None
        if self._mysql.is_cluster_replica():
            from_instance = self._mysql.get_cluster_global_primary_address()

        # The following operation uses locks to ensure that only one instance is removed
        # from the cluster at a time (to avoid split-brain or lack of majority issues)
        self._mysql.remove_instance(self.unit_label, from_instance=from_instance)

        # Inform other hooks of current status
        self.unit_peer_data["unit-status"] = "removing"

        if self.unit.is_leader():
            # Update 'units-added-to-cluster' counter in the peer relation databag
            units = int(self.app_peer_data.get("units-added-to-cluster", 1))
            self.app_peer_data["units-added-to-cluster"] = str(units - 1)


if __name__ == "__main__":
    main(MySQLOperatorCharm)
