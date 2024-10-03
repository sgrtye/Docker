import os
import time
import json
import docker
import telebot
import requests
import datetime

TELEBOT_TOKEN = os.environ.get("TELEBOT_TOKEN")
NOVEL_URL = os.environ.get("NOVEL_URL")

if TELEBOT_TOKEN is None or NOVEL_URL is None:
    print("Environment variables not fulfilled")

bot = telebot.TeleBot(TELEBOT_TOKEN, parse_mode="MarkdownV2")

commands = [
    telebot.types.BotCommand("info", "Get server usage status"),
    telebot.types.BotCommand("novel", "Get novel latest chapters"),
    telebot.types.BotCommand("restore", "Restart all exited containers"),
]

bot.set_my_commands(commands)


def MarkdownV2Encode(reply):
    text = "\n".join(reply)
    return f"```\n{text}```"


def dockerUsage():
    # Create a Docker client
    client = docker.DockerClient("unix:///var/run/docker.sock")

    # Get all containers
    containers = client.containers.list()

    total_cpu_usage = 0
    total_memory_usage = 0

    reply = []

    # Iterate over containers and retrieve resource usage
    reply.append(f"{'Name':<12} {'CPU':<5}  {'Memory':<5}")

    stats1 = dict()
    stats2 = dict()

    for container in containers:
        stats1[container.name] = container.stats(stream=False)

    time.sleep(10)

    for container in containers:
        stats2[container.name] = container.stats(stream=False)

    for container in containers:
        # Get container name
        container_name = container.name

        # Get container stats
        stats = stats1[container.name]
        cpu_stats1 = stats["cpu_stats"]
        cpu_usage1 = cpu_stats1["cpu_usage"]["total_usage"]
        cpu_system1 = cpu_stats1["system_cpu_usage"]

        stats = stats2[container.name]
        cpu_stats2 = stats["cpu_stats"]
        cpu_usage2 = cpu_stats2["cpu_usage"]["total_usage"]
        cpu_system2 = cpu_stats2["system_cpu_usage"]

        memory_stats = stats["memory_stats"]

        # CPU usage percentage
        cpu_delta = cpu_usage2 - cpu_usage1
        system_delta = cpu_system2 - cpu_system1
        cpu_percentage = (cpu_delta / system_delta) * 100

        # Memory usage in MB
        memory_usage = memory_stats["usage"]
        memory_usage_mb = memory_usage / (1024 * 1024)

        total_cpu_usage += cpu_percentage
        total_memory_usage += memory_usage

        reply.append(
            f"{container_name:<12} {cpu_percentage:<5.2f}% {memory_usage_mb:<5.1f} MB"
        )

    # Total usage
    total_memory_usage_mb = total_memory_usage / (1024 * 1024)

    reply.append(f"\nDocker CPU Usage: {total_cpu_usage:.2f} %")
    reply.append(f"Docker Memory Usage: {total_memory_usage_mb:.2f} MB")

    return MarkdownV2Encode(reply)


def novelUpdate():
    response = requests.get(NOVEL_URL)
    reply = []

    if response.status_code == 200:
        content = response.content.decode("utf-8")
        data_dict = json.loads(content)

        for novel, (title, url) in data_dict.items():
            reply.append(f"{novel}: \n{title}\n{url}")
    else:
        reply.append(f"Novel update is not currently available")

    print(reply)
    return reply


def restore():
    client = docker.DockerClient("unix:///var/run/docker.sock")
    containers = client.containers.list(all=True, filters={"status": "exited"})
    exited_containers = [
        c
        for c in containers
        if c.attrs["HostConfig"]["RestartPolicy"]["Name"] != "unless-stopped"
    ]
    reply = []

    for container in exited_containers:
        container.start()
        reply.append(f"Restarting container: {container.name}")

    if not reply:
        reply.append("All containers are running")

    return MarkdownV2Encode(reply)


# Booting up all containers that were not turned off manually
restore()


@bot.message_handler(commands=["info"])
def handle_info_command(message):
    bot.reply_to(message, dockerUsage())


@bot.message_handler(commands=["novel"])
def handle_novel_update_command(message):
    bot.reply_to(message, novelUpdate())


@bot.message_handler(commands=["restore"])
def handle_container_restore_command(message):
    bot.reply_to(message, restore())


if __name__ == "__main__":
    print(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "Telegram bot started")
    bot.infinity_polling(logger_level=None)
