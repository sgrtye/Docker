import os
import time
import json
import docker
import telebot
import requests
import datetime

TELEBOT_TOKEN = os.environ.get("TELEBOT_TOKEN")
NOVEL_URL = os.environ.get("NOVEL_URL")
GLANCES_URL = os.environ.get("GLANCES_URL")

if TELEBOT_TOKEN is None or NOVEL_URL is None or GLANCES_URL is None:
    print("Environment variables not fulfilled")
    raise SystemExit

bot = telebot.TeleBot(TELEBOT_TOKEN)

commands = [
    telebot.types.BotCommand("info", "Get server usage status"),
    telebot.types.BotCommand("novel", "Get novel latest chapters"),
    telebot.types.BotCommand("restore", "Restart all exited containers"),
]

bot.set_my_commands(commands)


def MarkdownV2Encode(reply):
    text = "\n".join(reply)
    return f"```\n{text}```"


def DefaultEncode(reply):
    text = "\n".join(reply)
    return text


def containerUsage():
    response = requests.get(GLANCES_URL)

    if response.status_code != 200:
        return ["Container usage is not currently available"]

    total_cpu_usage = 0
    total_memory_usage = 0
    containers = json.loads(response.content)

    reply = []
    reply.append(f"{'Name':<12} {'CPU':<5}  {'Memory':<5}")

    for container in containers:
        container_name = container["name"]

        cpu_percentage = container["cpu"]["total"]

        memory_usage = container["memory"]["usage"]
        memory_usage_mb = memory_usage / (1024 * 1024)

        total_cpu_usage += cpu_percentage
        total_memory_usage += memory_usage

        reply.append(
            f"{container_name:<12} {cpu_percentage:<5.2f}% {memory_usage_mb:<5.1f} MB"
        )

    total_memory_usage_mb = total_memory_usage / (1024 * 1024)

    reply.append(f"\nDocker CPU Usage: {total_cpu_usage:.2f} %")
    reply.append(f"Docker Memory Usage: {total_memory_usage_mb:.2f} MB")

    return reply


def novelUpdate():
    response = requests.get(NOVEL_URL)

    if response.status_code != 200:
        return ["Novel update is not currently available"]

    reply = []

    content = response.content.decode("utf-8")
    data_dict = json.loads(content)

    for novel, (title, url) in data_dict.items():
        reply.append(f"{novel}: \n{title}\n{url}")

    return reply


def restore():
    client = docker.DockerClient("unix:///var/run/docker.sock")
    containers = client.containers.list(all=True, filters={"status": "exited"})
    exited_containers = [
        container
        for container in containers
        if container.attrs["HostConfig"]["RestartPolicy"]["Name"] != "unless-stopped"
    ]
    reply = []

    for container in exited_containers:
        container.start()
        reply.append(f"Restarting container: {container.name}")

    if not reply:
        reply.append("All containers are running")

    return reply


# Booting up all containers that were not turned off manually
restore()


@bot.message_handler(commands=["info"])
def handle_info_command(message):
    bot.reply_to(message, MarkdownV2Encode(containerUsage()), parse_mode="MarkdownV2")


@bot.message_handler(commands=["novel"])
def handle_novel_update_command(message):
    bot.reply_to(message, DefaultEncode(novelUpdate()), parse_mode=None)


@bot.message_handler(commands=["restore"])
def handle_container_restore_command(message):
    bot.reply_to(message, MarkdownV2Encode(restore()), parse_mode="MarkdownV2")


if __name__ == "__main__":
    print(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "Telegram bot started")
    bot.infinity_polling(logger_level=None)
