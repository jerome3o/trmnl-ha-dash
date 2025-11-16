# TRMNL Home Assistant Habit Tracker - Technical Specification

## Overview

A BYOS (Bring Your Own Server) TRMNL server that integrates with Home Assistant to create a visual habit tracking "star chart" on an e-ink display. The system tracks user-defined goals (like gym visits, medication adherence, etc.) and displays weekly progress with visual indicators showing whether you're ahead or behind schedule.

## Core Objectives

1. **Visual Progress Tracking**: Display weekly goal progress on TRMNL e-ink display with ahead/behind indicators
2. **Zero Local Storage**: Use Home Assistant's history API, no local database needed
3. **Flexible Configuration**: Easy addition of new goals via Home Assistant labels
4. **Simple Architecture**: Lightweight implementation using FastAPI + Pillow + WebSocket
5. **Extensible Design**: Well-factored to support future dashboard types

## System Architecture

### High-Level Flow

```
┌────────────────────────────────────────────────────────────┐
│                    Home Assistant                           │
│                                                             │
│  Labels:                    Entities:                       │
│  - goal_4_per_week          - counter.gym_visits            │
│  - goal_3_per_week          - counter.toe_care              │
│  - goal_7_per_week          - counter.meditation            │
│                                                             │
│  History API: All counter increments with timestamps        │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          │ WebSocket API
                          ▼
         ┌────────────────────────────────────────┐
         │  TRMNL-HA-DASH Server (Python)         │
         │                                        │
         │  ┌──────────────────────────────────┐ │
         │  │   TRMNL BYOS API Endpoints       │ │
         │  │  - GET /api/display              │ │
         │  │  - POST /api/setup               │ │
         │  │  - POST /api/log                 │ │
         │  └──────────────────────────────────┘ │
         │  ┌──────────────────────────────────┐ │
         │  │   HA WebSocket Client            │ │
         │  │  - Entity/Label Discovery        │ │
         │  │  - History Queries               │ │
         │  │  - Goal Config Parser            │ │
         │  └──────────────────────────────────┘ │
         │  ┌──────────────────────────────────┐ │
         │  │   Dashboard Renderer             │ │
         │  │  - Progress Bar Generator        │ │
         │  │  - Pace Calculation              │ │
         │  │  - Image Generation (Pillow)     │ │
         │  └──────────────────────────────────┘ │
         └────────────────────────────────────────┘
                          │
                          ▼
                  ┌──────────────────┐
                  │  TRMNL Device    │
                  │  (800x480 e-ink) │
                  └──────────────────┘
```

### Technology Stack

- **Server Framework**: FastAPI (Python 3.11+)
- **HA Integration**: `websockets` library for WebSocket API
- **Image Generation**: Pillow (PIL)
- **Configuration**: Environment variables
- **Device Management**: SQLite (minimal - just device provisioning)

## Home Assistant Integration

### Goal Configuration via Labels

Goals are configured in Home Assistant using labels with a specific naming pattern and JSON metadata in the description field.

**Label Naming Convention**: `goal_<N>_per_week`

**Examples**:
- `goal_3_per_week` - For activities targeting 3 times per week
- `goal_4_per_week` - For activities targeting 4 times per week
- `goal_7_per_week` - For daily activities (7 times per week)

**Label Description** (JSON format):
```json
{
  "weekly_target": 4,
  "emoji": "💪",
  "sound": "chime.wav"
}
```

Where:
- `weekly_target` (required): Number of completions expected per week
- `emoji` (optional): Emoji to display with the goal
- `sound` (optional): Sound file to play on completion (future feature)

### Entity Types Supported

- `counter.*` - Increments each time a task is completed
- `input_boolean.*` - Toggle-based tracking (future support)
- `button.*` - Button press tracking (future support)

### Discovery Flow

1. **On Startup** (WebSocket API):
   - Connect to Home Assistant via WebSocket
   - Query label registry: `{"type": "config/label_registry/list"}`
   - Filter labels starting with `goal_`
   - Parse JSON from each label's description field
   - Query entity registry: `{"type": "config/entity_registry/list"}`
   - Find all entities that have any `goal_*` label assigned
   - Build mapping: entity → label → goal config

2. **When Rendering Dashboard** (WebSocket API):
   - For each goal entity, query history: `{"type": "history/history_during_period"}`
   - Filter state changes within current week (Sunday-Saturday)
   - Count increments: ignore resets (decreases), only count increases
   - Calculate progress and pace

### Example Configuration in Home Assistant

**Step 1: Create labels**
```
Settings → Labels → Create Label

Name: goal_4_per_week
Description: {"weekly_target": 4, "emoji": "💪"}
```

**Step 2: Create counter entities**
```yaml
# configuration.yaml
counter:
  gym_visits:
    name: "Gym Visits"
    icon: mdi:dumbbell
    initial: 0
    step: 1
```

**Step 3: Assign label to entity**
- Settings → Devices & Services → Entities
- Click on `counter.gym_visits`
- In the entity details, assign the `goal_4_per_week` label

### Week Definition

- **Week Start**: Sunday at 00:00:00
- **Week End**: Saturday at 23:59:59
- **Calculation**: Python `datetime.weekday()` with offset: `(weekday + 1) % 7`

## Data Model

### Goal Entity (Runtime Object)

```python
@dataclass
class Goal:
    """Represents a single habit/goal to track."""
    entity_id: str              # e.g., "counter.gym_visits"
    friendly_name: str          # From HA entity: e.g., "Gym Visits"
    weekly_target: int          # From label config: e.g., 4
    current_count: int          # Increments this week
    emoji: str | None           # Optional emoji from label config
    label_id: str               # e.g., "goal_4_per_week"

    # Calculated fields
    target_by_now: float        # Expected count by today
    status: str                 # "ahead", "on_track", "behind"
    days_left: int              # Days remaining in week
```

### Weekly Progress Calculation

```python
def calculate_target_by_now(weekly_target: int, day_of_week: int) -> float:
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

def calculate_status(current: int, target_by_now: float) -> str:
    """
    Determine if ahead, on track, or behind.

    Returns:
        "ahead" if current >= target_by_now + 0.5
        "on_track" if within ±0.5 of target
        "behind" if current < target_by_now - 0.5
    """
    diff = current - target_by_now
    if diff >= 0.5:
        return "ahead"
    elif diff <= -0.5:
        return "behind"
    else:
        return "on_track"
```

## Dashboard Rendering

### Layout Design (800x480 pixels)

```
┌────────────────────────────────────────────────────────────┐
│  Week 46: Nov 10-16, 2025     Day 4 of 7 (Wed)            │ Header (60px)
├────────────────────────────────────────────────────────────┤
│                                                            │
│  💪 Gym Visits                                             │
│  ▓▓▓|░░░  3/4   Target: 2.3  [AHEAD ⭐]                   │ Goal 1
│                                                            │
│  🦶 Toe Care                                               │
│  ▓▓|░  2/3   Target: 1.7  [ON TRACK ✓]                    │ Goal 2
│                                                            │
│  🧘 Meditation                                             │
│  ▓▓|▓░░░░  3/7   Target: 4.0  [BEHIND ⚠]                  │ Goal 3
│                                                            │
│  [Additional goals...]                                     │
│                                                            │
├────────────────────────────────────────────────────────────┤
│  Overall: 8/14 (57%)                Last update: 14:30    │ Footer (40px)
└────────────────────────────────────────────────────────────┘
```

### Visual Elements

**Progress Bar**:
- Length: 400px
- Height: 20px
- Filled blocks (`▓`): Completed count
- Target marker (`|`): Where you should be
- Empty blocks (`░`): Remaining to goal

**Status Indicators**:
- `⭐ AHEAD`: Current count ≥ target + 0.5
- `✓ ON TRACK`: Within ±0.5 of target
- `⚠ BEHIND`: Current count < target - 0.5

**Typography**:
- Header: 20pt bold
- Goal names: 18pt regular
- Progress text: 16pt regular
- Footer: 14pt

### Image Generation (Pillow)

```python
def render_dashboard(goals: list[Goal], width: int = 800, height: int = 480) -> Image:
    """
    Render the habit tracker dashboard.

    Returns:
        PIL Image in RGB mode (will be converted to monochrome for TRMNL)
    """
    image = Image.new('RGB', (width, height), 'white')
    draw = ImageDraw.Draw(image)

    # Draw header
    draw_header(draw, week_info)

    # Draw each goal
    y_offset = 80
    for goal in goals:
        draw_goal_row(draw, goal, y_offset)
        y_offset += 80

    # Draw footer
    draw_footer(draw, overall_stats)

    # Convert to monochrome
    return convert_to_monochrome(image)

def draw_goal_row(draw: ImageDraw, goal: Goal, y: int):
    """Draw a single goal with progress bar and status."""
    # Goal name with emoji
    name = f"{goal.emoji} {goal.friendly_name}" if goal.emoji else goal.friendly_name
    draw.text((50, y), name, fill='black', font=font_18pt)

    # Progress bar
    bar_y = y + 30
    draw_progress_bar(
        draw,
        x=50,
        y=bar_y,
        current=goal.current_count,
        target=goal.weekly_target,
        target_marker=goal.target_by_now
    )

    # Status text
    status_text = f"{goal.current_count}/{goal.weekly_target}   "
    status_text += f"Target: {goal.target_by_now:.1f}  "
    status_text += get_status_badge(goal.status)

    draw.text((470, bar_y), status_text, fill='black', font=font_16pt)

def draw_progress_bar(draw, x, y, current, target, target_marker):
    """
    Draw progress bar with target marker.

    Bar is divided into segments equal to target.
    Target marker shows expected progress by today.
    """
    bar_width = 400
    bar_height = 20
    segment_width = bar_width / target

    # Draw filled segments
    filled_width = int(current * segment_width)
    draw.rectangle([x, y, x + filled_width, y + bar_height], fill='black')

    # Draw empty segments
    draw.rectangle(
        [x + filled_width, y, x + bar_width, y + bar_height],
        outline='black',
        width=2
    )

    # Draw target marker
    marker_x = x + int(target_marker * segment_width)
    draw.line(
        [marker_x, y - 5, marker_x, y + bar_height + 5],
        fill='black',
        width=3
    )
```

## API Endpoints

### TRMNL BYOS Endpoints (Standard)

**GET /api/display**
- Returns current dashboard image URL
- Headers: `id` (device MAC), `Battery-Voltage`, `FW-Version`, etc.
- Response: `DisplayResponse` with image URL and refresh rate

**POST /api/setup**
- Device provisioning during first boot
- Headers: `id` (device MAC), `FW-Version`
- Response: `SetupResponse` with API key and welcome image

**POST /api/log**
- Device telemetry collection
- Headers: `id` (device MAC)
- Body: `DeviceLog` with battery, RSSI, etc.

### Custom Management Endpoints

**GET /**
- Simple status page showing server info

**GET /api/status**
- Server health check

**POST /api/refresh**
- Force dashboard re-render (for testing)

## Configuration

### Environment Variables

```bash
# Home Assistant connection (required)
HA_URL=http://192.168.1.128:8123
HA_API_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

# Server settings
SERVER_HOST=0.0.0.0
SERVER_PORT=8000

# Dashboard settings
DASHBOARD_REFRESH_INTERVAL=900  # 15 minutes (TRMNL polls this often)
CACHE_DURATION=300              # Cache rendered image for 5 minutes

# Week configuration
WEEK_START_DAY=sunday           # sunday or monday

# Logging
LOG_LEVEL=INFO
```

### Example .env file

```bash
HA_URL=http://homeassistant.local:8123
HA_API_KEY=your_long_lived_access_token_here
LOG_LEVEL=DEBUG
```

## Implementation Plan

### Phase 1: Core Functionality (MVP)

1. **Project Setup**
   - Initialize FastAPI project structure
   - Set up virtual environment and dependencies
   - Create basic configuration loading

2. **Home Assistant Integration**
   - WebSocket client for HA connection
   - Label discovery and parsing
   - Entity registry queries
   - History API queries

3. **Goal Tracking Logic**
   - Parse goal configuration from labels
   - Calculate weekly progress from history
   - Determine ahead/behind status
   - Handle week boundaries

4. **Dashboard Rendering**
   - Basic image generation with Pillow
   - Progress bar drawing
   - Target marker visualization
   - Status indicators

5. **TRMNL Integration**
   - Implement BYOS API endpoints
   - Device provisioning
   - Image serving
   - Refresh rate management

### Phase 2: Polish & Testing

1. **Error Handling**
   - HA connection failures
   - Invalid label configurations
   - Missing entities
   - Graceful degradation

2. **Testing**
   - Unit tests for calculations
   - Integration tests with mock HA
   - Manual testing with real TRMNL device

3. **Documentation**
   - Setup guide
   - Configuration examples
   - Troubleshooting

### Phase 3: Future Enhancements

1. **Multiple Dashboard Types**
   - Calendar view
   - Weather display
   - Generic data dashboards

2. **Advanced Features**
   - Historical trends
   - Streak tracking
   - Configurable visual themes
   - Web UI for configuration

## Project Structure

```
trmnl-ha-dash/
├── app/
│   ├── __init__.py
│   ├── main.py                  # FastAPI app and endpoints
│   ├── config.py                # Configuration loading
│   ├── models.py                # Pydantic models
│   │
│   ├── ha/
│   │   ├── __init__.py
│   │   ├── client.py            # WebSocket client
│   │   ├── discovery.py         # Label/entity discovery
│   │   ├── history.py           # History queries
│   │   └── models.py            # HA data models
│   │
│   ├── dashboard/
│   │   ├── __init__.py
│   │   ├── base.py              # Base Dashboard class
│   │   ├── habit_tracker.py    # Habit tracker implementation
│   │   ├── renderer.py          # Image generation
│   │   └── calculator.py        # Progress calculations
│   │
│   └── trmnl/
│       ├── __init__.py
│       ├── models.py            # TRMNL API models
│       └── database.py          # Device management (SQLite)
│
├── static/
│   └── images/                  # Generated images
│
├── tests/
│   ├── test_calculator.py
│   ├── test_discovery.py
│   └── test_renderer.py
│
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── .env.example
├── README.md
└── SPEC.md (this file)
```

## Dependencies

```
# requirements.txt
fastapi>=0.104.0
uvicorn>=0.24.0
websockets>=12.0
pillow>=10.1.0
pydantic>=2.4.0
pydantic-settings>=2.0.0
aiosqlite>=0.19.0
python-dotenv>=1.0.0
```

## Deployment

### Docker Deployment (Recommended)

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    imagemagick \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Docker Compose

```yaml
version: '3.8'

services:
  trmnl-ha-dash:
    build: .
    ports:
      - "8000:8000"
    environment:
      - HA_URL=${HA_URL}
      - HA_API_KEY=${HA_API_KEY}
    volumes:
      - ./data:/data
      - ./static:/app/static
    restart: unless-stopped
```

## Testing Strategy

### Unit Tests
- Goal calculation logic (target by now, status determination)
- Label parsing and validation
- Week boundary calculations
- Progress bar positioning math

### Integration Tests
- HA WebSocket connection and queries
- History data parsing
- Image generation pipeline
- TRMNL API endpoints

### Manual Testing
- Create test counters in HA
- Assign labels
- Increment counters at different times
- Verify dashboard updates correctly
- Test week rollover

## Security Considerations

1. **HA Token Storage**: Store in environment variables, never commit
2. **API Authentication**: Reuse TRMNL device MAC + API key auth
3. **Input Validation**: Validate all JSON from label descriptions
4. **Error Messages**: Don't expose internal details in API responses
5. **Rate Limiting**: Consider limiting HA API calls if needed

## Performance Considerations

1. **Image Caching**: Cache rendered images, only re-render on data changes
2. **HA Connection**: Reuse WebSocket connection, reconnect on failure
3. **History Queries**: Query only current week, not full history
4. **Batch Queries**: Query all entities at once, not individually

## Error Handling

### HA Connection Failures
- Retry connection with exponential backoff
- Return cached image if HA unavailable
- Log errors but continue serving

### Invalid Configurations
- Skip entities with invalid label JSON
- Log warnings for malformed configs
- Display only valid goals

### Missing Data
- Handle entities with no history gracefully
- Show 0/N for goals with no completions
- Display "No data" for disconnected entities

---

**Document Version**: 1.0
**Last Updated**: 2025-11-16
**Status**: Ready for Implementation
