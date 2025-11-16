"""TRMNL API models."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class DisplayResponse(BaseModel):
    """Response for /api/display endpoint."""

    status: int = 0
    image_url: str
    filename: str
    refresh_rate: int = 900  # 15 minutes default
    update_firmware: bool = False
    firmware_url: Optional[str] = None
    reset_firmware: bool = False
    special_function: str = "sleep"
    image_url_timeout: int = 30


class SetupResponse(BaseModel):
    """Response for /api/setup endpoint."""

    status: int = 200
    api_key: str
    friendly_id: str
    image_url: str
    message: str = "Welcome to your TRMNL HA Dashboard"


class DeviceLog(BaseModel):
    """Device telemetry log from /api/log endpoint."""

    battery_voltage: Optional[float] = None
    heap_free: Optional[int] = None
    rssi: Optional[int] = None
    wake_reason: Optional[str] = None
    sleep_duration: Optional[int] = None
    firmware_version: Optional[str] = None
    uptime: Optional[int] = None
    wifi_connect_time: Optional[int] = None
    image_download_time: Optional[int] = None
    display_render_time: Optional[int] = None


class Device(BaseModel):
    """Device record."""

    mac_address: str
    api_key: str
    friendly_id: str
    created_at: datetime
    last_seen: Optional[datetime] = None
    firmware_version: Optional[str] = None
    battery_voltage: Optional[float] = None
