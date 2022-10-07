import docker

from nxtools import logging, slugify
from typing import Any
from .config import config


class Services:
    client: docker.DockerClient | None = None
    prefix: str = "io.openpype.service"

    @classmethod
    def connect(cls):
        cls.client = docker.DockerClient(base_url="unix://var/run/docker.sock")

    @classmethod
    def get_running_services(cls) -> list[str]:
        result: list[str] = []
        if cls.client is None:
            cls.connect()
        for container in cls.client.containers.list():
            labels = container.labels
            if service_name := labels.get(f"{cls.prefix}.service_name"):
                result.append(service_name)
        return result

    @classmethod
    def stop_orphans(cls, should_run: list[str]):
        if cls.client is None:
            cls.connect()
        for container in cls.client.containers.list():
            labels = container.labels
            if service_name := labels.get(f"{cls.prefix}.service_name"):
                if service_name in should_run:
                    continue
                logging.warning(f"Stopping service {service_name}")
                container.stop()

    @classmethod
    def ensure_running(
        cls,
        service_name: str,
        addon_name: str,
        addon_version: str,
        service: str,
        image: str,
        environment: dict[str, Any] | None = None,
    ):
        if cls.client is None:
            cls.connect()

        if environment is None:
            environment = {}

        if "ay_api_key" not in environment:
            environment["ay_api_key"] = config.api_key

        environment.update(
            {
                "ay_addon_name": addon_name,
                "ay_addon_version": addon_version,
                "ay_server_url": config.server_url,
            }
        )

        hostname = slugify(
            f"aysvc_{service_name}",
            separator="_",
        )

        #
        # Check whether it is running already
        #

        for container in cls.client.containers.list():
            labels = container.labels

            if labels.get(f"{cls.prefix}.service_name") != service_name:
                continue

            if (
                labels.get(f"{cls.prefix}.service") != service
                or labels.get(f"{cls.prefix}.addon_name") != addon_name
                or labels.get(f"{cls.prefix}.addon_version") != addon_version
            ):
                logging.error("SERVICE MISMATCH. This shouldn't happen. Stopping.")
                container.stop()

            break
        else:

            # And start it, if not
            logging.info(
                f"Starting {service_name} {addon_name}:{addon_version}/{service} (image: {image})"
            )

            cls.client.containers.run(
                image,
                detach=True,
                auto_remove=True,
                environment=environment,
                hostname=hostname,
                name=hostname,
                labels={
                    f"{cls.prefix}.service_name": service_name,
                    f"{cls.prefix}.service": service,
                    f"{cls.prefix}.addon_name": addon_name,
                    f"{cls.prefix}.addon_version": addon_version,
                },
            )
