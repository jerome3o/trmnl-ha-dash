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

    # Layout constants
    X_MARGIN = 20
    HEADER_HEIGHT = 62
    BOTTOM_MARGIN = 20
    BAR_HEIGHT = 20  # Taller bars

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
        """Load fonts for rendering, including CJK support."""
        fonts = {}

        # Font paths to try - prioritize CJK-capable fonts
        font_paths = [
            # CJK fonts (support Chinese, Japanese, Korean)
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
            "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
            "/usr/share/fonts/truetype/arphic/uming.ttc",
            # Standard fonts (fallback)
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/System/Library/Fonts/Helvetica.ttc",  # macOS
        ]

        loaded_path = None
        try:
            for path in font_paths:
                if Path(path).exists():
                    fonts["header"] = ImageFont.truetype(path, 24)
                    fonts["title"] = ImageFont.truetype(path, 20)
                    fonts["normal"] = ImageFont.truetype(path, 16)
                    fonts["small"] = ImageFont.truetype(path, 14)
                    loaded_path = path
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
        period_start: datetime,
        period_end: datetime,
        width: int = 800,
        height: int = 480,
        weather: Optional[dict] = None,
    ) -> tuple[str, str]:
        """
        Render the dashboard.

        Args:
            goals: List of goals with progress calculated
            period_start: Start of current 2-week period
            period_end: End of current 2-week period
            width: Image width
            height: Image height
            weather: Optional weather data dict with 'temperature', 'condition', etc.

        Returns:
            Tuple of (filename, file_path)
        """
        logger.info(f"Rendering dashboard with {len(goals)} goals")

        # Create image
        image = Image.new("RGB", (width, height), "white")
        draw = ImageDraw.Draw(image)

        # Calculate time position for the continuous line
        now = datetime.now()
        days_into_period = (now - period_start).days
        day_fraction = (now.hour * 3600 + now.minute * 60 + now.second) / 86400
        time_fraction = (days_into_period + day_fraction) / 14

        # Draw midweek line FIRST (behind everything else)
        self._draw_midweek_line(draw, width, height)

        # Draw sections
        self._draw_header(draw, period_start, period_end, width, weather)
        goals_area = self._draw_goals(draw, goals, width, height, time_fraction)

        # Draw continuous time indicator line (full height)
        self._draw_time_indicator(draw, time_fraction, width, height)

        # Draw day ticks at bottom of goals area
        if goals_area:
            self._draw_day_ticks(draw, goals_area, width)

        # Convert to monochrome
        image = self._convert_to_monochrome(image)

        # Save
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        filename = f"dashboard-{timestamp}"
        file_path = self.output_dir / f"{filename}.png"

        image.save(file_path, "PNG")
        logger.info(f"Saved dashboard to {file_path}")

        return filename, str(file_path)

    def _draw_header(
        self,
        draw: ImageDraw,
        period_start: datetime,
        period_end: datetime,
        width: int,
        weather: Optional[dict] = None,
    ):
        """Draw header with 2-week period info, last update time, and optional weather."""
        # Period range
        period_text = f"{period_start.strftime('%b %d')} - {period_end.strftime('%b %d, %Y')}"
        draw.text((self.X_MARGIN, 10), period_text, fill="black", font=self.fonts["title"])

        # Calculate day within 2-week period
        now = datetime.now()
        days_into_period = (now - period_start).days
        day_of_period = min(days_into_period, 13)
        day_names = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
        day_name = day_names[(now.weekday() + 1) % 7]
        day_text = f"Day {day_of_period + 1} of 14 ({day_name})"
        draw.text((self.X_MARGIN, 32), day_text, fill="black", font=self.fonts["small"])

        # Weather info (if available)
        if weather:
            try:
                temp = weather.get("temperature", "")
                condition = weather.get("condition", "")
                weather_text = f"{temp}° {condition}" if temp else ""
                if weather_text:
                    bbox = draw.textbbox((0, 0), weather_text, font=self.fonts["small"])
                    text_width = bbox[2] - bbox[0]
                    draw.text((width - text_width - self.X_MARGIN, 10), weather_text, fill="black", font=self.fonts["small"])
            except Exception as e:
                logger.warning(f"Failed to render weather: {e}")

        # Last update time (right-aligned)
        time_text = f"Updated: {now.strftime('%H:%M')}"
        bbox = draw.textbbox((0, 0), time_text, font=self.fonts["small"])
        text_width = bbox[2] - bbox[0]
        draw.text((width - text_width - self.X_MARGIN, 32), time_text, fill="black", font=self.fonts["small"])

        # Divider line
        draw.line([self.X_MARGIN, 52, width - self.X_MARGIN, 52], fill="black", width=2)

    def _draw_goals(
        self,
        draw: ImageDraw,
        goals: list[Goal],
        width: int,
        height: int,
        time_fraction: float,
    ) -> Optional[dict]:
        """
        Draw all goals with progress bars, evenly distributed.

        Returns:
            Dict with goals area boundaries {top, bottom, left, right} or None if no goals
        """
        if not goals:
            return None

        available_height = height - self.HEADER_HEIGHT - self.BOTTOM_MARGIN
        num_goals = len(goals)
        goal_spacing = available_height / num_goals

        bar_positions = []  # Track bar positions for time indicator

        for i, goal in enumerate(goals):
            y_offset = self.HEADER_HEIGHT + int(i * goal_spacing)
            bar_y = self._draw_goal_row(draw, goal, y_offset, width)
            bar_positions.append(bar_y)

        # Return goals area boundaries
        if bar_positions:
            return {
                "top": bar_positions[0],
                "bottom": bar_positions[-1] + self.BAR_HEIGHT,
                "left": self.X_MARGIN,
                "right": width - self.X_MARGIN,
            }
        return None

    def _draw_goal_row(self, draw: ImageDraw, goal: Goal, y: int, width: int) -> int:
        """
        Draw a single goal with full-width progress bar.

        Returns:
            The y position of the progress bar
        """
        # Goal name with emoji
        if goal.config.emoji:
            name_text = f"{goal.config.emoji} {goal.friendly_name}"
        else:
            name_text = goal.friendly_name

        draw.text((self.X_MARGIN, y), name_text, fill="black", font=self.fonts["normal"])

        # Progress bar
        bar_y = y + 22
        bar_width = width - (self.X_MARGIN * 2)

        # Double weekly_target for 2-week period display
        period_target = goal.config.weekly_target * 2

        self._draw_progress_bar(
            draw,
            x=self.X_MARGIN,
            y=bar_y,
            width=bar_width,
            height=self.BAR_HEIGHT,
            current=goal.current_count,
            target=period_target,
        )

        return bar_y

    def _draw_progress_bar(
        self,
        draw: ImageDraw,
        x: int,
        y: int,
        width: int,
        height: int,
        current: int,
        target: float,
    ):
        """
        Draw progress bar with gray dividers on filled segments.

        For integer targets: bar is divided into segments.
        For fractional targets: smooth bar without segments.
        """
        if target <= 0:
            return

        is_integer_target = target == int(target)
        fill_fraction = min(current / target, 1.0)
        filled_width = int(fill_fraction * width)

        # Draw filled portion
        if filled_width > 0:
            draw.rectangle(
                [x, y, x + filled_width, y + height],
                fill="black",
            )

            # Draw gray/white dividers on filled segments so you can see increments
            if is_integer_target:
                int_target = int(target)
                segment_width = width / int_target
                for i in range(1, int_target):
                    seg_x = x + int(i * segment_width)
                    if seg_x < x + filled_width:
                        # Gray line on filled portion
                        draw.line([seg_x, y, seg_x, y + height], fill="white", width=2)

        # Draw bar outline
        draw.rectangle(
            [x, y, x + width, y + height],
            outline="black",
            width=1,
        )

        # Draw segment dividers on unfilled portion
        if is_integer_target:
            int_target = int(target)
            segment_width = width / int_target
            for i in range(1, int_target):
                seg_x = x + int(i * segment_width)
                if seg_x >= x + filled_width:
                    draw.line([seg_x, y, seg_x, y + height], fill="black", width=1)

    def _draw_midweek_line(self, draw: ImageDraw, width: int, height: int):
        """Draw light gray midweek line from header divider to bottom (behind everything)."""
        bar_width = width - (self.X_MARGIN * 2)
        midpoint_x = self.X_MARGIN + int((7 / 14) * bar_width)

        # Weekend is 2 days (Sat-Sun), so width = 2/14 of bar
        weekend_width = int((2 / 14) * bar_width)

        # Light gray, thick as weekend, from header line to bottom
        draw.line(
            [midpoint_x, 52, midpoint_x, height],  # Start at header divider (y=52)
            fill="#d0d0d0",  # Light gray
            width=weekend_width,
        )

    def _draw_time_indicator(
        self,
        draw: ImageDraw,
        time_fraction: float,
        width: int,
        height: int,
    ):
        """Draw continuous dashed vertical line from header divider to bottom."""
        bar_width = width - (self.X_MARGIN * 2)
        marker_x = self.X_MARGIN + int(time_fraction * bar_width)
        marker_x = max(self.X_MARGIN + 2, min(marker_x, width - self.X_MARGIN - 2))

        # From header divider to bottom
        marker_top = 52  # Header divider line
        marker_bottom = height

        # Dashed line pattern
        dash_length = 4
        gap_length = 3
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

    def _draw_day_ticks(self, draw: ImageDraw, goals_area: dict, width: int):
        """Draw day ticks for all 14 days."""
        bar_width = goals_area["right"] - goals_area["left"]
        tick_y_top = goals_area["bottom"] + 3
        tick_y_bottom = goals_area["bottom"] + 8

        # Draw ticks for all 14 days (bolder)
        for day in range(15):  # 0 through 14
            tick_x = goals_area["left"] + int((day / 14) * bar_width)
            tick_x = max(goals_area["left"], min(tick_x, goals_area["right"]))

            # Weekend days (0, 6, 7, 8, 13, 14) get slightly longer ticks
            is_weekend = day in [0, 6, 7, 8, 13, 14]
            tick_bottom = tick_y_bottom + (2 if is_weekend else 0)
            tick_width = 2

            draw.line([tick_x, tick_y_top, tick_x, tick_bottom], fill="black", width=tick_width)

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
        period_start, period_end = calculator._get_current_period()
        filename, file_path = renderer.render(goals, period_start, period_end)

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
