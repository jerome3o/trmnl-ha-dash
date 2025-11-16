"""Main FastAPI application."""

import logging
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, Header, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import settings
from .dashboard.renderer import DashboardRenderer
from .ha.client import HAClient
from .ha.discovery import GoalDiscovery
from .ha.history import ProgressCalculator
from .trmnl.database import (
    DeviceDatabase,
    generate_api_key,
    generate_friendly_id,
)
from .trmnl.models import Device, DeviceLog, DisplayResponse, SetupResponse

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="TRMNL Home Assistant Dashboard",
    description="Habit tracker dashboard for TRMNL e-ink displays",
    version="1.0.0",
)

# Initialize components
db = DeviceDatabase()
renderer = DashboardRenderer()

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

def get_base_url(request: Request) -> str:
    """Get base URL for serving images."""
    return f"{request.url.scheme}://{request.headers.get('host', 'localhost')}"


async def render_dashboard() -> tuple[str, str]:
    """
    Render fresh dashboard from Home Assistant data.

    Returns:
        Tuple of (filename, file_path)
    """
    logger.info("Rendering dashboard with fresh data from HA...")

    # Connect to HA and render dashboard
    client = HAClient(settings.ha_url, settings.ha_api_key)

    try:
        await client.connect()

        # Discover goals
        discovery = GoalDiscovery(client)
        goals = await discovery.discover_goals()

        if not goals:
            logger.warning("No goals found in Home Assistant")
            # TODO: Return a "no goals" image
            return "no-goals", "static/images/no-goals.png"

        # Calculate progress
        calculator = ProgressCalculator(client)
        goals = await calculator.calculate_progress(goals)

        # Render dashboard
        week_start, week_end = calculator._get_current_week()
        filename, file_path = renderer.render(goals, week_start, week_end)

        return filename, file_path

    finally:
        await client.disconnect()


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "TRMNL Home Assistant Dashboard",
        "version": "1.0.0",
        "endpoints": {
            "display": "/api/display",
            "setup": "/api/setup",
            "log": "/api/log",
            "status": "/status",
        },
    }


@app.get("/status")
async def status():
    """Server status endpoint."""
    return {
        "status": "running",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat(),
        "ha_url": settings.ha_url,
        "ha_connected": bool(settings.ha_api_key),
    }


@app.get("/api/display", response_model=DisplayResponse)
async def display_endpoint(
    request: Request,
    id: str = Header(..., description="Device MAC address"),
    battery_voltage: Optional[float] = Header(None, alias="Battery-Voltage"),
    fw_version: Optional[str] = Header(None, alias="FW-Version"),
):
    """
    Primary device endpoint for screen content delivery.

    This is called by the TRMNL device to fetch the current dashboard.
    """
    logger.info(f"Display request from device: {id}")

    # Update device status
    device = db.get_device(id)
    if device:
        db.update_device_status(
            id,
            last_seen=datetime.utcnow(),
            firmware_version=fw_version,
            battery_voltage=battery_voltage,
        )

    # Render fresh dashboard
    filename, file_path = await render_dashboard()

    # Build image URL
    base_url = get_base_url(request)
    image_url = f"{base_url}/static/images/{filename}.png"

    logger.info(f"Serving dashboard: {filename}")

    return DisplayResponse(
        status=0,
        image_url=image_url,
        filename=filename,
        refresh_rate=settings.dashboard_refresh_interval,
        update_firmware=False,
        firmware_url=None,
        reset_firmware=False,
        special_function="sleep",
        image_url_timeout=30,
    )


@app.post("/api/setup", response_model=SetupResponse)
async def setup_endpoint(
    request: Request,
    id: str = Header(..., description="Device MAC address"),
    fw_version: Optional[str] = Header(None, alias="FW-Version"),
):
    """
    Device provisioning during first boot.

    Creates new device credentials or returns existing ones.
    """
    logger.info(f"Setup request from device: {id}")

    # Check if device already exists
    existing_device = db.get_device(id)
    if existing_device:
        logger.info(f"Device already exists: {existing_device.friendly_id}")

        # Return existing credentials with fresh dashboard
        base_url = get_base_url(request)
        filename, _ = await render_dashboard()
        image_url = f"{base_url}/static/images/{filename}.png"

        return SetupResponse(
            status=200,
            api_key=existing_device.api_key,
            friendly_id=existing_device.friendly_id,
            image_url=image_url,
            message="Welcome back to your TRMNL HA Dashboard",
        )

    # Create new device
    api_key = generate_api_key()
    friendly_id = generate_friendly_id()

    new_device = Device(
        mac_address=id,
        api_key=api_key,
        friendly_id=friendly_id,
        created_at=datetime.utcnow(),
        firmware_version=fw_version,
    )

    db.create_device(new_device)

    # Return setup response with fresh dashboard
    base_url = get_base_url(request)
    filename, _ = await render_dashboard()
    image_url = f"{base_url}/static/images/{filename}.png"

    logger.info(f"Device provisioned: {friendly_id} ({id})")

    return SetupResponse(
        status=200,
        api_key=api_key,
        friendly_id=friendly_id,
        image_url=image_url,
        message="Welcome to your TRMNL HA Dashboard",
    )


@app.post("/api/log")
async def log_endpoint(
    log_data: DeviceLog,
    id: str = Header(..., description="Device MAC address"),
):
    """
    Device telemetry and logging endpoint.

    Receives logs from the device (battery, WiFi, etc.)
    """
    logger.debug(f"Log from device {id}: {log_data.dict(exclude_none=True)}")

    # Update device status with telemetry
    db.update_device_status(
        id,
        last_seen=datetime.utcnow(),
        firmware_version=log_data.firmware_version,
        battery_voltage=log_data.battery_voltage,
    )

    return {"status": "success", "message": "Log data received"}


@app.post("/api/refresh")
async def refresh_endpoint():
    """
    Render dashboard immediately (for testing).

    Note: Cache is disabled, so every request gets fresh data anyway.
    This endpoint is kept for backward compatibility.
    """
    logger.info("Manual refresh requested")
    filename, file_path = await render_dashboard()

    return {
        "status": "success",
        "message": "Dashboard rendered with fresh data",
        "filename": filename,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host=settings.server_host,
        port=settings.server_port,
        log_level=settings.log_level.lower(),
    )
