#!/usr/bin/env python3
"""Test Home Assistant WebSocket API for history queries."""

import asyncio
import json
import os
from datetime import datetime, timedelta
import websockets


async def test_history_websocket():
    """Query history via WebSocket API."""

    ha_url = os.getenv("HA_URL", "http://192.168.1.128:8123/")
    ha_token = os.getenv("HA_API_KEY")

    ws_url = ha_url.replace("http://", "ws://").replace("https://", "wss://")
    if not ws_url.endswith("/"):
        ws_url += "/"
    ws_url += "api/websocket"

    print(f"Connecting to: {ws_url}\n")

    async with websockets.connect(ws_url) as websocket:
        # Auth
        await websocket.recv()
        await websocket.send(json.dumps({"type": "auth", "access_token": ha_token}))
        auth_result = json.loads(await websocket.recv())

        if auth_result.get("type") != "auth_ok":
            print("Authentication failed!")
            return

        print("✓ Connected and authenticated\n")

        # Query history for last 7 days
        end_time = datetime.now()
        start_time = end_time - timedelta(days=7)

        history_request = {
            "id": 1,
            "type": "history/history_during_period",
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "entity_ids": ["counter.test_counter"],
            "minimal_response": False,
            "no_attributes": False
        }

        print(f"Querying history from {start_time.date()} to {end_time.date()}...\n")
        await websocket.send(json.dumps(history_request))

        history_response = await websocket.recv()
        history_data = json.loads(history_response)

        if not history_data.get("success"):
            print(f"History query failed: {history_data}")
            return

        result = history_data.get("result", {})
        entity_history = result.get("counter.test_counter", [])

        print(f"Found {len(entity_history)} state changes:\n")

        # Show all states
        for i, state in enumerate(entity_history[:10]):  # Show first 10
            timestamp_unix = state.get('lu')
            if timestamp_unix:
                dt = datetime.fromtimestamp(timestamp_unix)
                time_str = dt.strftime('%Y-%m-%d %H:%M:%S')
            else:
                time_str = 'N/A'
            print(f"[{i+1}] State: {state.get('s')} at {time_str}")

        # Calculate increments for current week
        print("\n" + "="*60)
        print("WEEKLY INCREMENTS:")
        print("="*60 + "\n")

        # Define week (Sunday = 0, Saturday = 6)
        now = datetime.now()
        # Get start of current week (Sunday)
        days_since_sunday = (now.weekday() + 1) % 7  # Convert to Sunday=0
        week_start = (now - timedelta(days=days_since_sunday)).replace(hour=0, minute=0, second=0, microsecond=0)
        week_end = week_start + timedelta(days=7)

        print(f"Current week: {week_start.date()} to {week_end.date()}")
        print()

        increments_this_week = []
        prev_state = None

        for state in entity_history:
            # Parse timestamp - WebSocket uses 'lu' (last_updated) as Unix timestamp
            timestamp_unix = state.get('lu') or state.get('lc')
            if not timestamp_unix:
                continue

            # Convert Unix timestamp to datetime
            timestamp = datetime.fromtimestamp(timestamp_unix)

            # Get state value - WebSocket uses 's' for state
            state_value = state.get('s') or state.get('state')

            try:
                current_int = int(state_value)

                # Check if it's within current week
                if week_start <= timestamp < week_end:
                    if prev_state is not None:
                        prev_int = int(prev_state)

                        # Only count positive increments (ignore resets)
                        if current_int > prev_int:
                            increment = current_int - prev_int
                            increments_this_week.append({
                                'timestamp': timestamp,
                                'from': prev_int,
                                'to': current_int,
                                'increment': increment
                            })
                            print(f"INCREMENT: {prev_int} → {current_int} (+{increment})")
                            print(f"  Time: {timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
                            print()

                prev_state = state_value

            except (ValueError, TypeError):
                continue

        print(f"\n✓ Total increments this week: {len(increments_this_week)}")

        if increments_this_week:
            total_incremented = sum(inc['increment'] for inc in increments_this_week)
            print(f"✓ Total count this week: {total_incremented}")


if __name__ == "__main__":
    asyncio.run(test_history_websocket())
