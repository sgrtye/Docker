import time
import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler


def synchronized_task(arg1: int, arg2: str) -> None:
    time.sleep(10)


async def async_task(arg1: int, arg2: str) -> None:
    await asyncio.sleep(10)


def schedule_tasks() -> None:
    scheduler = AsyncIOScheduler()

    scheduler.add_job(
        synchronized_task,
        "interval",
        hours=8,
        args=(1, "1"),
    )

    scheduler.add_job(
        async_task,
        "cron",
        hour="5,10",
        minute="24",
        kwargs={"arg1": 1, "arg2": "1"},
    )

    scheduler.start()


async def main() -> None:
    schedule_tasks()

    # await some_other_async_function()


if __name__ == "__main__":
    # asyncio.get_event_loop().run_forever()

    asyncio.run(main())
