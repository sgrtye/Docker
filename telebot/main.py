import os
import re
import json
import asyncio
from datetime import datetime

import docker
from docker.models.containers import Container

import httpx
from telegram import Update, BotCommand
from telegram.ext import Application, ContextTypes, CommandHandler

import logging

logger = logging.getLogger("my_app")
logger.setLevel(logging.INFO)
console_handler = logging.StreamHandler()
formatter = logging.Formatter(
    fmt="%(asctime)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
)
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)
logger.propagate = False

NOVEL_URL: str | None = os.getenv("NOVEL_URL")
GLANCES_URL: str | None = os.getenv("GLANCES_URL")
TELEBOT_TOKEN: str | None = os.getenv("TELEBOT_TOKEN")
TELEBOT_USER_ID: str | None = os.getenv("TELEBOT_USER_ID")

if (
    NOVEL_URL is None
    or GLANCES_URL is None
    or TELEBOT_TOKEN is None
    or TELEBOT_USER_ID is None
):
    logger.critical("Environment variables not fulfilled")
    raise SystemExit(0)


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
    containers: list[dict] = response.json()

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

    reply.append("")
    reply.append(f"Docker CPU Usage: {total_cpu_usage:.2f} %")
    reply.append(f"Docker Memory Usage: {total_memory_usage_mb:.2f} MB")

    return reply


async def novel_update() -> list[str]:
    async with httpx.AsyncClient() as client:
        response = await client.get(NOVEL_URL)

    if response.status_code != 200:
        return ["Novel update is not currently available"]

    reply: list[str] = []

    content: str = response.content.decode("utf-8")
    data_dict: dict[str, list[str]] = json.loads(content)

    for name, (title, time, link) in data_dict.items():
        title_match = re.search(r'[^\-－—–,:()\[\]，：（）【】]+', name)
        name = title_match.group(0) if title_match else name
        time = datetime.fromisoformat(time)
        time = time.strftime("%b") + f"-{time.day}"
        reply.append(f"{name} ({time}):\n{title[:15]}\n{link}")

    return reply


def restore() -> list[str]:
    client = docker.DockerClient("unix:///var/run/docker.sock")
    exited_containers: list[Container] = client.containers.list(
        all=True, filters={"status": "exited"}
    )
    exited_containers: list[Container] = [
        container
        for container in exited_containers
        if container.attrs["HostConfig"]["RestartPolicy"]["Name"] != "unless-stopped"
    ]

    reply: list[str] = []

    for container in exited_containers:
        container.start()
        reply.append(f"Restarting container: {container.name}")

    if not reply:
        reply.append("No exited containers to restart")

    return reply


def is_authorized(update: Update) -> bool:
    return str(update.effective_user.id) == TELEBOT_USER_ID


async def unauthorized_response(update: Update) -> None:
    await update.message.reply_text(
        "?????????????????????????",
        reply_to_message_id=update.message.message_id,
    )


async def handle_info_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    if not is_authorized(update):
        await unauthorized_response(update)
        return

    await update.message.reply_text(
        markdown_v2_encode(await container_usage()),
        parse_mode="MarkdownV2",
        reply_to_message_id=update.message.message_id,
    )


async def handle_novel_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    if not is_authorized(update):
        await unauthorized_response(update)
        return

    await update.message.reply_text(
        default_encode(await novel_update()),
        reply_to_message_id=update.message.message_id,
    )


async def handle_restore_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    if not is_authorized(update):
        await unauthorized_response(update)
        return

    await update.message.reply_text(
        default_encode(restore()),
        reply_to_message_id=update.message.message_id,
    )


def set_commands(app: Application) -> None:
    commands: list[BotCommand] = [
        BotCommand("info", "Get server usage status"),
        BotCommand("novel", "Get novel latest chapters"),
        BotCommand("restore", "Restart all exited containers"),
    ]

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(app.bot.set_my_commands(commands))


def main() -> None:
    # Booting up all containers that were not turned off manually
    restore()

    app = Application.builder().token(TELEBOT_TOKEN).build()
    app.add_handler(CommandHandler("info", handle_info_command))
    app.add_handler(CommandHandler("novel", handle_novel_command))
    app.add_handler(CommandHandler("restore", handle_restore_command))

    set_commands(app)

    logger.info("Telegram bot started")
    app.run_polling()


if __name__ == "__main__":
    main()
