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
        """Draw header with week info and last update time."""
        # Week range
        week_text = f"Week: {week_start.strftime('%b %d')} - {week_end.strftime('%b %d, %Y')}"
        draw.text((20, 10), week_text, fill="black", font=self.fonts["title"])

        # Current day and last update on second line
        day_names = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
        now = datetime.now()
        day_of_week = (now.weekday() + 1) % 7
        day_text = f"Day {day_of_week + 1} of 7 ({day_names[day_of_week]})"
        draw.text((20, 32), day_text, fill="black", font=self.fonts["small"])

        # Last update time (right-aligned)
        time_text = f"Updated: {now.strftime('%H:%M')}"
        bbox = draw.textbbox((0, 0), time_text, font=self.fonts["small"])
        text_width = bbox[2] - bbox[0]
        draw.text((width - text_width - 20, 32), time_text, fill="black", font=self.fonts["small"])

        # Divider line
        draw.line([20, 52, width - 20, 52], fill="black", width=2)

    def _draw_goals(self, draw: ImageDraw, goals: list[Goal], width: int, height: int):
        """Draw all goals with progress bars, evenly distributed."""
        if not goals:
            return

        header_height = 62  # Space used by header
        bottom_margin = 15  # Margin at bottom
        available_height = height - header_height - bottom_margin

        # Distribute goals evenly across available space
        num_goals = len(goals)
        goal_spacing = available_height / num_goals

        for i, goal in enumerate(goals):
            y_offset = header_height + int(i * goal_spacing)
            self._draw_goal_row(draw, goal, y_offset, width)

    def _draw_goal_row(self, draw: ImageDraw, goal: Goal, y: int, width: int):
        """Draw a single goal with full-width slim progress bar."""
        x_margin = 20

        # Goal name with emoji
        if goal.config.emoji:
            name_text = f"{goal.config.emoji} {goal.friendly_name}"
        else:
            name_text = goal.friendly_name

        draw.text((x_margin, y), name_text, fill="black", font=self.fonts["normal"])

        # Progress bar - full width, fixed slim height
        bar_y = y + 20
        bar_width = width - (x_margin * 2)
        bar_height = 14  # Slim, consistent height

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
        Draw slim progress bar with dotted target marker.

        The bar is divided into segments equal to target.
        Target marker shows expected progress as a thin dotted line.
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
            )

        # Draw bar outline
        draw.rectangle(
            [x, y, x + width, y + height],
            outline="black",
            width=1,
        )

        # Draw segment dividers (thin lines)
        for i in range(1, target):
            seg_x = x + int(i * segment_width)
            draw.line([seg_x, y, seg_x, y + height], fill="black", width=1)

        # Draw target marker as dashed vertical line with small arrow
        marker_x = x + int(target_marker * segment_width)
        marker_x = max(x + 2, min(marker_x, x + width - 2))  # Clamp with padding

        # Dashed line pattern (more visible than dots)
        dash_length = 4
        gap_length = 3
        marker_top = y - 6
        marker_bottom = y + height + 6
        current_y = marker_top
        drawing = True
        while current_y < marker_bottom:
            if drawing:
                end_y = min(current_y + dash_length, marker_bottom)
                draw.line([marker_x, current_y, marker_x, end_y], fill="black", width=2)
                current_y = end_y
            else:
                current_y += gap_length
            drawing = not drawing

        # Small downward arrow at top
        arrow_size = 3
        draw.polygon(
            [
                (marker_x, marker_top),
                (marker_x - arrow_size, marker_top - arrow_size),
                (marker_x + arrow_size, marker_top - arrow_size),
            ],
            fill="black",
        )

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
