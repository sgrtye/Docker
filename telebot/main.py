import os
import json
import docker
import asyncio

import httpx
from telebot.types import Message, BotCommand
from telebot.async_telebot import AsyncTeleBot

import logging

logger = logging.getLogger("my_app")
logger.setLevel(logging.INFO)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
formatter = logging.Formatter(
    fmt="%(asctime)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
)
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)
logger.propagate = False

NOVEL_URL: str | None = os.environ.get("NOVEL_URL")
GLANCES_URL: str | None = os.environ.get("GLANCES_URL")
TELEBOT_TOKEN: str | None = os.environ.get("TELEBOT_TOKEN")
TELEBOT_USER_ID: str | None = os.environ.get("TELEBOT_USER_ID")

if (
    NOVEL_URL is None
    or GLANCES_URL is None
    or TELEBOT_TOKEN is None
    or TELEBOT_USER_ID is None
):
    logger.critical("Environment variables not fulfilled")
    raise SystemExit(0)

bot = AsyncTeleBot(TELEBOT_TOKEN)


def markdown_v2_encode(reply) -> str:
    text = "\n".join(reply)
    return f"```\n{text}```"


def default_encode(reply) -> str:
    text = "\n".join(reply)
    return text


async def container_usage() -> list[str]:
    async with httpx.AsyncClient() as client:
        response = await client.get(GLANCES_URL)

    if response.status_code != 200:
        return ["Container usage is not currently available"]

    total_cpu_usage: float = 0
    total_memory_usage: int = 0
    containers: list[dict] = json.loads(response.content)

    reply: list[str] = []
    reply.append(f"{'Name':<12} {'CPU':<5}  {'Memory':<5}")

    for container in containers:
        if container["status"] != "running":
            continue

        container_name: str = container["name"]

        cpu_percentage: float = container["cpu"]["total"]

        memory_usage: int = container["memory"]["usage"]
        memory_usage_mb: float = memory_usage / (1024 * 1024)

        total_cpu_usage += cpu_percentage
        total_memory_usage += memory_usage

        reply.append(
            f"{container_name:<12} {cpu_percentage:<5.2f}% {memory_usage_mb:<5.1f} MB"
        )

    total_memory_usage_mb: float = total_memory_usage / (1024 * 1024)

    reply.append(f"\nDocker CPU Usage: {total_cpu_usage:.2f} %")
    reply.append(f"Docker Memory Usage: {total_memory_usage_mb:.2f} MB")

    return reply


async def novel_update() -> list[str]:
    async with httpx.AsyncClient() as client:
        response = await client.get(NOVEL_URL)

    if response.status_code != 200:
        return ["Novel update is not currently available"]

    reply: list[str] = []

    content: str = response.content.decode("utf-8")
    data_dict: dict[str, list[str, str]] = json.loads(content)

    for novel, (title, url) in data_dict.items():
        reply.append(f"{novel}: \n{title}\n{url}")

    return reply


def restore() -> list[str]:
    client = docker.DockerClient("unix:///var/run/docker.sock")
    containers: list[docker.models.containers.Container] = client.containers.list(
        all=True, filters={"status": "exited"}
    )
    exited_containers: list = [
        container
        for container in containers
        if container.attrs["HostConfig"]["RestartPolicy"]["Name"] != "unless-stopped"
    ]

    reply: list[str] = []

    for container in exited_containers:
        container.start()
        reply.append(f"Restarting container: {container.name}")

    if not reply:
        reply.append("All containers are running")

    return reply


def is_authorized(message: Message) -> bool:
    return message.from_user.id == TELEBOT_USER_ID


@bot.message_handler(commands=["info"])
async def handle_info_command(message: Message) -> None:
    if not is_authorized(message):
        await bot.reply_to(message, "?????????????????????????")
        return

    await bot.reply_to(
        message, markdown_v2_encode(await container_usage()), parse_mode="MarkdownV2"
    )


@bot.message_handler(commands=["novel"])
async def handle_novel_update_command(message: Message) -> None:
    if not is_authorized(message):
        await bot.reply_to(message, "?????????????????????????")
        return

    await bot.reply_to(message, default_encode(await novel_update()), parse_mode=None)


@bot.message_handler(commands=["restore"])
async def handle_container_restore_command(message: Message) -> None:
    if not is_authorized(message):
        await bot.reply_to(message, "?????????????????????????")
        return

    await bot.reply_to(message, markdown_v2_encode(restore()), parse_mode="MarkdownV2")


async def main() -> None:
    # Booting up all containers that were not turned off manually
    restore()

    commands: list[BotCommand] = [
        BotCommand("info", "Get server usage status"),
        BotCommand("novel", "Get novel latest chapters"),
        BotCommand("restore", "Restart all exited containers"),
    ]

    logger.info("Telegram bot started")
    await bot.set_my_commands(commands)
    await bot.infinity_polling()


if __name__ == "__main__":
    asyncio.run(main())
