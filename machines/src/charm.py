#!/usr/bin/env python3
# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

"""Charmed Machine Operator for MySQL."""

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
from charms.grafana_agent.v0.cos_agent import COSAgentProvider, ProtocolNotFoundError
from charms.mysql.v0.async_replication import (
    RELATION_CONSUMER,
    RELATION_OFFER,
    MySQLAsyncReplicationConsumer,
    MySQLAsyncReplicationOffer,
)
from charms.mysql.v0.backups import S3_INTEGRATOR_RELATION_NAME, MySQLBackups
from charms.mysql.v0.mysql import (
    UNIT_ADD_LOCKNAME,
    Error,
    InstanceRole,
    InstanceState,
    MySQLAddInstanceToClusterError,
    MySQLCharmBase,
    MySQLComponentInstallError,
    MySQLConfigureInstanceError,
    MySQLConfigureMySQLRolesError,
    MySQLConfigureMySQLUsersError,
    MySQLCreateClusterError,
    MySQLCreateClusterSetError,
    MySQLGetClusterPrimaryAddressError,
    MySQLGetMySQLVersionError,
    MySQLInitializeJujuOperationsTableError,
    MySQLLockAcquisitionError,
    MySQLRebootFromCompleteOutageError,
    MySQLRejoinInstanceToClusterError,
    MySQLSetClusterPrimaryError,
    MySQLStartMySQLDError,
    MySQLUnableToGetMemberStateError,
)
from object_storage import S3Requirer
from ops import (
    ActiveStatus,
    BlockedStatus,
    InstallEvent,
    MaintenanceStatus,
    RelationBrokenEvent,
    RelationChangedEvent,
    RelationCreatedEvent,
    RelationDepartedEvent,
    StartEvent,
    Unit,
    WaitingStatus,
)
from ops_tracing import Tracing, set_destination
from tenacity import (
    RetryError,
    Retrying,
    retry_if_exception_type,
    stop_after_attempt,
    stop_after_delay,
    wait_exponential,
    wait_fixed,
)

from config import CharmConfig, MySQLConfig
from constants import (
    BACKUPS_PASSWORD_KEY,
    BACKUPS_USERNAME,
    CHARMED_MYSQL_SNAP_NAME,
    CHARMED_MYSQLD_SERVICE,
    COS_AGENT_RELATION_NAME,
    DB_RELATION_NAME,
    DEFAULT_PASSWORD_LENGTH,
    GR_MAX_MEMBERS,
    MONITORING_PASSWORD_KEY,
    MONITORING_USERNAME,
    MYSQL_EXPORTER_PORT,
    MYSQLD_CUSTOM_CONFIG_FILE,
    MYSQLD_SOCK_FILE,
    OPERATOR_PASSWORD_KEY,
    OPERATOR_USERNAME,
    PEER,
    REPLICATION_PASSWORD_KEY,
    REPLICATION_USERNAME,
    TRACING_PROTOCOL,
)
from log_rotation_setup import LogRotationSetup
from mysql_vm_helpers import (
    MySQL,
    MySQLCreateCustomMySQLDConfigError,
    MySQLInitialiseMySQLDError,
    MySQLInstallError,
    SnapServiceOperationError,
    instance_hostname,
    is_volume_mounted,
    snap,
    snap_service_operation,
)
from refresh import MachinesMySQLRefresh
from relations.mysql_provider import MySQLProvider
from relations.tls import TLS
from services.events import CharmServicesEvents
from services.managers import IPAddressManager, SelfHealingManager
from services.observers import IPAddressObserver, RotateMySQLLogsObserver, SelfHealingMySQLObserver
from utils import compare_dictionaries, generate_random_password

logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


class StorageUnavailableError(Exception):
    """Cannot find storage mountpoint."""


class MySQLDNotRestartedError(Error):
    """Exception raised when MySQLD is not restarted after configuring instance."""


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

        self.framework.observe(self.on.install, self._on_install)
        self.framework.observe(self.on.leader_elected, self._on_leader_elected)
        self.framework.observe(self.on.leader_settings_changed, self._on_leader_settings_changed)
        self.framework.observe(self.on.config_changed, self._on_config_changed)
        self.framework.observe(self.on.start, self._on_start)
        self.framework.observe(self.on.update_status, self._on_update_status)

        self.framework.observe(self.on.archive_storage_detaching, self._on_storage_detaching)
        self.framework.observe(self.on.data_storage_detaching, self._on_storage_detaching)
        self.framework.observe(self.on.logs_storage_detaching, self._on_storage_detaching)
        self.framework.observe(self.on.temp_storage_detaching, self._on_storage_detaching)

        self.framework.observe(self.on[PEER].relation_changed, self._on_peer_relation_changed)
        self.framework.observe(self.on[PEER].relation_departed, self._on_peer_relation_departed)

        self.mysql_config = MySQLConfig()
        self.database_relation = MySQLProvider(self)
        self.tls = TLS(self)
        self._grafana_agent = COSAgentProvider(
            self,
            metrics_endpoints=[
                {"path": "/metrics", "port": MYSQL_EXPORTER_PORT},
            ],
            metrics_rules_dir="./src/alert_rules/prometheus",
            logs_rules_dir="./src/alert_rules/loki",
            log_slots=[f"{CHARMED_MYSQL_SNAP_NAME}:logs"],
            tracing_protocols=[TRACING_PROTOCOL],
        )
        self.framework.observe(
            self.on[COS_AGENT_RELATION_NAME].relation_created, self._on_cos_agent_relation_created
        )
        self.framework.observe(
            self.on[COS_AGENT_RELATION_NAME].relation_broken, self._on_cos_agent_relation_broken
        )

        self.s3_integrator = S3Requirer(self, S3_INTEGRATOR_RELATION_NAME)
        self.backups = MySQLBackups(self, self.s3_integrator)

        try:
            self._refresh = charm_refresh.Machines(
                MachinesMySQLRefresh(
                    workload_name="MySQL",
                    charm_name="mysql",
                    _charm=self,
                )
            )
        except charm_refresh.PeerRelationNotReady:
            self.unit.status = MaintenanceStatus("Waiting for peer relation")
            self._refresh = None
        except charm_refresh.UnitTearingDown:
            self.unit.status = MaintenanceStatus("Tearing down")
            self._refresh = None
        else:
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

        self.hostname_observer = IPAddressObserver(self)
        self.hostname_manager = IPAddressManager(self)
        self.hostname_manager.start_manager()

        self.self_healing_observer = SelfHealingMySQLObserver(self)
        self.self_healing_manager = SelfHealingManager(self)
        self.self_healing_manager.start_manager()

        self.log_rotation_setup = LogRotationSetup(self)
        self.log_rotate_observer = RotateMySQLLogsObserver(self)

        self.replication_offer = MySQLAsyncReplicationOffer(self)
        self.replication_consumer = MySQLAsyncReplicationConsumer(self)

        self.tracing = Tracing(self, tracing_relation_name="tracing")
        self._charm_tracing_config()

    # =======================
    #  Charm Lifecycle Hooks
    # =======================

    def _on_install(self, _: InstallEvent) -> None:
        """Handle the install event."""
        self.set_unit_status(MaintenanceStatus("Installing MySQL"))

        if not is_volume_mounted():
            # https://github.com/juju/juju/issues/21135
            logger.error("Data directory not attached.")
            raise StorageUnavailableError

        if self.install_workload():
            self.set_unit_status(WaitingStatus("Waiting to start MySQL"))
        else:
            self.set_unit_status(BlockedStatus("Failed to install and configure MySQL"))

    def _on_leader_elected(self, _) -> None:
        """Handle the leader elected event."""
        # Set MySQL config values in the peer relation databag
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
        self.unit_peer_data.update({"leader": "true"})

        # Create and set cluster and cluster-set names in the peer relation databag
        common_hash = self.generate_random_hash()
        self.app_peer_data.setdefault(
            "cluster-name", self.config.cluster_name or f"cluster-{common_hash}"
        )
        self.app_peer_data.setdefault(
            "cluster-set-domain-name", self.config.cluster_set_name or f"cluster-set-{common_hash}"
        )

    def _on_leader_settings_changed(self, _) -> None:
        """Handle the leader settings changed event."""
        self.unit_peer_data.update({"leader": "false"})

    def _on_config_changed(self, _) -> None:
        """Handle the config changed event."""
        if not self._is_peer_data_set:
            # skip when not initialized
            return

        if self._refresh is None:
            logger.warning("Refresh could be in progress")
        if self._refresh and self._refresh.in_progress:
            logger.debug("Refresh in progress")
            return

        config_content = self._mysql.read_file_content(MYSQLD_CUSTOM_CONFIG_FILE)
        if not config_content:
            return

        logger.info("Persisting configuration changes to file")
        old_config = self.mysql_config.get_custom_config(config_content)
        new_config = self._mysql.write_mysqld_config()
        changed_config = compare_dictionaries(old_config, new_config)

        # Override log rotation
        self.log_rotation_setup.setup()

        # Rotate TLS keys
        self._rotate_private_keys()

        if (
            self.mysql_config.keys_requires_restart(changed_config)
            and self._mysql.is_mysqld_running()
        ):
            logger.info("Configuration change requires restart")
            self.rolling_ops.request_async_lock(callback_id="restart")

        elif dynamic_config := self.mysql_config.filter_static_keys(changed_config):
            # if only dynamic config changed, apply it
            logger.info("Configuration does not requires restart")
            for config in dynamic_config:
                if config not in new_config:
                    # skip removed configs
                    continue
                self._mysql.set_dynamic_variable(config.removeprefix("loose-"), new_config[config])

    def _on_start(self, event: StartEvent) -> None:  # noqa: C901
        """Handle the start event.

        Configure MySQL users and the instance for use in an InnoDB cluster.
        """
        if not self._can_start(event):
            return

        self.set_unit_status(MaintenanceStatus("Setting up cluster node"))

        try:
            self.workload_initialise()
        except MySQLInitialiseMySQLDError:
            self.set_unit_status(BlockedStatus("Failed to initialize MySQL data directory"))
            return
        except MySQLConfigureMySQLRolesError:
            self.set_unit_status(BlockedStatus("Failed to initialize MySQL roles"))
            return
        except MySQLConfigureMySQLUsersError:
            self.set_unit_status(BlockedStatus("Failed to initialize MySQL users"))
            return
        except MySQLConfigureInstanceError:
            self.set_unit_status(BlockedStatus("Failed to configure instance for InnoDB"))
            return
        except MySQLCreateCustomMySQLDConfigError:
            self.set_unit_status(BlockedStatus("Failed to create custom mysqld config"))
            return
        except MySQLStartMySQLDError:
            self.set_unit_status(BlockedStatus("Failed to start mysqld server"))
            return
        except MySQLDNotRestartedError:
            self.set_unit_status(BlockedStatus("Failed to restart instance"))
            return
        except MySQLComponentInstallError:
            logger.warning("Failed to install MySQL components")
        except MySQLGetMySQLVersionError:
            logger.debug("Fail to get MySQL version")

    def _on_peer_relation_changed(self, event: RelationChangedEvent) -> None:
        """Handle the peer relation changed event."""
        # Only execute if peer relation data contains cluster config values
        if not self._is_peer_data_set:
            event.defer()
            return

        # Update endpoint addresses
        self.update_endpoint_addresses()

        if self._is_unit_waiting_to_join_cluster():
            self.join_unit_to_cluster()
            self.unit.set_ports(3306, 33060)

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

        def _get_leader_unit() -> Unit | None:
            """Get the leader unit."""
            for unit in self.peers.units:
                if self.peers.data[unit]["leader"] == "true":
                    return unit

        if self.is_unit_primary() and not self.unit.is_leader():
            # Preemptively switch primary to unit leader
            logger.info("Switching primary to the leader unit")
            if leader_unit := _get_leader_unit():
                try:
                    self._mysql.set_cluster_primary(
                        new_primary_address=self.get_unit_address(leader_unit, PEER)
                    )
                except MySQLSetClusterPrimaryError:
                    logger.warning("Failed to switch primary to leader unit")

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

    def _charm_tracing_config(self) -> None:
        """Utility function to set tracing destination."""
        if not self._grafana_agent.is_ready():
            return

        try:
            endpoint = self._grafana_agent.get_tracing_endpoint("otlp_http")
            if not endpoint:
                return
        except ProtocolNotFoundError:
            logger.warning(
                "Endpoint for tracing wasn't provided as tracing backend isn't ready yet."
                "If grafana-agent isn't connected to a tracing backend, integrate it."
                "Otherwise this issue should resolve itself in a few events."
            )
            return

        if endpoint.startswith("https://"):
            logger.warning("Cannot send traces to an https endpoint without a certificate.")
            return

        set_destination(f"{endpoint}/v1/traces", None)

    def _handle_non_online_instance_status(self, state: str) -> bool:  # noqa: C901
        """Helper method to handle non-online instance statuses.

        Invoked from the update status event handler.
        """
        # A surviving member can stay ONLINE in its local view while the
        # cluster has lost quorum (majority UNREACHABLE). The reboot-from-
        # complete-outage path below only fires on state == OFFLINE, so
        # without this the leader stays stuck and the cluster never recovers.
        if state == InstanceState.ONLINE and self._mysql.is_cluster_in_no_quorum():
            logger.warning("Cluster has lost quorum")
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
            # server is in the process of becoming an active member
            logger.info("Instance is being recovered")
            return True

        if state == InstanceState.OFFLINE:
            # Group Replication is active but the member does not belong to any group
            all_states = {
                self.peers.data[unit].get("member-state", "UNKNOWN") for unit in self.peers.units
            }

            if all_states | {state} == {state} and self.unit.is_leader():
                loopback_entry_exists = self.hostname_observer.update_etc_hosts(None)
                if loopback_entry_exists and not snap_service_operation(
                    CHARMED_MYSQL_SNAP_NAME, CHARMED_MYSQLD_SERVICE, "restart"
                ):
                    self.set_unit_status(
                        BlockedStatus("Unable to restart before rebooting from complete outage")
                    )
                    return False

                self._mysql.wait_until_mysql_connection()

                # All instance are off or its a single unit cluster
                # reboot cluster from outage from the leader unit
                logger.info("Attempting reboot from complete outage.")
                try:
                    # reboot from outage forcing it when it a single unit
                    self._mysql.reboot_from_complete_outage()
                    return True
                except MySQLRebootFromCompleteOutageError:
                    logger.error("Failed to reboot cluster from complete outage.")
                    self.set_unit_status(BlockedStatus("failed to recover cluster."))
                    return False

            if self._mysql.is_cluster_auto_rejoin_ongoing():
                logger.info("Cluster auto-rejoin attempts are still ongoing.")
            else:
                logger.info("Cluster auto-rejoin attempts are exhausted. Attempting manual rejoin")
                self._execute_manual_rejoin()

        if state == InstanceState.UNREACHABLE:
            try:
                if not snap_service_operation(
                    CHARMED_MYSQL_SNAP_NAME, CHARMED_MYSQLD_SERVICE, "restart"
                ):
                    # mysqld access not possible and daemon restart fails
                    # force reset necessary
                    self.set_unit_status(BlockedStatus("Unable to recover from unreachable state"))
                    return False
            except SnapServiceOperationError as e:
                self.set_unit_status(BlockedStatus(e.message))
                return False

        return True

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
                unit_address=self.unit_fqdn,
                unit_label=self.unit_label,
                from_instance=cluster_primary,
            )
            return
        except MySQLRejoinInstanceToClusterError:
            logger.warning("Can't rejoin instance to the cluster. Falling back to remove and add")

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

    def _set_app_status(self, state: str) -> None:
        """Set the application status based on the cluster state."""
        if not self.unit.is_leader() or state != InstanceState.ONLINE:
            return

        block_message = self.app_peer_data.get("s3-block-message")
        if block_message:
            self.app.status = BlockedStatus(block_message)
            return

        self.app.status = self.build_app_workload_status()

    def _on_update_status(self, _) -> None:
        """Handle update status.

        Takes care of workload health checks.
        """
        if (
            not self.cluster_initialized
            or not self.unit_peer_data.get("member-role")
            or not is_volume_mounted()
        ):
            # health checks only after cluster and member are initialised
            logger.info("skip status update when not initialized")
            return
        if (
            self.unit_peer_data.get("member-state") == "waiting"
            and not self.unit_configured
            and not self.unit_initialized()
            and not self.unit.is_leader()
        ):
            # avoid changing status while in initialising
            logger.info("skip status update while initialising")
            return

        if self._refresh is None:
            logger.debug("Refresh could be in progress")
            return
        if self._refresh and self._refresh.in_progress:
            logger.debug("Refresh in progress")
            return

        if not (self.replication_offer.idle and self.replication_consumer.idle):
            # avoid changing status while in async replication
            logger.debug("skip status update while setting up async replication")
            return

        if self._is_unit_waiting_to_join_cluster():
            self.join_unit_to_cluster()
            return

        # retrieve and persist state for every unit
        try:
            role = self._mysql.get_member_role()
            state = self._mysql.get_member_state()
        except MySQLUnableToGetMemberStateError:
            role = "UNKNOWN"
            state = "UNREACHABLE"

        logger.info(f"Unit workload member-state is {state} with member-role {role}")
        self.unit_peer_data["member-role"] = role
        self.unit_peer_data["member-state"] = state
        self.set_unit_status(self.build_unit_workload_status())

        if not self._handle_non_online_instance_status(state):
            return

        self._set_app_status(state)

    def _on_cos_agent_relation_created(self, event: RelationCreatedEvent) -> None:
        """Handle the cos_agent relation created event.

        Enable the mysqld-exporter snap service.
        """
        if not self._is_peer_data_set:
            logger.debug("Charm not yet set up. Deferring")
            event.defer()
            return

        self._mysql.connect_mysql_exporter()

    def _on_cos_agent_relation_broken(self, _: RelationBrokenEvent) -> None:
        """Handle the cos_agent relation broken event.

        Disable the mysqld-exporter snap service.
        """
        if not self._is_peer_data_set:
            return

        self._mysql.stop_mysql_exporter()

    # =======================
    #  Helpers
    # =======================

    @property
    def _mysql(self) -> MySQL:
        """Returns an instance of the MySQL object."""
        return MySQL(
            self.unit_fqdn,
            MYSQLD_SOCK_FILE,
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
            self,
        )

    @property
    def refresh(self) -> charm_refresh.Machines | None:
        """Return the Machines refresh instance."""
        return self._refresh

    @property
    def _has_blocked_status(self) -> bool:
        """Returns whether the unit is in a blocked state."""
        return isinstance(self.unit.status, BlockedStatus)

    @property
    def unit_fqdn(self) -> str:
        """Returns the unit's FQDN."""
        return socket.getfqdn()

    def is_unit_busy(self) -> bool:
        """Returns whether the unit is in blocked state and should not run any operations."""
        return self.unit_peer_data.get("member-state") == "waiting"

    def is_unit_primary(self) -> bool:
        """Returns whether the unit is the primary."""
        return self._mysql.get_primary_label() == self.unit_label

    def get_unit_hostname(self, unit_name: str | None = None) -> str:
        """Get the hostname of the unit."""
        if unit_name:
            unit = self.model.get_unit(unit_name)
            return self.peers.data[unit]["instance-hostname"].split(":")[0]  # type: ignore
        return self.unit_peer_data["instance-hostname"].split(":")[0]

    @property
    def unit_address(self) -> str:
        """Returns the unit's address."""
        return str(self.model.get_binding(PEER).network.bind_address)

    @property
    def database_address(self) -> str:
        """Database endpoint address."""
        return str(self.model.get_binding(DB_RELATION_NAME).network.bind_address)

    @property
    def replication_offer_address(self) -> str:
        """Async replication offer endpoint address."""
        return str(self.model.get_binding(RELATION_OFFER).network.bind_address)

    @property
    def replication_consumer_address(self) -> str:
        """Async replication consumer endpoint address."""
        return str(self.model.get_binding(RELATION_CONSUMER).network.bind_address)

    @property
    def text_logs(self) -> list:
        """Enabled text logs."""
        # slow logs isn't enabled by default
        text_logs = ["error"]

        if self.config.plugin_audit_enabled:
            text_logs.append("audit")

        return text_logs

    def update_endpoint_addresses(self) -> None:
        """Update ip addresses for relation endpoints on unit peer databag."""
        logger.debug("Updating relation endpoints addresses")

        self.unit_peer_data.update({
            f"{PEER}-address": self.unit_address,
            f"{DB_RELATION_NAME}-address": self.database_address,
            f"{RELATION_OFFER}-address": self.replication_offer_address,
            f"{RELATION_CONSUMER}-address": self.replication_consumer_address,
        })

    def update_endpoint_address(self, relation_name: str) -> None:
        """Update ip address for the provided relation on unit peer databag."""
        logger.debug(f"Updating {relation_name} endpoint address")

        relation_binding = self.model.get_binding(relation_name)
        if not relation_binding:
            return

        self.unit_peer_data.update({
            f"{relation_name}-address": str(relation_binding.network.bind_address)
        })

    def install_workload(self) -> bool:
        """Exponential backoff retry to install and configure MySQL.

        Returns: True if successful, False otherwise.
        """

        def set_retry_status(_):
            self.set_unit_status(
                MaintenanceStatus("Failed to install and configure MySQL. Retrying...")
            )

        try:
            for attempt in Retrying(
                wait=wait_exponential(multiplier=10),
                stop=stop_after_delay(60 * 5),
                retry=retry_if_exception_type(snap.SnapError),
                after=set_retry_status,
            ):
                with attempt:
                    MySQL.install_and_configure_mysql_dependencies()
        except (RetryError, MySQLInstallError):
            return False
        return True

    def workload_initialise(self) -> None:
        """Workload initialisation commands.

        Create users and configuration to setup instance as an Group Replication node.
        Raised errors must be treated on handlers.
        """
        self._mysql.write_mysqld_config()
        self.log_rotation_setup.setup()

        if self._mysql.is_data_dir_initialised():
            logger.info("Data directory is already initialised, skipping configuration")
            self._mysql.start_mysqld()
            if not self.unit_initialized() and self.unit.is_leader():
                # when unit is new and has data, it means the app is scaling out
                # from zero units
                logger.info("Scaling out from zero units")
                # create the cluster due it being dissolved on scale-down
                self.create_cluster()
                self._on_update_status(None)
            return

        # ensure hostname can be resolved
        self.hostname_observer.update_etc_hosts(None)

        logger.info("Initializing MySQL data directory")
        self._mysql.initialise_mysqld()

        logger.info("Set operator user and restart mysqld")
        self._mysql.set_operator_user_and_start_mysqld()

        logger.info("Configuring initialized mysqld")
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

        current_mysqld_pid = self._mysql.get_pid_of_port_3306()
        self._mysql.configure_instance()

        for attempt in Retrying(wait=wait_fixed(30), stop=stop_after_attempt(20), reraise=True):
            with attempt:
                new_mysqld_pid = self._mysql.get_pid_of_port_3306()
                if not new_mysqld_pid:
                    raise MySQLDNotRestartedError("mysqld process not yet up after restart")

                if current_mysqld_pid == new_mysqld_pid:
                    raise MySQLDNotRestartedError("mysqld not yet shutdown")

        self._mysql.wait_until_mysql_connection()
        self.unit_peer_data["instance-hostname"] = f"{instance_hostname()}:3306"

        if not self.unit.is_leader():
            # Wait to be joined and set flags
            self.set_unit_status(WaitingStatus("Waiting to join the cluster"))
            self.unit_peer_data["member-role"] = InstanceRole.SECONDARY.value
            self.unit_peer_data["member-state"] = "waiting"
            return

        self._create_cluster()

    def get_unit_address(self, unit: Unit, relation_name: str) -> str:
        """Get the IP address of a specific unit."""
        if not self.peers:
            return ""

        try:
            return str(self.peers.data[unit].get(f"{relation_name}-address", ""))
        except KeyError:
            return ""

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

    def update_endpoints(self) -> None:
        """Update endpoints for the cluster."""
        self.database_relation._update_endpoints_all_relations(None)

    def _can_start(self, event: StartEvent) -> bool:
        """Check if the unit can start.

        Args:
            event: StartEvent
        """
        # Safeguard unit starting before leader unit sets peer data
        if not self._is_peer_data_set:
            logger.debug("Peer data not yet set. Deferring")
            event.defer()
            return False

        # Safeguard against starting while refreshing
        if self._refresh is None:
            logger.warning("Refresh could be in progress")
        if self._refresh and self._refresh.in_progress:
            logger.debug("Refresh in progress")
            event.defer()
            return False

        # Safeguard against error on install hook
        if self._has_blocked_status:
            return False

        # Safeguard against storage not attached
        # https://github.com/juju/juju/issues/21135
        if not is_volume_mounted():
            logger.error("Data directory not attached.")
            raise StorageUnavailableError

        if not self._mysql.read_file_content(MYSQLD_CUSTOM_CONFIG_FILE):
            # empty config mean start never ran, skip next checks
            return True

        # Safeguard if receiving on start after unit initialization
        # with retries to allow for mysqld startup
        try:
            for attempt in Retrying(stop=stop_after_attempt(6), wait=wait_fixed(5)):
                with attempt:
                    if self.unit_initialized(raise_exceptions=True):
                        logger.debug(
                            "Delegate status update for start handler on initialized unit."
                        )
                        self._on_update_status(None)
                        return False
        except RetryError:
            event.defer()
            return False

        return True

    def _create_cluster(self) -> None:
        """Creates the InnoDB cluster and sets up the ports."""
        try:
            # Create the cluster and cluster set from the leader unit
            logger.info(f"Creating cluster {self.app_peer_data['cluster-name']}")
            self.create_cluster()
            self.unit.set_ports(3306, 33060)
            self.set_unit_status(self.build_unit_workload_status())
        except (
            MySQLCreateClusterError,
            MySQLCreateClusterSetError,
            MySQLInitializeJujuOperationsTableError,
        ) as e:
            logger.exception("Failed to create cluster")
            raise e

    def _is_unit_waiting_to_join_cluster(self) -> bool:
        """Return if the unit is waiting to join the cluster."""
        # alternatively, we could check if the instance is configured
        # and have an empty performance_schema.replication_group_members table
        return (
            self.unit_peer_data.get("member-state") == "waiting"
            and self.unit_configured
            and not self.unit_initialized()
            and self.cluster_initialized
        )

    def _get_primary_from_online_peer(self) -> str | None:
        """Get the primary address from an online peer."""
        for unit in self.peers.units:
            if self.peers.data[unit].get("member-state") == InstanceState.ONLINE:
                try:
                    return self._mysql.get_cluster_primary_address(
                        from_instance=self.get_unit_address(unit, PEER)
                    )
                except MySQLGetClusterPrimaryAddressError:
                    # try next unit
                    continue

    def join_unit_to_cluster(self) -> None:
        """Join the unit to the cluster.

        Try to join the unit from the primary unit.
        """
        instance_label = self.unit_label
        instance_address = self.unit_address

        if not self._mysql.is_instance_in_cluster(instance_label):
            # Add new instance to the cluster
            try:
                cluster_primary = self._get_primary_from_online_peer()
                if not cluster_primary:
                    self.set_unit_status(WaitingStatus("waiting to get cluster primary from peer"))
                    logger.info("waiting: unable to retrieve the cluster primary from online peer")
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
                    self.set_unit_status(WaitingStatus("waiting to join the cluster."))
                    logger.info("waiting: cluster lock is held")
                    return

                self.set_unit_status(MaintenanceStatus("joining the cluster"))

                # Stop GR for cases where the instance was previously part of the cluster
                # harmless otherwise
                self._mysql.stop_group_replication()
                # Add the instance to the cluster. This operation uses locks to ensure that
                # only one instance is added to the cluster at a time
                # (so only one instance is involved in a state transfer at a time)
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
                logger.info("Waiting to join the cluster, failed to acquire lock.")
                return

        self.unit_peer_data["member-state"] = InstanceState.ONLINE.value
        self.set_unit_status(self.build_unit_workload_status())
        logger.info(f"Instance {instance_label} added to cluster")

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

        if self.is_unit_primary() and any(ongoing_ops):
            logger.info("Skipping group replication restart")
            return OperationResult.RETRY_RELEASE

        if self.is_unit_primary() and self.app.planned_units() > 1:
            try:
                new_primary = self.get_unit_address(self.peers.units.pop(), PEER)
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
        if not self.unit_initialized():
            logger.debug("Restarting standalone mysqld")
            self._mysql.restart_mysqld()
            return OperationResult.RELEASE

        if self.app.planned_units() > 1 and self.is_unit_primary():
            try:
                new_primary = self.get_unit_address(self.peers.units.pop(), PEER)
                logger.debug(f"Switching primary to {new_primary}")
                self._mysql.set_cluster_primary(new_primary)
            except MySQLSetClusterPrimaryError:
                logger.warning("Changing primary failed")

        logger.debug("Restarting mysqld")
        self.set_unit_status(MaintenanceStatus("restarting MySQL"))
        self._mysql.restart_mysqld()
        self.set_unit_status(MaintenanceStatus("recovering unit after restart"))
        sleep(10)
        self.recover_unit_after_restart()

        self._on_update_status(None)
        return OperationResult.RELEASE

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


if __name__ == "__main__":
    main(MySQLOperatorCharm)
