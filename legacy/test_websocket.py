#!/usr/bin/env python3
"""Test Home Assistant WebSocket API to retrieve entity labels."""

import asyncio
import json
import os
import websockets


async def test_ha_websocket():
    """Connect to HA WebSocket and query entity registry for labels."""

    ha_url = os.getenv("HA_URL", "http://192.168.1.128:8123/")
    ha_token = os.getenv("HA_API_KEY")

    # Convert HTTP URL to WebSocket URL
    ws_url = ha_url.replace("http://", "ws://").replace("https://", "wss://")
    if not ws_url.endswith("/"):
        ws_url += "/"
    ws_url += "api/websocket"

    print(f"Connecting to: {ws_url}")

    async with websockets.connect(ws_url) as websocket:
        # 1. Receive auth required message
        auth_msg = await websocket.recv()
        print(f"\n1. Auth required:\n{auth_msg}\n")

        # 2. Send auth token
        auth_payload = {
            "type": "auth",
            "access_token": ha_token
        }
        await websocket.send(json.dumps(auth_payload))
        print(f"2. Sent auth token")

        # 3. Receive auth result
        auth_result = await websocket.recv()
        print(f"\n3. Auth result:\n{auth_result}\n")

        auth_data = json.loads(auth_result)
        if auth_data.get("type") != "auth_ok":
            print("Authentication failed!")
            return

        print("✓ Authentication successful!\n")

        # 4. Request entity registry list
        registry_request = {
            "id": 1,
            "type": "config/entity_registry/list"
        }
        await websocket.send(json.dumps(registry_request))
        print(f"4. Requesting entity registry...")

        # 5. Receive entity registry response
        registry_response = await websocket.recv()
        registry_data = json.loads(registry_response)

        if not registry_data.get("success"):
            print(f"Registry request failed: {registry_data}")
            return

        entities = registry_data.get("result", [])
        print(f"\n5. Received {len(entities)} entities\n")

        # 6. Find entities with labels
        entities_with_labels = [e for e in entities if e.get("labels")]

        print(f"Found {len(entities_with_labels)} entities with labels:")
        for entity in entities_with_labels[:10]:  # Show first 10
            print(f"\n  Entity: {entity.get('entity_id')}")
            print(f"  Labels: {entity.get('labels')}")
            print(f"  Name: {entity.get('name', 'N/A')}")

        # 7. Look specifically for counter.test_counter
        test_counter = next((e for e in entities if e.get("entity_id") == "counter.test_counter"), None)

        if test_counter:
            print(f"\n\n✓ Found counter.test_counter!")
            print(json.dumps(test_counter, indent=2))
        else:
            print(f"\n\n✗ counter.test_counter not found in entity registry")
            print("This might be because it's a simple helper not in the registry")

        # 8. Request label registry to see all available labels
        label_request = {
            "id": 2,
            "type": "config/label_registry/list"
        }
        await websocket.send(json.dumps(label_request))
        print(f"\n\n6. Requesting label registry...")

        label_response = await websocket.recv()
        label_data = json.loads(label_response)

        if label_data.get("success"):
            labels = label_data.get("result", [])
            print(f"\nFound {len(labels)} labels defined:")
            for label in labels:
                print(f"\n  Label ID: {label.get('label_id')}")
                print(f"  Name: {label.get('name')}")
                print(f"  Description: {label.get('description', 'N/A')}")
                print(f"  Icon: {label.get('icon', 'N/A')}")
                print(f"  Color: {label.get('color', 'N/A')}")


if __name__ == "__main__":
    asyncio.run(test_ha_websocket())
