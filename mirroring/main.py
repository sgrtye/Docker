import json
import os
import subprocess
from dataclasses import dataclass
from enum import Enum, auto

event_name: str | None = os.getenv("GITHUB_EVENT_NAME")
github_step_summary: str | None = os.getenv("GITHUB_STEP_SUMMARY")

if event_name is None or github_step_summary is None:
    print("Error: Missing one or more required secrets. Exiting.")
    raise SystemExit(1)
else:
    SCHEDULED: bool = event_name == "schedule"
    GITHUB_STEP_SUMMARY: str = github_step_summary
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
    images: list[Image] = []

    with open("mirroring/images.txt", "r") as file:
        for i, line in enumerate(file):
            if line:
                parts: list[str] = line.split()
                assert len(parts) == 5

                images.append(
                    Image(
                        name=parts[0],
                        original_identifier=parts[1],
                        original_tag=parts[2],
                        target_identifier=parts[3],
                        target_tag=parts[4],
                    )
                )

    print(f"images: {[image.name for image in images]} to be processed")
    return images


def get_image_digest(manifests: list[dict] | dict, platform: str) -> str | None:
    if not manifests:
        return None

    if isinstance(manifests, dict):
        manifests = [manifests]

    for manifest in manifests:
        info: dict[str, str] = manifest.get("Descriptor", {}).get("platform", {})
        if not f"{info.get('os', '')}/{info.get('architecture', '')}" == platform:
            continue

        match manifest["Descriptor"]["mediaType"]:
            case "application/vnd.docker.distribution.manifest.v1+json":
                return manifest["SchemaV1Manifest"]["config"]["digest"]
            case "application/vnd.docker.distribution.manifest.v2+json":
                return manifest["SchemaV2Manifest"]["config"]["digest"]
            case "application/vnd.docker.distribution.manifest.list.v2+json":
                return manifest["ManifestList"]["config"]["digest"]
            case "application/vnd.oci.image.manifest.v1+json":
                return manifest["OCIManifest"]["config"]["digest"]
            case "application/vnd.oci.image.index.v1+json":
                return manifest["OCIIndex"]["config"]["digest"]

    return None


def check_image_status(image: Image) -> dict[str, Status]:
    original_manifest = subprocess.run(
        [
            "docker",
            "manifest",
            "inspect",
            f"{image.original_identifier}:{image.original_tag}",
            "--verbose",
        ],
        capture_output=True,
        text=True,
    )

    if original_manifest.returncode != 0:
        return dict.fromkeys(PLATFORMS.keys(), Status.NOT_SUPPORTED)

    original_manifest_parsed = json.loads(original_manifest.stdout)

    target_manifest = subprocess.run(
        [
            "docker",
            "manifest",
            "inspect",
            f"{image.target_identifier}:{image.target_tag}",
            "--verbose",
        ],
        capture_output=True,
        text=True,
    )

    if target_manifest.returncode != 0 or not SCHEDULED:
        target_manifest_parsed = []
    else:
        target_manifest_parsed = json.loads(target_manifest.stdout)

    status: dict[str, Status] = dict()
    for platform in PLATFORMS.keys():
        original_platform = get_image_digest(original_manifest_parsed, platform)
        target_platform = get_image_digest(target_manifest_parsed, platform)

        if original_platform is None:
            status[platform] = Status.NOT_SUPPORTED
        elif target_platform is None:
            status[platform] = Status.NEW
        elif original_platform != target_platform:
            status[platform] = Status.OUTDATED
        else:
            status[platform] = Status.UP_TO_DATE

    return status


def download_and_push_image(image: Image, platform: str) -> None:
    print(
        f"Mirroring {image.name}:{image.original_tag} to {image.target_identifier}:{image.target_tag} for {platform}"
    )

    subprocess.run(
        [
            "docker",
            "pull",
            f"{image.original_identifier}:{image.original_tag}",
            "--platform",
            platform,
        ],
        capture_output=True,
        text=True,
    )

    print("Image pulled successfully")

    subprocess.run(
        [
            "docker",
            "tag",
            f"{image.original_identifier}:{image.original_tag}",
            f"{image.target_identifier}:{PLATFORMS[platform]}",
        ],
        capture_output=True,
        text=True,
    )

    subprocess.run(
        [
            "docker",
            "push",
            f"{image.target_identifier}:{PLATFORMS[platform]}",
        ],
        capture_output=True,
        text=True,
    )

    print("Image pushed successfully")

    subprocess.run(
        [
            "docker",
            "image",
            "prune",
            "-af",
        ],
        capture_output=True,
        text=True,
    )


def create_manifest(image: Image, supported_platforms: list[str]) -> bool:
    print(f"Creating multi-platform manifest for {image.name}")

    manifest_name: str = f"{image.target_identifier}:{image.target_tag}"
    platform_images: list[str] = [
        f"{image.target_identifier}:{PLATFORMS[platform]}"
        for platform in supported_platforms
    ]

    subprocess.run(
        ["docker", "manifest", "rm", manifest_name], capture_output=True, text=True
    )

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


def image_mirror(image: Image, status: dict[str, Status]) -> bool:
    try:
        for platform, platform_status in status.items():
            match platform_status:
                case Status.NEW | Status.OUTDATED:
                    download_and_push_image(image, platform)

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

        image_width: int = max(15, max(len(image.name) for image in result.keys()) + 2)
        platform_width: int = 15

        header: str = f"|{'Image':^{image_width}}"
        separator: str = f"|{'-' * image_width}"

        for platform_name in PLATFORMS.values():
            header += f"|{platform_name:^{platform_width}}"
            separator += f"|{'-' * platform_width}"

        header += "|\n"
        separator += "|\n"

        summary_file.write(separator)
        summary_file.write(header)
        summary_file.write(separator)

        for image, status in result.items():
            row: str = f"|{image.name:^{image_width}}"

            for platform_key in PLATFORMS.keys():
                platform_status: Status = status.get(platform_key, Status.ERROR)
                row += f"|{platform_status.name:^{platform_width}}"

            row += "|\n"
            summary_file.write(row)
            summary_file.write(separator)

        summary_file.write(separator)

        summary_file.write("```\n")


def main() -> None:
    images: list[Image] = load_images_from_file()
    result: dict[Image, dict[str, Status]] = dict()

    for image in images:
        status = check_image_status(image)
        print(f"Status for {image.name}: {status}")

        pushed_successfully = image_mirror(image, status)

        if pushed_successfully:
            result[image] = status
        else:
            result[image] = dict.fromkeys(status.keys(), Status.ERROR)

    create_step_summary(result)


if __name__ == "__main__":
    main()
