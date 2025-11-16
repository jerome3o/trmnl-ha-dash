"""Home Assistant WebSocket client."""

import asyncio
import json
import logging
from typing import Optional
import websockets

logger = logging.getLogger(__name__)


class HAClient:
    """WebSocket client for Home Assistant API."""

    def __init__(self, ha_url: str, ha_token: str):
        """
        Initialize HA client.

        Args:
            ha_url: Home Assistant URL (e.g., http://192.168.1.128:8123)
            ha_token: Long-lived access token
        """
        self.ha_url = ha_url
        self.ha_token = ha_token
        self.ws_url = self._convert_to_ws_url(ha_url)
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self._message_id = 0

    def _convert_to_ws_url(self, http_url: str) -> str:
        """Convert HTTP URL to WebSocket URL."""
        ws_url = http_url.replace("http://", "ws://").replace("https://", "wss://")
        if not ws_url.endswith("/"):
            ws_url += "/"
        return ws_url + "api/websocket"

    async def connect(self):
        """Connect and authenticate to Home Assistant WebSocket API."""
        logger.info(f"Connecting to {self.ws_url}")

        self.websocket = await websockets.connect(self.ws_url)

        # Receive auth required message
        auth_required = json.loads(await self.websocket.recv())
        logger.debug(f"Auth required: {auth_required}")

        if auth_required.get("type") != "auth_required":
            raise Exception(f"Unexpected message: {auth_required}")

        # Send auth token
        await self.websocket.send(
            json.dumps({"type": "auth", "access_token": self.ha_token})
        )

        # Receive auth result
        auth_result = json.loads(await self.websocket.recv())
        logger.debug(f"Auth result: {auth_result}")

        if auth_result.get("type") != "auth_ok":
            raise Exception(f"Authentication failed: {auth_result}")

        logger.info("✓ Connected and authenticated to Home Assistant")

    async def disconnect(self):
        """Disconnect from Home Assistant."""
        if self.websocket:
            await self.websocket.close()
            self.websocket = None
            logger.info("Disconnected from Home Assistant")

    async def send_command(self, command_type: str, **kwargs) -> dict:
        """
        Send a command to Home Assistant and wait for response.

        Args:
            command_type: Command type (e.g., "config/label_registry/list")
            **kwargs: Additional command parameters

        Returns:
            Response data dictionary
        """
        if not self.websocket:
            raise Exception("Not connected to Home Assistant")

        self._message_id += 1
        message = {"id": self._message_id, "type": command_type, **kwargs}

        logger.debug(f"Sending command: {command_type} (id={self._message_id})")
        await self.websocket.send(json.dumps(message))

        # Wait for response with matching ID
        while True:
            response_text = await self.websocket.recv()
            response = json.loads(response_text)

            if response.get("id") == self._message_id:
                if not response.get("success"):
                    logger.error(f"Command failed: {response}")
                    raise Exception(f"Command failed: {response.get('error', 'Unknown error')}")

                logger.debug(f"Received response for id={self._message_id}")
                return response.get("result", {})

    async def get_labels(self) -> list[dict]:
        """
        Get all labels from Home Assistant.

        Returns:
            List of label dictionaries with keys: label_id, name, description, icon, color
        """
        return await self.send_command("config/label_registry/list")

    async def get_entities(self) -> list[dict]:
        """
        Get all entities from Home Assistant entity registry.

        Returns:
            List of entity dictionaries
        """
        return await self.send_command("config/entity_registry/list")

    async def get_state(self, entity_id: str) -> dict:
        """
        Get current state of an entity.

        Args:
            entity_id: Entity ID (e.g., "counter.gym_visits")

        Returns:
            State dictionary
        """
        states = await self.send_command("get_states")
        for state in states:
            if state.get("entity_id") == entity_id:
                return state
        raise Exception(f"Entity not found: {entity_id}")

    async def get_history(
        self, entity_ids: list[str], start_time: str, end_time: str
    ) -> dict:
        """
        Query history for entities during a time period.

        Args:
            entity_ids: List of entity IDs to query
            start_time: Start time in ISO format
            end_time: End time in ISO format

        Returns:
            Dictionary mapping entity_id to list of state changes
        """
        result = await self.send_command(
            "history/history_during_period",
            start_time=start_time,
            end_time=end_time,
            entity_ids=entity_ids,
            minimal_response=False,
            no_attributes=False,
        )
        return result


async def test_connection():
    """Test HA connection."""
    import os
    from dotenv import load_dotenv

    load_dotenv()

    ha_url = os.getenv("HA_URL")
    ha_token = os.getenv("HA_API_KEY")

    if not ha_url or not ha_token:
        print("Error: HA_URL and HA_API_KEY must be set in .env file")
        return

    client = HAClient(ha_url, ha_token)

    try:
        await client.connect()

        # Test getting labels
        labels = await client.get_labels()
        print(f"\nFound {len(labels)} labels")
        for label in labels:
            print(f"  - {label.get('name')}: {label.get('description')}")

        # Test getting entities
        entities = await client.get_entities()
        print(f"\nFound {len(entities)} entities in registry")

    finally:
        await client.disconnect()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(test_connection())
