#!/usr/bin/env python3
"""Check raw WebSocket history response structure."""

import asyncio
import json
import os
from datetime import datetime, timedelta
import websockets


async def test_raw_history():
    """See the raw history response."""

    ha_url = os.getenv("HA_URL", "http://192.168.1.128:8123/")
    ha_token = os.getenv("HA_API_KEY")

    ws_url = ha_url.replace("http://", "ws://").replace("https://", "wss://")
    if not ws_url.endswith("/"):
        ws_url += "/"
    ws_url += "api/websocket"

    async with websockets.connect(ws_url) as websocket:
        # Auth
        await websocket.recv()
        await websocket.send(json.dumps({"type": "auth", "access_token": ha_token}))
        await websocket.recv()

        # Query history
        end_time = datetime.now()
        start_time = end_time - timedelta(days=1)

        history_request = {
            "id": 1,
            "type": "history/history_during_period",
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "entity_ids": ["counter.test_counter"],
            "minimal_response": False,
            "no_attributes": False
        }

        await websocket.send(json.dumps(history_request))
        history_response = await websocket.recv()

        print("RAW RESPONSE:")
        print(json.dumps(json.loads(history_response), indent=2)[:3000])


if __name__ == "__main__":
    asyncio.run(test_raw_history())
