"""
Disaster feed tool — fetches live disaster events from NASA EONET
(Earth Observatory Natural Event Tracker). Free, no API key required.
Provides real-world crisis intelligence for active natural disasters.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

import httpx

from app.tools.registry import tool_registry

logger = logging.getLogger(__name__)

_HTTP_TIMEOUT = 10.0
_EONET_BASE = "https://eonet.gsfc.nasa.gov/api/v3/events"

# Map EONET category IDs to human-readable crisis types
_CATEGORY_MAP = {
    "wildfires": "Wildfire",
    "severeStorms": "Severe Storm",
    "volcanoes": "Volcanic Activity",
    "floods": "Flood",
    "earthquakes": "Earthquake",
    "drought": "Drought",
    "landslides": "Landslide",
    "seaLakeIce": "Sea/Lake Ice",
    "snow": "Snow",
    "dustHaze": "Dust/Haze",
    "tempExtremes": "Temperature Extreme",
}

# Bounding box for South Asia (India + neighbours)
_SOUTH_ASIA_BBOX = (60.0, 5.0, 100.0, 40.0)  # west, south, east, north


def _is_in_region(geometry: list[dict], bbox: tuple[float, float, float, float]) -> bool:
    """Check if any event geometry point falls within a bounding box."""
    west, south, east, north = bbox
    for geo in geometry:
        coords = geo.get("coordinates", [])
        if coords and len(coords) >= 2:
            lon, lat = coords[0], coords[1]
            if west <= lon <= east and south <= lat <= north:
                return True
    return False


async def disaster_feed(
    region: str = "south_asia",
    category: Optional[str] = None,
    limit: int = 10,
    status: str = "open",
) -> dict[str, Any]:
    """Fetch active disaster events from NASA EONET.

    Args:
        region: Geographic filter — 'south_asia' (default), 'global', or 'all'.
        category: Optional category filter — wildfires, severeStorms, floods,
                  volcanoes, earthquakes, landslides, drought.
        limit: Max results (1-20, default 10).
        status: Event status — 'open' (active) or 'closed' (past).
    """
    limit = max(1, min(20, limit))

    params: dict[str, str] = {
        "status": status,
        "limit": str(limit * 3 if region == "south_asia" else limit),
    }
    if category:
        params["category"] = category

    try:
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
            resp = await client.get(_EONET_BASE, params=params)
            resp.raise_for_status()
            data = resp.json()
    except (httpx.HTTPError, httpx.TimeoutException) as exc:
        logger.warning(f"[disaster_feed] NASA EONET API failed: {exc}")
        return {
            "error": f"NASA EONET API unavailable: {exc}",
            "source": "NASA EONET",
            "events": [],
        }

    events = []
    for ev in data.get("events", []):
        geometry = ev.get("geometry", [])
        categories = ev.get("categories", [])

        # Filter by region if south_asia
        if region == "south_asia" and not _is_in_region(geometry, _SOUTH_ASIA_BBOX):
            continue

        # Extract latest coordinates
        latest_coords = None
        latest_date = None
        if geometry:
            latest = geometry[-1]
            latest_coords = latest.get("coordinates")
            latest_date = latest.get("date")

        events.append({
            "id": ev.get("id"),
            "title": ev.get("title", "Unknown"),
            "categories": [
                _CATEGORY_MAP.get(c.get("id"), c.get("title", "Unknown"))
                for c in categories
            ],
            "coordinates": latest_coords,
            "date": latest_date,
            "sources": [
                {"id": s.get("id"), "url": s.get("url")}
                for s in ev.get("sources", [])[:2]
            ],
        })

        if len(events) >= limit:
            break

    return {
        "region": region,
        "status": status,
        "event_count": len(events),
        "events": events,
        "source": "NASA EONET (Earth Observatory Natural Event Tracker)",
    }


# ── Register tool ────────────────────────────────────────

tool_registry.register(
    name="disaster_feed",
    description=(
        "Fetch live disaster events from NASA's Earth Observatory Natural Event "
        "Tracker (EONET). Returns active disasters worldwide or filtered to South Asia "
        "including type (Wildfire, Flood, Cyclone, Earthquake), coordinates, and dates. "
        "Use this to understand the current disaster landscape and identify active "
        "emergencies affecting the region. Free, no API key required."
    ),
    parameters={
        "type": "object",
        "properties": {
            "region": {
                "type": "string",
                "description": "Geographic filter: 'south_asia' (India+neighbours, default), 'global' (all events)",
            },
            "category": {
                "type": "string",
                "description": "Filter by category: wildfires, severeStorms, floods, volcanoes, earthquakes, landslides, drought",
            },
            "limit": {
                "type": "integer",
                "description": "Max results (1-20, default 10)",
            },
            "status": {
                "type": "string",
                "description": "Event status: 'open' (active, default) or 'closed' (past)",
            },
        },
        "required": [],
    },
    handler=disaster_feed,
)
