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

    def __init__(self, params: dict):
        """Initialize the class attributes."""
        self._params = self._build_params(params)
        self._endpoint = self._build_endpoint()

        self._session = Session(
            aws_access_key_id=self._params["access-key"],
            aws_secret_access_key=self._params["secret-key"],
            region_name=self._params["region"],
        )

    @cached_property
    def bucket_name(self) -> str:
        """Return the bucket name."""
        return self._params["bucket"]

    @cached_property
    def bucket_path(self) -> str:
        """Return the bucket path."""
        return self._params["path"]

    @cached_property
    def ca_chain(self) -> str | None:
        """Return the CA chain."""
        chain = self._params.get("tls-ca-chain")
        if isinstance(chain, list):
            chain = "\n".join(chain)

        return chain

    @cached_property
    def _required_params(self) -> set[str]:
        """Return the required params."""
        return {"bucket", "access-key", "secret-key"}

    def _build_endpoint(self) -> str:
        """Build the S3 storage endpoint, considering the region."""
        endpoint = self._params["endpoint"]
        region = self._params["region"]

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

    def _build_params(self, storage_params: dict) -> dict:
        """Build the S3 storage parameters."""
        if not self._required_params <= storage_params.keys():
            raise ValueError("Invalid storage parameters. Required keys missing")

        # Add some sensible defaults for missing optional parameters
        storage_params.setdefault("endpoint", "https://s3.amazonaws.com")
        storage_params.setdefault("path", "/")
        storage_params.setdefault("region", None)
        storage_params.setdefault("s3-uri-style", "auto")
        storage_params.setdefault("s3-api-version", "auto")

        # Strip whitespaces from all parameters
        for key, value in storage_params.items():
            if isinstance(value, str):
                storage_params[key] = value.strip()

        # Clean up extra slash symbols to avoid issues on third-party storages
        storage_params["bucket"] = storage_params["bucket"].strip("/")
        storage_params["endpoint"] = storage_params["endpoint"].strip("/")

        return storage_params

    def build_backup_args(self, ca_chain_path: str | PathProtocol | None) -> list[str]:
        """Build the backup args for upload / download."""
        optional_args = []
        required_args = [
            f"--s3-region={self._params['region']}",
            f"--s3-bucket={self._params['bucket']}",
            f"--s3-endpoint={self._params['endpoint']}",
            f"--s3-api-version={self._params['s3-api-version']}",
            f"--s3-bucket-lookup={self._params['s3-uri-style']}",
        ]

        if ca_chain_path:
            optional_args = [f"--cacert={ca_chain_path}"]

        return [*required_args, *optional_args]

    def build_backup_env(self) -> dict[str, str]:
        """Build the backup env for upload / download."""
        return {
            "ACCESS_KEY_ID": self._params["access-key"],
            "SECRET_ACCESS_KEY": self._params["secret-key"],
        }

    def build_backup_client(self, ca_chain_path: str | PathProtocol | None) -> BaseClient:
        """Build the backup client for upload / download."""
        return self._session.client(
            service_name=self.name,
            endpoint_url=self._endpoint,
            region_name=self._params["region"],
            verify=ca_chain_path,
        )
