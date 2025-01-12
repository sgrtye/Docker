import signal
import asyncio
import platform


def handle_termination_signal(signum, frame) -> None:
    print("Exiting")
    raise SystemExit(0)


def handle_termination_signal_async() -> None:
    print("Exiting")
    raise SystemExit(0)


async def main() -> None:
    match platform.system():
        case "Linux":
            signal.signal(signal.SIGTERM, handle_termination_signal)

            asyncio.get_running_loop().add_signal_handler(
                signal.SIGTERM, handle_termination_signal_async
            )
        case _:
            pass

    await asyncio.sleep(60)


if __name__ == "__main__":
    asyncio.run(main())
