#!/usr/bin/env python3
"""Test Home Assistant History API to track counter increments."""

import json
import os
import requests
from datetime import datetime, timedelta


def test_history_api():
    """Query HA history for counter.test_counter."""

    ha_url = os.getenv("HA_URL", "http://192.168.1.128:8123/")
    ha_token = os.getenv("HA_API_KEY")

    # Remove trailing slash
    if ha_url.endswith("/"):
        ha_url = ha_url[:-1]

    headers = {
        "Authorization": f"Bearer {ha_token}",
        "Content-Type": "application/json"
    }

    # Get history for the last 7 days
    end_time = datetime.now()
    start_time = end_time - timedelta(days=7)

    # Format: /api/history/period/2025-11-10T00:00:00+00:00?filter_entity_id=counter.test_counter
    start_timestamp = start_time.isoformat()

    url = f"{ha_url}/api/history/period/{start_timestamp}"
    params = {
        "filter_entity_id": "counter.test_counter",
        "minimal_response": "false",
        "significant_changes_only": "false"
    }

    print(f"Querying: {url}")
    print(f"Params: {params}\n")

    response = requests.get(url, headers=headers, params=params)

    if response.status_code != 200:
        print(f"Error: {response.status_code}")
        print(response.text)
        return

    history = response.json()

    print(f"Response type: {type(history)}")
    print(f"Number of entity groups: {len(history)}\n")

    if not history:
        print("No history data found!")
        return

    # History returns array of arrays, one per entity
    for entity_history in history:
        if not entity_history:
            continue

        print(f"Found {len(entity_history)} state changes for counter.test_counter:\n")

        # Show each state change
        for i, state in enumerate(entity_history):
            print(f"[{i+1}] State: {state.get('state')}")
            print(f"    Last Changed: {state.get('last_changed')}")
            print(f"    Last Updated: {state.get('last_updated')}")

            # Show attributes if present
            attrs = state.get('attributes', {})
            if attrs:
                print(f"    Attributes: {json.dumps(attrs, indent=6)}")
            print()

        # Calculate increments
        print("\n" + "="*60)
        print("ANALYZING INCREMENTS:")
        print("="*60 + "\n")

        increments = []
        prev_state = None

        for state in entity_history:
            current_value = state.get('state')
            timestamp = state.get('last_changed')

            # Try to parse state as integer
            try:
                current_int = int(current_value)

                if prev_state is not None:
                    prev_int = int(prev_state.get('state'))

                    # Check if it increased
                    if current_int > prev_int:
                        increment_amount = current_int - prev_int
                        increments.append({
                            'timestamp': timestamp,
                            'from': prev_int,
                            'to': current_int,
                            'increment': increment_amount
                        })
                        print(f"INCREMENT: {prev_int} → {current_int} (+{increment_amount})")
                        print(f"  Time: {timestamp}\n")

                prev_state = state

            except (ValueError, TypeError):
                print(f"Non-numeric state: {current_value}")
                continue

        print(f"\nTotal increments detected: {len(increments)}")

        # Group by day
        if increments:
            print("\n" + "="*60)
            print("INCREMENTS BY DAY:")
            print("="*60 + "\n")

            by_day = {}
            for inc in increments:
                # Parse ISO timestamp
                dt = datetime.fromisoformat(inc['timestamp'].replace('Z', '+00:00'))
                day = dt.date().isoformat()

                if day not in by_day:
                    by_day[day] = []
                by_day[day].append(inc)

            for day in sorted(by_day.keys()):
                print(f"{day}: {len(by_day[day])} increment(s)")
                for inc in by_day[day]:
                    dt = datetime.fromisoformat(inc['timestamp'].replace('Z', '+00:00'))
                    print(f"  - {dt.strftime('%H:%M:%S')}: +{inc['increment']}")


if __name__ == "__main__":
    test_history_api()
