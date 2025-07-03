import json
import os
import subprocess
from dataclasses import dataclass
from datetime import datetime
from enum import Enum, auto

import docker

event_name: str | None = os.getenv("GITHUB_EVENT_NAME")
github_step_summary: str | None = os.getenv("GITHUB_STEP_SUMMARY")
tencent_registry_address: str | None = os.getenv("TENCENT_REGISTRY_ADDRESS")
tencent_registry_namespace: str | None = os.getenv("TENCENT_REGISTRY_NAME_SPACE")

if (
    event_name is None
    or github_step_summary is None
    or tencent_registry_address is None
    or tencent_registry_namespace is None
):
    print("Error: Missing one or more required secrets. Exiting.")
    raise SystemExit(1)
else:
    SCHEDULED: bool = event_name == "schedule"
    GITHUB_STEP_SUMMARY: str = github_step_summary
    TENCENT_REGISTRY_ADDRESS: str = tencent_registry_address
    TENCENT_REGISTRY_NAMESPACE: str = tencent_registry_namespace

PLATFORMS: dict[str, str] = {"linux/arm64": "arm64", "linux/amd64": "amd64"}


class Status(Enum):
    NEW = auto()
    OUTDATED = auto()
    UP_TO_DATE = auto()
    NOT_SUPPORTED = auto()
    ERROR = auto()


@dataclass(frozen=True)
class Image:
    name: str
    original_identifier: str
    original_tag: str
    target_identifier: str
    target_tag: str


def load_images_from_file() -> list[Image]:
    today_weekday: int = datetime.now().weekday()

    images: list[Image] = []

    with open("mirroring/images.txt", "r") as file:
        for i, line in enumerate(file):
            if line and (not SCHEDULED or i % 7 == today_weekday):
                parts: list[str] = line.split()
                assert len(parts) == 4

                images.append(
                    Image(
                        name=parts[2],
                        original_identifier=parts[0],
                        original_tag=parts[1],
                        target_identifier=f"{TENCENT_REGISTRY_ADDRESS}/{TENCENT_REGISTRY_NAMESPACE}/{parts[2]}",
                        target_tag=parts[3],
                    )
                )

    return images


def check_image_status(image: Image) -> dict[str, Status]:
    original_manifest = subprocess.run(
        [
            "docker",
            "manifest",
            "inspect",
            f"{image.original_identifier}:{image.original_tag}",
        ],
        capture_output=True,
        text=True,
    )

    if original_manifest.returncode != 0:
        return dict.fromkeys(PLATFORMS.keys(), Status.NOT_SUPPORTED)

    original_manifest_dict = json.loads(original_manifest.stdout)

    target_manifest = subprocess.run(
        [
            "docker",
            "manifest",
            "inspect",
            f"{image.target_identifier}:{image.target_tag}",
        ],
        capture_output=True,
        text=True,
    )

    if target_manifest.returncode != 0:
        return dict.fromkeys(PLATFORMS.keys(), Status.NEW)

    target_manifest_dict = json.loads(target_manifest.stdout)

    status: dict[str, Status] = dict()
    for platform in PLATFORMS.keys():
        original_platform = next(
            (
                p
                for p in original_manifest_dict["manifests"]
                if f"{p['platform']['os']}/{p['platform']['architecture']}" == platform
            ),
            None,
        )
        target_platform = next(
            (
                p
                for p in target_manifest_dict["manifests"]
                if f"{p['platform']['os']}/{p['platform']['architecture']}" == platform
            ),
            None,
        )

        if original_platform is None:
            status[platform] = Status.NOT_SUPPORTED
        elif target_platform is None:
            status[platform] = Status.NEW
        elif original_platform["digest"] != target_platform["digest"]:
            status[platform] = Status.OUTDATED
        else:
            status[platform] = Status.UP_TO_DATE

    return status


def download_and_push_image(
    client: docker.DockerClient, image: Image, platform: str
) -> None:
    print(
        f"Mirroring {image.name}:{image.original_tag} to {image.target_identifier}:{image.target_tag} for {platform}"
    )

    client.images.pull(
        image.original_identifier,
        tag=image.original_tag,
        platform=platform,
    )

    pulled_image = client.images.get(
        f"{image.original_identifier}:{image.original_tag}"
    )
    pulled_image.tag(image.target_identifier, tag=PLATFORMS[platform])

    client.images.push(f"{image.target_identifier}:{PLATFORMS[platform]}")

    client.images.prune()


def create_manifest(image: Image, supported_platforms: list[str]) -> bool:
    print(f"Creating multi-platform manifest for {image.name}")

    manifest_name: str = f"{image.target_identifier}:{image.target_tag}"
    platform_images: list[str] = [
        f"{image.target_identifier}:{PLATFORMS[platform]}"
        for platform in supported_platforms
    ]
    create_cmd: list[str] = [
        "docker",
        "manifest",
        "create",
        manifest_name,
    ] + platform_images

    result = subprocess.run(create_cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"Failed to create manifest for {image.name}: {result.stderr}")
        return False

    push_result = subprocess.run(
        ["docker", "manifest", "push", manifest_name], capture_output=True, text=True
    )

    if push_result.returncode != 0:
        print(f"Failed to push manifest for {image.name}: {push_result.stderr}")
        return False
    else:
        print(
            f"Successfully created and pushed multi-platform manifest for {image.name}"
        )

    return True


def image_mirror(
    client: docker.DockerClient, image: Image, status: dict[str, Status]
) -> bool:
    try:
        for platform, platform_status in status.items():
            match platform_status:
                case Status.NEW | Status.OUTDATED:
                    download_and_push_image(client, image, platform)

        supported_platforms: list[str] = [
            platform
            for platform, platform_status in status.items()
            if platform_status != Status.NOT_SUPPORTED
        ]
        if supported_platforms:
            return create_manifest(image, supported_platforms)
        else:
            print(
                f"No supported platforms for {image.name}, skipping manifest creation"
            )
            return True

    except Exception as e:
        print(f"Error mirroring {image.name}: {e}")
        return False


def create_step_summary(result: dict[Image, dict[str, Status]]) -> None:
    with open(GITHUB_STEP_SUMMARY, "a") as summary_file:
        summary_file.write("### Docker Image Mirroring Results\n\n")
        summary_file.write("```\n")

        summary_file.write(f"{'Image':^15}|{'Platform':^15}|{'Status':^15}\n")
        summary_file.write(f"{'-' * 15}|{'-' * 15}|{'-' * 15}\n")

        for image, status in result.items():
            for platform, platform_status in status.items():
                summary_file.write(
                    f"{image.name:^15}|{PLATFORMS[platform]:^15}|{platform_status.name:^15}\n"
                )

        summary_file.write(f"{'-' * 15}|{'-' * 15}|{'-' * 15}\n")
        summary_file.write("```\n")


def main() -> None:
    client = docker.from_env()

    images: list[Image] = load_images_from_file()
    result: dict[Image, dict[str, Status]] = dict()

    for image in images:
        status = check_image_status(image)
        pushed_successfully = image_mirror(client, image, status)

        if pushed_successfully:
            result[image] = status
        else:
            result[image] = dict.fromkeys(status.keys(), Status.ERROR)

    create_step_summary(result)


if __name__ == "__main__":
    main()
