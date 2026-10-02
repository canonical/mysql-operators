# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

from functools import cached_property

from boto3.session import Session
from botocore.client import BaseClient
from botocore.loaders import Loader
from botocore.regions import EndpointResolver
from charmlibs.pathops import PathProtocol

from .base import BaseBackupStorage


class S3BackupStorage(BaseBackupStorage):
    """Class to deal with the S3 backup storage."""

    name = "s3"
    certs_dir_name = "s3_ca"
    certs_file_name = "s3-ca.pem"

    def __init__(self, config: dict[str, str]):
        """Initialize the class attributes."""
        self._config = self._build_config(config)
        self._endpoint = self._build_endpoint()
        self._session = Session(
            aws_access_key_id=self._config["access-key"],
            aws_secret_access_key=self._config["secret-key"],
            region_name=self._config["region"],
        )

    @cached_property
    def bucket_name(self) -> str:
        """Return the bucket name."""
        return self._config["bucket"]

    @cached_property
    def bucket_path(self) -> str:
        """Return the bucket path."""
        return self._config["path"]

    @cached_property
    def ca_chain(self) -> str | None:
        """Return the CA chain."""
        chain = self._config.get("tls-ca-chain")
        if isinstance(chain, list):
            chain = "\n".join(chain)

        return chain

    @cached_property
    def _required_params(self) -> set[str]:
        """Return the required params."""
        return {"bucket", "access-key", "secret-key"}

    def _build_endpoint(self) -> str:
        """Build the S3 storage endpoint, considering the region."""
        endpoint = self._config["endpoint"]
        region = self._config["region"]

        # Construct the endpoint using the region
        endpoints = Loader().load_data("endpoints")
        resolver = EndpointResolver(endpoints)
        endpoint_data = resolver.construct_endpoint("s3", region)

        if not endpoint_data:
            return endpoint

        endpoint_suffix = endpoint_data["dnsSuffix"]
        endpoint_hostname = endpoint_data["hostname"]

        # Use the built endpoint if it is an AWS endpoint
        if endpoint.endswith(endpoint_suffix):
            protocol = endpoint.split("://")[0]
            endpoint = f"{protocol}://{endpoint_hostname}"

        return endpoint

    def _build_config(self, config: dict[str, str]) -> dict:
        """Build the S3 storage configuration."""
        if not self._required_params <= config.keys():
            raise ValueError("Invalid storage configuration. Required keys missing")

        # Add some sensible defaults for missing optional parameters
        config.setdefault("endpoint", "https://s3.amazonaws.com")
        config.setdefault("path", "/")
        config.setdefault("region", None)
        config.setdefault("s3-uri-style", "auto")
        config.setdefault("s3-api-version", "auto")

        # Strip whitespaces from all parameters
        for key, value in config.items():
            if isinstance(value, str):
                config[key] = value.strip()

        # Clean up extra slash symbols to avoid issues on third-party storages
        config["bucket"] = config["bucket"].strip("/")
        config["endpoint"] = config["endpoint"].strip("/")

        return config

    def build_backup_args(self, ca_chain_path: str | PathProtocol | None) -> list[str]:
        """Build the backup args for upload / download."""
        optional_args = []
        required_args = [
            f"--s3-region={self._config['region']}",
            f"--s3-bucket={self._config['bucket']}",
            f"--s3-endpoint={self._config['endpoint']}",
            f"--s3-api-version={self._config['s3-api-version']}",
            f"--s3-bucket-lookup={self._config['s3-uri-style']}",
        ]

        if ca_chain_path:
            optional_args = [f"--cacert={ca_chain_path}"]

        return [*required_args, *optional_args]

    def build_backup_env(self) -> dict[str, str]:
        """Build the backup env for upload / download."""
        return {
            "ACCESS_KEY_ID": self._config["access-key"],
            "SECRET_ACCESS_KEY": self._config["secret-key"],
        }

    def build_backup_client(self, ca_chain_path: str | PathProtocol | None) -> BaseClient:
        """Build the backup client for upload / download."""
        return self._session.client(
            service_name=self.name,
            endpoint_url=self._endpoint,
            region_name=self._config["region"],
            verify=ca_chain_path,
        )
