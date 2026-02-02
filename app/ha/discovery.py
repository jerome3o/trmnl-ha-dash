"""Goal discovery from Home Assistant labels and entities."""

import json
import logging
from typing import Optional

from .client import HAClient
from .models import Goal, GoalConfig

logger = logging.getLogger(__name__)


class GoalDiscovery:
    """Discovers and configures goals from HA labels and entities."""

    def __init__(self, client: HAClient):
        """Initialize with HA client."""
        self.client = client

    async def discover_goals(self) -> list[Goal]:
        """
        Discover all goals configured in Home Assistant.

        Looks for labels starting with "goal_" and finds entities with those labels.

        Returns:
            List of Goal objects
        """
        logger.info("Discovering goals from Home Assistant...")

        # Get all labels
        all_labels = await self.client.get_labels()
        logger.debug(f"Found {len(all_labels)} total labels")

        # Debug: print all labels
        for label in all_labels:
            logger.debug(f"  Label: {label.get('label_id')} - {label.get('name')}")

        # Filter for goal labels (check name field, not label_id)
        goal_labels = [
            label for label in all_labels if label.get("name", "").startswith("goal_")
        ]
        logger.info(f"Found {len(goal_labels)} goal labels")

        # Parse goal configurations from labels
        goal_configs = {}
        for label in goal_labels:
            config = self._parse_label_config(label)
            if config:
                # Use label_id as key (entities reference label_id, not name)
                goal_configs[label["label_id"]] = config

        logger.info(f"Parsed {len(goal_configs)} valid goal configurations")

        # Get all entities
        all_entities = await self.client.get_entities()
        logger.debug(f"Found {len(all_entities)} entities in registry")

        # Find entities with goal labels
        goals = []
        for entity in all_entities:
            entity_labels = entity.get("labels", [])
            entity_id = entity.get("entity_id")

            # Check if entity has any goal label
            for label_id in entity_labels:
                if label_id in goal_configs:
                    # Found a goal entity!
                    goal = Goal(
                        entity_id=entity_id,
                        friendly_name=self._get_friendly_name(entity),
                        label_id=label_id,
                        config=goal_configs[label_id],
                    )
                    goals.append(goal)
                    logger.info(f"  ✓ Discovered goal: {goal.friendly_name} ({entity_id})")
                    break  # Only use first matching goal label

        logger.info(f"Discovered {len(goals)} goals total")
        return goals

    def _parse_label_config(self, label: dict) -> Optional[GoalConfig]:
        """
        Parse goal configuration from label description.

        Args:
            label: Label dictionary from HA

        Returns:
            GoalConfig if valid, None if invalid
        """
        label_id = label.get("label_id")
        label_name = label.get("name", label_id)
        description = label.get("description", "")

        if not description:
            logger.warning(f"Label {label_name} has no description, skipping")
            return None

        try:
            # Parse JSON from description
            config_data = json.loads(description)

            # Extract weekly_target (required) - supports int or float (e.g., 1.5 for "3 per 2 weeks")
            weekly_target = config_data.get("weekly_target")
            if weekly_target is None or not isinstance(weekly_target, (int, float)) or weekly_target <= 0:
                logger.warning(f"Label {label_name} missing valid weekly_target, skipping")
                return None
            weekly_target = float(weekly_target)  # Ensure it's a float

            # Extract optional fields
            emoji = config_data.get("emoji")
            sound = config_data.get("sound")

            return GoalConfig(
                label_id=label_name,  # Store the name, not internal ID
                weekly_target=weekly_target,
                emoji=emoji,
                sound=sound,
            )

        except json.JSONDecodeError as e:
            logger.warning(f"Label {label_name} has invalid JSON in description: {e}")
            return None

    def _get_friendly_name(self, entity: dict) -> str:
        """
        Get friendly name for an entity.

        Args:
            entity: Entity dictionary from HA

        Returns:
            Friendly name or entity ID if not available
        """
        # Try entity's name field first
        name = entity.get("name")
        if name:
            return name

        # Try original_name
        name = entity.get("original_name")
        if name:
            return name

        # Fall back to entity ID
        entity_id = entity.get("entity_id", "Unknown")
        # Convert "counter.gym_visits" to "Gym Visits"
        if "." in entity_id:
            name_part = entity_id.split(".")[1]
            return name_part.replace("_", " ").title()

        return entity_id


async def demo_discovery():
    """Demo: Discover and print all goals."""
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

        discovery = GoalDiscovery(client)
        goals = await discovery.discover_goals()

        print("\n" + "=" * 60)
        print("DISCOVERED GOALS")
        print("=" * 60 + "\n")

        if not goals:
            print("No goals found!")
            print("\nTo create goals:")
            print("1. Create a label in HA like 'goal_4_per_week'")
            print('2. Set description to: {"weekly_target": 4}')
            print("3. Assign label to a counter entity")
            return

        for goal in goals:
            print(f"Goal: {goal.friendly_name}")
            print(f"  Entity ID: {goal.entity_id}")
            print(f"  Label: {goal.label_id}")
            print(f"  Weekly Target: {goal.config.weekly_target}")
            if goal.config.emoji:
                print(f"  Emoji: {goal.config.emoji}")
            print()

    finally:
        await client.disconnect()


if __name__ == "__main__":
    import asyncio

    logging.basicConfig(level=logging.DEBUG)
    asyncio.run(demo_discovery())
