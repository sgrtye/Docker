import ast
import json
import asyncio
import datetime
import requests
import websockets


response = requests.get(
    "https://gamma-api.polymarket.com/events?limit=100&closed=false"
).json()
tokens_pair = dict()

for event in response:
    if event["volume"] > 10_000_000 and event["volume24hr"] > 1_000_000:

        for market in event["markets"]:
            if market["volumeNum"] < 1_000_000:
                continue

            if "outcomePrices" in market and "clobTokenIds" in market:
                token1, token2 = ast.literal_eval(market["clobTokenIds"])
                tokens_pair[token1] = token2
                tokens_pair[token2] = token1


url = "wss://ws-subscriptions-clob.polymarket.com/ws/market"
last_pong = datetime.datetime.now()


async def main():
    async with websockets.connect(url) as websocket:
        await websocket.send(
            json.dumps(
                {
                    "assets_ids": list(tokens_pair.values()),
                    "type": "market",
                }
            )
        )

        print(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "Monitor started")

        while True:
            message = await websocket.recv()

            if message != "PONG":
                last_pong = datetime.datetime.now()

            info = json.loads(message)

            info = {
                event["asset_id"]: event
                for event in info
                if event["event_type"] == "book"
            }
            checked = []

            for asset_id in info.keys():
                if asset_id in checked:
                    continue

                pair_id = tokens_pair[asset_id]

                if pair_id not in info.keys():
                    # print("Matching bet not found in the same epoch")
                    continue

                event1 = info[asset_id]
                event2 = info[pair_id]

                # if (
                #     event1["asks"]
                #     and event2["bids"]
                #     and event1["asks"][-1]["size"] != event2["bids"][-1]["size"]
                # ):
                #     print("Bets mismatch")
                #     print(event1["asks"][-1])
                #     print(event2["bids"][-1])

                # if (
                #     event1["bids"]
                #     and event2["asks"]
                #     and event1["bids"][-1]["size"] != event2["asks"][-1]["size"]
                # ):
                #     print("Bets mismatch")
                #     print(event1["bids"][-1])
                #     print(event2["asks"][-1])

                if (
                    event1["asks"]
                    and event2["asks"]
                    and float(event1["asks"][-1]["price"])
                    + float(event2["asks"][-1]["price"])
                    < 1
                ):
                    print(
                        datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "Arbitrage opportunities found",
                    )
                    print(event1["asks"][-1])
                    print(event2["asks"][-1])

                checked.append(asset_id)
                checked.append(pair_id)

            if last_pong + datetime.timedelta(seconds=10) < datetime.datetime.now():
                await websocket.send("PING")


if __name__ == "__main__":
    asyncio.run(main())
