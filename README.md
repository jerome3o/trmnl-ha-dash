# TRMNL Home Assistant Habit Tracker

A BYOS (Bring Your Own Server) TRMNL server that displays habit tracking progress from Home Assistant on an e-ink display.

![Dashboard Example](docs/dashboard-example.png)

## Features

- 🎯 **Visual Progress Tracking**: Track weekly goals with progress bars
- ⚡ **Real-time Status**: Shows if you're ahead, on track, or behind schedule
- 🏠 **Home Assistant Integration**: Seamless WebSocket integration
- 🖼️ **E-ink Optimized**: High contrast, monochrome rendering
- 🐳 **Docker Ready**: Easy deployment with Docker Compose
- 📊 **Target Markers**: Visual indicators showing expected progress by today

## Quick Start

### Prerequisites

- Home Assistant instance with a long-lived access token
- TRMNL e-ink display device
- Docker and Docker Compose (recommended) or Python 3.11+

### Setup with Docker (Recommended)

1. **Clone the repository**:
   ```bash
   git clone https://github.com/jerome3o/trmnl-ha-dash.git
   cd trmnl-ha-dash
   ```

2. **Create `.env` file**:
   ```bash
   cp .env.example .env
   # Edit .env with your settings
   ```

3. **Configure environment variables**:
   ```bash
   # Required
   HA_URL=http://homeassistant.local:8123
   HA_API_KEY=your_long_lived_access_token

   # Optional
   SERVER_PORT=8000
   LOG_LEVEL=INFO
   ```

4. **Start the server**:
   ```bash
   docker-compose up -d
   ```

5. **Check status**:
   ```bash
   curl http://localhost:8000/status
   ```

### Setup without Docker

1. **Install dependencies**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Set environment variables** (create `.env` file as above)

3. **Run the server**:
   ```bash
   python -m app.main
   ```

## Home Assistant Configuration

### 1. Create Goal Labels

In Home Assistant, create labels for your weekly goals:

**Settings → Labels → Create Label**

- **Name**: `goal_4_per_week` (for 4 times per week target)
- **Description**: `{"weekly_target": 4, "emoji": "💪"}`

You can create labels for any frequency:
- `goal_3_per_week` - Three times per week
- `goal_7_per_week` - Daily (seven times per week)
- etc.

### 2. Create Counter Entities

Create counter entities to track completions:

```yaml
# configuration.yaml
counter:
  gym_visits:
    name: "Gym Visits"
    icon: mdi:dumbbell
    initial: 0
    step: 1

  toe_care:
    name: "Toe Care"
    icon: mdi:foot-print
    initial: 0
    step: 1
```

### 3. Assign Labels to Entities

1. Go to **Settings → Devices & Services → Entities**
2. Click on your counter entity (e.g., `counter.gym_visits`)
3. Assign the appropriate goal label (e.g., `goal_4_per_week`)

### 4. Create Automation to Increment Counters

Create automations to increment counters when you press buttons:

```yaml
# automations.yaml
- alias: "Increment Gym Counter"
  trigger:
    - platform: state
      entity_id: input_button.gym_button
  action:
    - service: counter.increment
      target:
        entity_id: counter.gym_visits
```

## TRMNL Device Setup

1. Configure your TRMNL device to point to your server:
   - URL: `http://YOUR_SERVER_IP:8000`

2. The device will auto-provision on first connection

3. Dashboard updates every 15 minutes (configurable via `DASHBOARD_REFRESH_INTERVAL`)

## Dashboard Features

### Progress Bars with Target Markers

Each goal shows:
- **Progress bar**: Segmented by weekly target
- **Target marker** (`|`): Shows where you should be by today
- **Current count**: e.g., "3/4"
- **Expected target**: e.g., "Target: 2.3"
- **Status**:
  - ⭐ **AHEAD** - You're doing great!
  - ✓ **ON TRACK** - Right on schedule
  - ⚠ **BEHIND** - Time to catch up

### Week Tracking

- Weeks run Sunday to Saturday
- Progress resets each Sunday
- Uses Home Assistant's history API (no local database needed for tracking)

## API Endpoints

- `GET /api/display` - TRMNL device endpoint for dashboard
- `POST /api/setup` - Device provisioning
- `POST /api/log` - Device telemetry
- `POST /api/refresh` - Force dashboard refresh (clear cache)
- `GET /status` - Server health check

## Configuration Options

All settings can be configured via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `HA_URL` | - | Home Assistant URL (required) |
| `HA_API_KEY` | - | Long-lived access token (required) |
| `SERVER_HOST` | `0.0.0.0` | Server bind address |
| `SERVER_PORT` | `8000` | Server port |
| `DASHBOARD_REFRESH_INTERVAL` | `900` | TRMNL refresh interval (seconds) |
| `CACHE_DURATION` | `300` | Dashboard cache duration (seconds) |
| `LOG_LEVEL` | `INFO` | Logging level |

## Development

### Project Structure

```
trmnl-ha-dash/
├── app/
│   ├── ha/              # Home Assistant integration
│   │   ├── client.py    # WebSocket client
│   │   ├── discovery.py # Goal discovery
│   │   └── history.py   # Progress calculation
│   ├── dashboard/       # Dashboard rendering
│   │   └── renderer.py  # Image generation
│   ├── trmnl/          # TRMNL device management
│   │   ├── models.py    # API models
│   │   └── database.py  # Device database
│   ├── config.py       # Configuration
│   └── main.py         # FastAPI application
├── static/images/      # Generated dashboard images
├── data/              # SQLite database
└── SPEC.md           # Detailed specification
```

### Running Tests

```bash
# Run individual demos
python -m app.ha.discovery    # Demo 1: Discover goals
python -m app.ha.history      # Demo 2: Calculate progress
python -m app.dashboard.renderer  # Demo 3: Render dashboard
```

## Troubleshooting

### Dashboard not updating

1. Check server logs: `docker-compose logs -f`
2. Verify HA connection: `curl http://localhost:8000/status`
3. Force refresh: `curl -X POST http://localhost:8000/api/refresh`

### No goals found

1. Verify labels start with `goal_`
2. Check label description is valid JSON
3. Ensure labels are assigned to counter entities
4. Check server logs for discovery errors

### Connection issues

1. Verify `HA_URL` and `HA_API_KEY` in `.env`
2. Test HA connection: `curl -H "Authorization: Bearer $HA_API_KEY" $HA_URL/api/`
3. Check network connectivity between server and HA

## Docker Management

```bash
# Start server
docker-compose up -d

# View logs
docker-compose logs -f

# Restart server
docker-compose restart

# Stop server
docker-compose down

# Rebuild after code changes
docker-compose up -d --build
```

## Production Deployment

### Reverse Proxy (nginx)

```nginx
server {
    listen 80;
    server_name trmnl.yourdomain.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

### Systemd Service (without Docker)

```ini
[Unit]
Description=TRMNL HA Dashboard
After=network.target

[Service]
Type=simple
User=YOUR_USER
WorkingDirectory=/path/to/trmnl-ha-dash
Environment="PATH=/path/to/trmnl-ha-dash/venv/bin"
ExecStart=/path/to/trmnl-ha-dash/venv/bin/python -m app.main
Restart=always

[Install]
WantedBy=multi-user.target
```

## Contributing

See [SPEC.md](SPEC.md) for detailed technical specification.

## License

MIT License - See LICENSE file for details

## Acknowledgments

- Built with [FastAPI](https://fastapi.tiangolo.com/)
- Uses [Home Assistant](https://www.home-assistant.io/) for data
- Designed for [TRMNL](https://usetrmnl.com/) e-ink displays
