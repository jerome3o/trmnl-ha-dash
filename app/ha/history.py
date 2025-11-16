"""History querying and progress calculation."""

import logging
from datetime import datetime, timedelta
from typing import Optional

from .client import HAClient
from .models import Goal

logger = logging.getLogger(__name__)


class ProgressCalculator:
    """Calculates goal progress from Home Assistant history."""

    def __init__(self, client: HAClient):
        """Initialize with HA client."""
        self.client = client

    async def calculate_progress(self, goals: list[Goal]) -> list[Goal]:
        """
        Calculate current progress for all goals.

        Uses current counter state and updates goal objects with:
        - current_count: Current counter value
        - target_by_now: Expected count by today
        - status: ahead/on_track/behind
        - days_left: Days remaining in week

        Args:
            goals: List of Goal objects

        Returns:
            Same list with progress fields updated
        """
        if not goals:
            return goals

        logger.info(f"Calculating progress for {len(goals)} goals...")

        # Get current week boundaries for status display
        week_start, week_end = self._get_current_week()
        logger.info(f"Current week: {week_start.date()} to {week_end.date()}")

        # Get current states for all goal entities
        states = await self.client.send_command("get_states")

        # Create a mapping of entity_id to state
        state_map = {state.get("entity_id"): state for state in states}

        # Calculate progress for each goal
        for goal in goals:
            state = state_map.get(goal.entity_id)

            # Get current counter value
            if state:
                try:
                    current_count = int(state.get("state", 0))
                except (ValueError, TypeError):
                    logger.warning(f"Invalid state for {goal.entity_id}: {state.get('state')}")
                    current_count = 0
            else:
                logger.warning(f"State not found for {goal.entity_id}")
                current_count = 0

            # Calculate expected progress
            day_of_week = self._get_day_of_week(datetime.now())
            target_by_now = self._calculate_target_by_now(
                goal.config.weekly_target, day_of_week
            )

            # Determine status
            status = self._calculate_status(current_count, target_by_now)

            # Calculate days left
            days_left = 6 - day_of_week  # Sunday=0, Saturday=6

            # Update goal object
            goal.current_count = current_count
            goal.target_by_now = target_by_now
            goal.status = status
            goal.days_left = days_left

            logger.info(
                f"  {goal.friendly_name}: {current_count}/{goal.config.weekly_target} "
                f"(target by now: {target_by_now:.1f}, status: {status})"
            )

        return goals

    def _get_current_week(self) -> tuple[datetime, datetime]:
        """
        Get start and end of current week (Sunday-Saturday).

        Returns:
            Tuple of (week_start, week_end) as datetime objects
        """
        now = datetime.now()

        # Calculate days since Sunday (0=Sunday, 6=Saturday)
        days_since_sunday = (now.weekday() + 1) % 7

        # Week starts Sunday 00:00:00
        week_start = (now - timedelta(days=days_since_sunday)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )

        # Week ends Saturday 23:59:59
        week_end = week_start + timedelta(days=7, seconds=-1)

        return week_start, week_end

    def _get_day_of_week(self, dt: datetime) -> int:
        """
        Get day of week where Sunday=0, Saturday=6.

        Args:
            dt: Datetime to check

        Returns:
            Day of week (0-6)
        """
        # Python weekday: Monday=0, Sunday=6
        # Convert to: Sunday=0, Saturday=6
        return (dt.weekday() + 1) % 7


    def _calculate_target_by_now(self, weekly_target: int, day_of_week: int) -> float:
        """
        Calculate expected count by current day.

        Args:
            weekly_target: Goal for the full week (e.g., 4)
            day_of_week: 0=Sunday, 6=Saturday

        Returns:
            Expected count by end of current day

        Example:
            weekly_target = 4, day_of_week = 3 (Wednesday)
            = 4 * (4/7) = 2.29
        """
        return weekly_target * ((day_of_week + 1) / 7)

    def _calculate_status(self, current: int, target_by_now: float) -> str:
        """
        Determine if ahead, on track, or behind.

        Args:
            current: Current count
            target_by_now: Expected count

        Returns:
            "ahead", "on_track", or "behind"
        """
        diff = current - target_by_now

        if diff >= 0.5:
            return "ahead"
        elif diff <= -0.5:
            return "behind"
        else:
            return "on_track"


async def demo_progress():
    """Demo: Calculate and display weekly progress."""
    import os
    from dotenv import load_dotenv
    from .discovery import GoalDiscovery

    load_dotenv()

    ha_url = os.getenv("HA_URL")
    ha_token = os.getenv("HA_API_KEY")

    if not ha_url or not ha_token:
        print("Error: HA_URL and HA_API_KEY must be set in .env file")
        return

    client = HAClient(ha_url, ha_token)

    try:
        await client.connect()

        # Discover goals
        discovery = GoalDiscovery(client)
        goals = await discovery.discover_goals()

        if not goals:
            print("\nNo goals found! Run Demo 1 first to check setup.")
            return

        # Calculate progress
        calculator = ProgressCalculator(client)
        goals = await calculator.calculate_progress(goals)

        # Display results
        print("\n" + "=" * 60)
        print("WEEKLY PROGRESS")
        print("=" * 60 + "\n")

        week_start, week_end = calculator._get_current_week()
        day_of_week = calculator._get_day_of_week(datetime.now())
        day_names = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]

        print(f"Week: {week_start.strftime('%b %d')} - {week_end.strftime('%b %d')}")
        print(f"Today: {day_names[day_of_week]} (day {day_of_week + 1} of 7)")
        print()

        for goal in goals:
            emoji = goal.config.emoji or "•"
            status_icon = {"ahead": "⭐", "on_track": "✓", "behind": "⚠"}[goal.status]

            print(f"{emoji} {goal.friendly_name}")
            print(f"  Progress: {goal.current_count}/{goal.config.weekly_target}")
            print(f"  Target by now: {goal.target_by_now:.1f}")
            print(f"  Status: {goal.status.upper()} {status_icon}")
            print(f"  Days left: {goal.days_left}")
            print()

    finally:
        await client.disconnect()


if __name__ == "__main__":
    import asyncio

    logging.basicConfig(level=logging.INFO)
    asyncio.run(demo_progress())
