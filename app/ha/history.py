"""History querying and progress calculation."""

import logging
from datetime import datetime, timedelta
from typing import Optional

from .client import HAClient
from .models import Goal

logger = logging.getLogger(__name__)


class ProgressCalculator:
    """Calculates goal progress from Home Assistant history."""

    # Reference date for 2-week period alignment (a Sunday)
    PERIOD_ANCHOR = datetime(2020, 1, 5, 0, 0, 0)
    PERIOD_DAYS = 14  # 2-week periods

    def __init__(self, client: HAClient):
        """Initialize with HA client."""
        self.client = client

    async def calculate_progress(self, goals: list[Goal]) -> list[Goal]:
        """
        Calculate current progress for all goals.

        Uses current counter state and updates goal objects with:
        - current_count: Current counter value
        - target_by_now: Expected count by current time
        - status: on_track/behind
        - days_left: Days remaining in 2-week period

        Args:
            goals: List of Goal objects

        Returns:
            Same list with progress fields updated
        """
        if not goals:
            return goals

        logger.info(f"Calculating progress for {len(goals)} goals...")

        # Get current 2-week period boundaries
        period_start, period_end = self._get_current_period()
        logger.info(f"Current 2-week period: {period_start.date()} to {period_end.date()}")

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

                # Update friendly name from state attributes (in case it was renamed in HA)
                attributes = state.get("attributes", {})
                friendly_name = attributes.get("friendly_name")
                if friendly_name:
                    goal.friendly_name = friendly_name
            else:
                logger.warning(f"State not found for {goal.entity_id}")
                current_count = 0

            # Calculate expected progress (weekly_target * 2 for 2-week period)
            day_of_period = self._get_day_of_period(datetime.now())
            period_target = goal.config.weekly_target * 2  # Double for 2-week period
            target_by_now = self._calculate_target_by_now(
                period_target, day_of_period, goal.config.hours_offset
            )

            # Determine status
            status = self._calculate_status(current_count, target_by_now)

            # Calculate days left in 2-week period
            days_left = (self.PERIOD_DAYS - 1) - day_of_period

            # Update goal object
            goal.current_count = current_count
            goal.target_by_now = target_by_now
            goal.status = status
            goal.days_left = days_left

            logger.info(
                f"  {goal.friendly_name}: {current_count}/{period_target} "
                f"(target by now: {target_by_now:.1f}, status: {status})"
            )

        return goals

    def _get_current_period(self) -> tuple[datetime, datetime]:
        """
        Get start and end of current 2-week period.

        Uses a fixed anchor date to ensure consistent 2-week boundaries.

        Returns:
            Tuple of (period_start, period_end) as datetime objects
        """
        now = datetime.now()

        # Calculate days since anchor
        days_since_anchor = (now - self.PERIOD_ANCHOR).days

        # Find which 2-week period we're in
        periods_elapsed = days_since_anchor // self.PERIOD_DAYS
        day_in_period = days_since_anchor % self.PERIOD_DAYS

        # Period start is the beginning of this 2-week period
        period_start = self.PERIOD_ANCHOR + timedelta(days=periods_elapsed * self.PERIOD_DAYS)
        period_start = period_start.replace(hour=0, minute=0, second=0, microsecond=0)

        # Period ends 14 days later minus 1 second
        period_end = period_start + timedelta(days=self.PERIOD_DAYS, seconds=-1)

        return period_start, period_end

    def _get_day_of_period(self, dt: datetime) -> int:
        """
        Get day within the current 2-week period (0-13).

        Args:
            dt: Datetime to check

        Returns:
            Day of period (0-13)
        """
        days_since_anchor = (dt - self.PERIOD_ANCHOR).days
        return days_since_anchor % self.PERIOD_DAYS

    def _calculate_target_by_now(
        self, period_target: float, day_of_period: int, hours_offset: float = 0.0
    ) -> float:
        """
        Calculate expected count by current time (moves smoothly throughout the day).

        Args:
            period_target: Goal for the 2-week period (e.g., 4, or 1.5)
            day_of_period: 0-13 (day within 2-week period)
            hours_offset: Grace period in hours (e.g., 18 means due at 6pm not midnight)

        Returns:
            Expected count by current moment (fractional days elapsed)

        Example:
            period_target = 4, day_of_period = 7 (middle of period), time = 12:00 noon
            days_elapsed = 7.5
            = 4 * (7.5/14) = 2.14

            With hours_offset = 18:
            days_elapsed = 7.5 - (18/24) = 6.75
            = 4 * (6.75/14) = 1.93
        """
        now = datetime.now()
        # Calculate fraction of today that has passed (0.0 at midnight, 1.0 at end of day)
        day_fraction = (now.hour * 3600 + now.minute * 60 + now.second) / 86400
        # Total days elapsed including partial current day
        days_elapsed = day_of_period + day_fraction

        # Apply hours offset (subtract grace period, but don't go below 0)
        offset_days = hours_offset / 24.0
        days_elapsed = max(0.0, days_elapsed - offset_days)

        return period_target * (days_elapsed / self.PERIOD_DAYS)

    def _calculate_status(self, current: int, target_by_now: float) -> str:
        """
        Determine if on track or behind.

        Logic:
        - Compare progress fraction (current/weekly_target) to time fraction (days_elapsed/7)
        - If current < target_by_now: "behind"
        - Otherwise: "on_track"

        Args:
            current: Current count
            target_by_now: Expected count by now (weekly_target * days_elapsed / 7)

        Returns:
            "on_track" or "behind"
        """
        if current < target_by_now:
            return "behind"
        return "on_track"


async def demo_progress():
    """Demo: Calculate and display 2-week progress."""
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
        print("2-WEEK PROGRESS")
        print("=" * 60 + "\n")

        period_start, period_end = calculator._get_current_period()
        day_of_period = calculator._get_day_of_period(datetime.now())

        print(f"Period: {period_start.strftime('%b %d')} - {period_end.strftime('%b %d')}")
        print(f"Today: Day {day_of_period + 1} of 14")
        print()

        for goal in goals:
            emoji = goal.config.emoji or "•"
            status_icon = {"on_track": "✓", "behind": "⚠"}[goal.status]
            period_target = goal.config.weekly_target * 2  # 2-week target

            print(f"{emoji} {goal.friendly_name}")
            print(f"  Progress: {goal.current_count}/{period_target} (weekly: {goal.config.weekly_target})")
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
