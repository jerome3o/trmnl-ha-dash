"""Dashboard image renderer."""

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageFont

from app.ha.models import Goal

logger = logging.getLogger(__name__)


class DashboardRenderer:
    """Renders habit tracker dashboard to image."""

    def __init__(self, output_dir: str = "static/images"):
        """
        Initialize renderer.

        Args:
            output_dir: Directory to save generated images
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Try to load fonts, fall back to default
        self.fonts = self._load_fonts()

    def _load_fonts(self) -> dict:
        """Load fonts for rendering."""
        fonts = {}

        # Try to find system fonts
        font_paths = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/System/Library/Fonts/Helvetica.ttc",  # macOS
        ]

        try:
            # Regular fonts
            for path in font_paths:
                if Path(path).exists():
                    fonts["header"] = ImageFont.truetype(path, 24)
                    fonts["title"] = ImageFont.truetype(path, 20)
                    fonts["normal"] = ImageFont.truetype(path, 16)
                    fonts["small"] = ImageFont.truetype(path, 14)
                    logger.info(f"Loaded fonts from {path}")
                    break
        except Exception as e:
            logger.warning(f"Could not load TrueType fonts: {e}, using default")

        # Fall back to default fonts
        if not fonts:
            default_font = ImageFont.load_default()
            fonts["header"] = default_font
            fonts["title"] = default_font
            fonts["normal"] = default_font
            fonts["small"] = default_font

        return fonts

    def render(
        self,
        goals: list[Goal],
        week_start: datetime,
        week_end: datetime,
        width: int = 800,
        height: int = 480,
    ) -> tuple[str, str]:
        """
        Render the dashboard.

        Args:
            goals: List of goals with progress calculated
            week_start: Start of current week
            week_end: End of current week
            width: Image width
            height: Image height

        Returns:
            Tuple of (filename, file_path)
        """
        logger.info(f"Rendering dashboard with {len(goals)} goals")

        # Create image
        image = Image.new("RGB", (width, height), "white")
        draw = ImageDraw.Draw(image)

        # Draw sections
        self._draw_header(draw, week_start, week_end, width)
        self._draw_goals(draw, goals, width, height)
        self._draw_footer(draw, goals, width, height)

        # Convert to monochrome
        image = self._convert_to_monochrome(image)

        # Save
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        filename = f"dashboard-{timestamp}"
        file_path = self.output_dir / f"{filename}.png"

        image.save(file_path, "PNG")
        logger.info(f"Saved dashboard to {file_path}")

        return filename, str(file_path)

    def _draw_header(self, draw: ImageDraw, week_start: datetime, week_end: datetime, width: int):
        """Draw header with week info."""
        # Week range
        week_text = f"Week: {week_start.strftime('%b %d')} - {week_end.strftime('%b %d, %Y')}"
        draw.text((20, 15), week_text, fill="black", font=self.fonts["header"])

        # Current day
        day_names = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
        now = datetime.now()
        day_of_week = (now.weekday() + 1) % 7
        day_text = f"Day {day_of_week + 1} of 7 ({day_names[day_of_week]})"

        # Right-align day text
        bbox = draw.textbbox((0, 0), day_text, font=self.fonts["normal"])
        text_width = bbox[2] - bbox[0]
        draw.text((width - text_width - 20, 18), day_text, fill="black", font=self.fonts["normal"])

        # Divider line
        draw.line([20, 50, width - 20, 50], fill="black", width=2)

    def _draw_goals(self, draw: ImageDraw, goals: list[Goal], width: int, height: int):
        """Draw all goals with progress bars."""
        y_offset = 70

        for goal in goals:
            if y_offset > height - 100:  # Leave room for footer
                break

            self._draw_goal_row(draw, goal, y_offset, width)
            y_offset += 85

    def _draw_goal_row(self, draw: ImageDraw, goal: Goal, y: int, width: int):
        """Draw a single goal with progress bar and status."""
        x_margin = 30

        # Goal name with emoji
        if goal.config.emoji:
            name_text = f"{goal.config.emoji} {goal.friendly_name}"
        else:
            name_text = goal.friendly_name

        draw.text((x_margin, y), name_text, fill="black", font=self.fonts["title"])

        # Progress bar
        bar_y = y + 35
        bar_width = 400
        bar_height = 25

        self._draw_progress_bar(
            draw,
            x=x_margin,
            y=bar_y,
            width=bar_width,
            height=bar_height,
            current=goal.current_count,
            target=goal.config.weekly_target,
            target_marker=goal.target_by_now,
        )

        # Progress text and status
        progress_text = f"{goal.current_count}/{goal.config.weekly_target}"
        target_text = f"Target: {goal.target_by_now:.1f}"

        # Status with icon
        status_icons = {"ahead": "⭐ AHEAD", "on_track": "✓ ON TRACK", "behind": "⚠ BEHIND"}
        status_text = status_icons[goal.status]

        # Draw text to right of progress bar
        text_x = x_margin + bar_width + 20
        draw.text((text_x, bar_y - 5), progress_text, fill="black", font=self.fonts["normal"])
        draw.text((text_x, bar_y + 15), target_text, fill="black", font=self.fonts["small"])

        # Status (right-aligned)
        bbox = draw.textbbox((0, 0), status_text, font=self.fonts["normal"])
        status_width = bbox[2] - bbox[0]
        draw.text((width - status_width - 30, bar_y + 3), status_text, fill="black", font=self.fonts["normal"])

    def _draw_progress_bar(
        self,
        draw: ImageDraw,
        x: int,
        y: int,
        width: int,
        height: int,
        current: int,
        target: int,
        target_marker: float,
    ):
        """
        Draw progress bar with target marker.

        The bar is divided into segments equal to target.
        Target marker shows expected progress by today.
        """
        if target == 0:
            return

        segment_width = width / target

        # Draw filled segments (completed)
        filled_segments = min(current, target)
        filled_width = int(filled_segments * segment_width)

        if filled_width > 0:
            draw.rectangle(
                [x, y, x + filled_width, y + height],
                fill="black",
                outline="black",
            )

        # Draw empty segments outline
        draw.rectangle(
            [x, y, x + width, y + height],
            outline="black",
            width=2,
        )

        # Draw segment dividers
        for i in range(1, target):
            seg_x = x + int(i * segment_width)
            draw.line([seg_x, y, seg_x, y + height], fill="black", width=1)

        # Draw target marker (vertical line)
        marker_x = x + int(target_marker * segment_width)
        marker_x = max(x, min(marker_x, x + width))  # Clamp to bar bounds

        # Draw marker as thick vertical line
        draw.line(
            [marker_x, y - 8, marker_x, y + height + 8],
            fill="black",
            width=4,
        )

        # Draw small triangle at top of marker
        triangle_size = 6
        draw.polygon(
            [
                (marker_x, y - 8),
                (marker_x - triangle_size, y - 8 - triangle_size),
                (marker_x + triangle_size, y - 8 - triangle_size),
            ],
            fill="black",
        )

    def _draw_footer(self, draw: ImageDraw, goals: list[Goal], width: int, height: int):
        """Draw footer with summary stats."""
        y = height - 35

        # Divider line
        draw.line([20, y - 10, width - 20, y - 10], fill="black", width=2)

        # Overall progress
        total_current = sum(g.current_count for g in goals)
        total_target = sum(g.config.weekly_target for g in goals)

        if total_target > 0:
            percentage = int((total_current / total_target) * 100)
            summary_text = f"Overall: {total_current}/{total_target} ({percentage}%)"
        else:
            summary_text = "Overall: No goals"

        draw.text((20, y), summary_text, fill="black", font=self.fonts["normal"])

        # Last update time
        time_text = f"Last update: {datetime.now().strftime('%H:%M')}"
        bbox = draw.textbbox((0, 0), time_text, font=self.fonts["small"])
        text_width = bbox[2] - bbox[0]
        draw.text((width - text_width - 20, y + 2), time_text, fill="black", font=self.fonts["small"])

    def _convert_to_monochrome(self, image: Image) -> Image:
        """Convert image to monochrome for e-ink display."""
        return image.convert("1")


async def demo_render():
    """Demo: Render dashboard image."""
    import os
    from dotenv import load_dotenv
    from app.ha.client import HAClient
    from app.ha.discovery import GoalDiscovery
    from app.ha.history import ProgressCalculator

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
            print("\nNo goals found!")
            return

        # Calculate progress
        calculator = ProgressCalculator(client)
        goals = await calculator.calculate_progress(goals)

        # Render dashboard
        renderer = DashboardRenderer()
        week_start, week_end = calculator._get_current_week()
        filename, file_path = renderer.render(goals, week_start, week_end)

        print("\n" + "=" * 60)
        print("DASHBOARD RENDERED")
        print("=" * 60)
        print(f"\nImage saved to: {file_path}")
        print(f"\nView it with: xdg-open {file_path}")
        print("(or open the file in your file browser)")

    finally:
        await client.disconnect()


if __name__ == "__main__":
    import asyncio
    import logging

    logging.basicConfig(level=logging.INFO)
    asyncio.run(demo_render())
