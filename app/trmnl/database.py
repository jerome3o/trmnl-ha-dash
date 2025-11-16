"""Simple SQLite database for device management."""

import logging
import secrets
import sqlite3
import string
from datetime import datetime
from pathlib import Path
from typing import Optional

from .models import Device

logger = logging.getLogger(__name__)


class DeviceDatabase:
    """Simple SQLite database for TRMNL devices."""

    def __init__(self, db_path: str = "data/devices.db"):
        """Initialize database."""
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        """Create database tables if they don't exist."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS devices (
                    mac_address TEXT PRIMARY KEY,
                    api_key TEXT NOT NULL,
                    friendly_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    last_seen TEXT,
                    firmware_version TEXT,
                    battery_voltage REAL
                )
            """)
            conn.commit()
        logger.info(f"Database initialized at {self.db_path}")

    def get_device(self, mac_address: str) -> Optional[Device]:
        """Get device by MAC address."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM devices WHERE mac_address = ?", (mac_address,)
            )
            row = cursor.fetchone()

            if not row:
                return None

            return Device(
                mac_address=row["mac_address"],
                api_key=row["api_key"],
                friendly_id=row["friendly_id"],
                created_at=datetime.fromisoformat(row["created_at"]),
                last_seen=datetime.fromisoformat(row["last_seen"])
                if row["last_seen"]
                else None,
                firmware_version=row["firmware_version"],
                battery_voltage=row["battery_voltage"],
            )

    def create_device(self, device: Device):
        """Create new device."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO devices (mac_address, api_key, friendly_id, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (
                    device.mac_address,
                    device.api_key,
                    device.friendly_id,
                    device.created_at.isoformat(),
                ),
            )
            conn.commit()
        logger.info(f"Created device: {device.friendly_id} ({device.mac_address})")

    def update_device_status(
        self,
        mac_address: str,
        last_seen: Optional[datetime] = None,
        firmware_version: Optional[str] = None,
        battery_voltage: Optional[float] = None,
    ):
        """Update device status."""
        updates = []
        params = []

        if last_seen:
            updates.append("last_seen = ?")
            params.append(last_seen.isoformat())

        if firmware_version:
            updates.append("firmware_version = ?")
            params.append(firmware_version)

        if battery_voltage:
            updates.append("battery_voltage = ?")
            params.append(battery_voltage)

        if not updates:
            return

        params.append(mac_address)

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                f"UPDATE devices SET {', '.join(updates)} WHERE mac_address = ?",
                params,
            )
            conn.commit()


def generate_api_key() -> str:
    """Generate secure API key."""
    return "".join(
        secrets.choice(string.ascii_letters + string.digits) for _ in range(32)
    )


def generate_friendly_id() -> str:
    """Generate short friendly device ID."""
    return "".join(
        secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6)
    )
