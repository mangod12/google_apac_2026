"""
Route tool — real alternative-route lookup and nearest airport/port finder.

Uses OpenRouteService (free, 2000 req/day) for driving routes with road avoidance,
and a static dataset of Indian airports + ports for multi-modal fallback options.
"""

from __future__ import annotations

import logging
import math
from typing import Any, Optional

import httpx

from app.tools.registry import tool_registry

logger = logging.getLogger(__name__)

_HTTP_TIMEOUT = 12.0

# ── Static transport hub data (lat, lon, name, IATA/code, runway/berth capacity) ──

AIRPORTS: list[dict[str, Any]] = [
    {"name": "Biju Patnaik International Airport", "code": "BBI", "city": "Bhubaneswar", "lat": 20.2444, "lon": 85.8178, "runway_m": 2743, "military": False},
    {"name": "Netaji Subhas Chandra Bose Airport", "code": "CCU", "city": "Kolkata", "lat": 22.6547, "lon": 88.4467, "runway_m": 3627, "military": False},
    {"name": "Chennai International Airport", "code": "MAA", "city": "Chennai", "lat": 12.9941, "lon": 80.1709, "runway_m": 3658, "military": False},
    {"name": "Sardar Vallabhbhai Patel Airport", "code": "AMD", "city": "Ahmedabad", "lat": 23.0772, "lon": 72.6347, "runway_m": 3505, "military": False},
    {"name": "Jaipur International Airport", "code": "JAI", "city": "Jaipur", "lat": 26.8242, "lon": 75.8122, "runway_m": 3440, "military": False},
    {"name": "Jolly Grant Airport", "code": "DED", "city": "Dehradun", "lat": 30.1897, "lon": 78.1803, "runway_m": 2140, "military": False},
    {"name": "Gauchar Airstrip", "code": "GCR", "city": "Gauchar", "lat": 30.2667, "lon": 79.2333, "runway_m": 800, "military": True},
    {"name": "Chhatrapati Shivaji Maharaj Airport", "code": "BOM", "city": "Mumbai", "lat": 19.0896, "lon": 72.8656, "runway_m": 3660, "military": False},
    {"name": "Kempegowda International Airport", "code": "BLR", "city": "Bangalore", "lat": 13.1986, "lon": 77.7066, "runway_m": 4000, "military": False},
    {"name": "Rajiv Gandhi International Airport", "code": "HYD", "city": "Hyderabad", "lat": 17.2403, "lon": 78.4294, "runway_m": 4260, "military": False},
    {"name": "Indira Gandhi International Airport", "code": "DEL", "city": "Delhi", "lat": 28.5562, "lon": 77.1000, "runway_m": 4430, "military": False},
    {"name": "Lokpriya Gopinath Bordoloi Airport", "code": "GAU", "city": "Guwahati", "lat": 26.1061, "lon": 91.5856, "runway_m": 2750, "military": False},
    {"name": "Jay Prakash Narayan Airport", "code": "PAT", "city": "Patna", "lat": 25.5913, "lon": 85.0880, "runway_m": 2286, "military": False},
    {"name": "Cochin International Airport", "code": "COK", "city": "Kochi", "lat": 10.1520, "lon": 76.4019, "runway_m": 3400, "military": False},
    {"name": "Veer Savarkar International Airport", "code": "IXZ", "city": "Port Blair", "lat": 11.6412, "lon": 92.7297, "runway_m": 3108, "military": False},
    {"name": "Visakhapatnam Airport", "code": "VTZ", "city": "Visakhapatnam", "lat": 17.7212, "lon": 83.2245, "runway_m": 2286, "military": False},
    {"name": "Srinagar Airport", "code": "SXR", "city": "Srinagar", "lat": 33.9871, "lon": 74.7742, "runway_m": 3735, "military": True},
    {"name": "Leh Kushok Bakula Rimpochee Airport", "code": "IXL", "city": "Leh", "lat": 34.1359, "lon": 77.5465, "runway_m": 3048, "military": True},
    # IAF bases used for disaster airlift
    {"name": "IAF Tambaram", "code": "TBM", "city": "Chennai", "lat": 12.9072, "lon": 80.1189, "runway_m": 2750, "military": True},
    {"name": "IAF Kalaikunda", "code": "KLK", "city": "Kolkata", "lat": 22.3395, "lon": 87.2145, "runway_m": 2745, "military": True},
    {"name": "IAF Yelahanka", "code": "YLK", "city": "Bangalore", "lat": 13.1353, "lon": 77.6061, "runway_m": 2750, "military": True},
]

PORTS: list[dict[str, Any]] = [
    {"name": "Paradip Port", "city": "Paradip", "state": "Odisha", "lat": 20.2644, "lon": 86.6100, "type": "major", "capacity_mt_yr": 130},
    {"name": "Visakhapatnam Port", "city": "Visakhapatnam", "state": "Andhra Pradesh", "lat": 17.6868, "lon": 83.2985, "type": "major", "capacity_mt_yr": 75},
    {"name": "Chennai Port", "city": "Chennai", "state": "Tamil Nadu", "lat": 13.0937, "lon": 80.2971, "type": "major", "capacity_mt_yr": 61},
    {"name": "Jawaharlal Nehru Port (JNPT)", "city": "Navi Mumbai", "state": "Maharashtra", "lat": 18.9500, "lon": 72.9500, "type": "major", "capacity_mt_yr": 86},
    {"name": "Mumbai Port", "city": "Mumbai", "state": "Maharashtra", "lat": 18.9322, "lon": 72.8414, "type": "major", "capacity_mt_yr": 63},
    {"name": "Kandla Port (Deendayal)", "city": "Kandla", "state": "Gujarat", "lat": 23.0333, "lon": 70.2167, "type": "major", "capacity_mt_yr": 132},
    {"name": "Mundra Port", "city": "Mundra", "state": "Gujarat", "lat": 22.7394, "lon": 69.7250, "type": "major", "capacity_mt_yr": 210},
    {"name": "Kochi Port", "city": "Kochi", "state": "Kerala", "lat": 9.9680, "lon": 76.2673, "type": "major", "capacity_mt_yr": 32},
    {"name": "Haldia Dock Complex", "city": "Haldia", "state": "West Bengal", "lat": 22.0260, "lon": 88.0589, "type": "major", "capacity_mt_yr": 43},
    {"name": "Kolkata Port (Syama Prasad Mookerjee)", "city": "Kolkata", "state": "West Bengal", "lat": 22.5480, "lon": 88.3322, "type": "major", "capacity_mt_yr": 15},
    {"name": "New Mangalore Port", "city": "Mangalore", "state": "Karnataka", "lat": 12.9198, "lon": 74.8101, "type": "major", "capacity_mt_yr": 45},
    {"name": "Tuticorin Port (V.O. Chidambaranar)", "city": "Tuticorin", "state": "Tamil Nadu", "lat": 8.7642, "lon": 78.1848, "type": "major", "capacity_mt_yr": 38},
    {"name": "Gopalpur Port", "city": "Gopalpur", "state": "Odisha", "lat": 19.2583, "lon": 84.9028, "type": "minor", "capacity_mt_yr": 10},
]


# ── Haversine distance ──────────────────────────────────────

def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in km between two lat/lon points."""
    R = 6371.0
    rlat1, rlat2 = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(rlat1) * math.cos(rlat2) * math.sin(dlon / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ── City coordinate resolver (reuse from weather_tool) ──────

def _resolve_city(name: str) -> tuple[float, float] | None:
    """Resolve a city/state name to (lat, lon). Checks airports, ports, then weather_tool coords."""
    key = name.strip().lower()

    # Check airport cities
    for ap in AIRPORTS:
        if key in (ap["city"].lower(), ap["code"].lower()):
            return ap["lat"], ap["lon"]

    # Check port cities
    for pt in PORTS:
        if key in (pt["city"].lower(), pt["state"].lower()):
            return pt["lat"], pt["lon"]

    # Fall back to weather_tool's city coords
    from app.tools.weather_tool import _CITY_COORDS
    coords = _CITY_COORDS.get(key)
    if coords:
        return coords

    return None


# ── Nearest transport hubs ──────────────────────────────────

async def find_nearest_hubs(
    location_name: str | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
    hub_type: str = "both",
    radius_km: float = 300.0,
    limit: int = 3,
) -> dict[str, Any]:
    """Find nearest airports and/or ports to a location.

    Args:
        location_name: City or state name to resolve coordinates.
        latitude/longitude: Explicit coordinates (override location_name).
        hub_type: "airport", "port", or "both".
        radius_km: Search radius in km.
        limit: Max results per hub type.
    """
    if latitude is not None and longitude is not None:
        lat, lon = float(latitude), float(longitude)
    elif location_name:
        coords = _resolve_city(location_name)
        if not coords:
            return {"error": f"Unknown location '{location_name}'. Provide lat/lon or a known Indian city."}
        lat, lon = coords
    else:
        return {"error": "Provide location_name or latitude/longitude."}

    results: dict[str, Any] = {"location": location_name or f"{lat},{lon}", "latitude": lat, "longitude": lon}

    if hub_type in ("airport", "both"):
        airports = []
        for ap in AIRPORTS:
            dist = _haversine_km(lat, lon, ap["lat"], ap["lon"])
            if dist <= radius_km:
                airports.append({
                    "name": ap["name"],
                    "code": ap["code"],
                    "city": ap["city"],
                    "distance_km": round(dist, 1),
                    "runway_m": ap["runway_m"],
                    "military": ap["military"],
                    "airlift_eta_hrs": round(dist / 500 + 0.5, 1),  # ~500 km/h avg + 30min prep
                })
        airports.sort(key=lambda x: x["distance_km"])
        results["nearest_airports"] = airports[:limit]

    if hub_type in ("port", "both"):
        ports = []
        for pt in PORTS:
            dist = _haversine_km(lat, lon, pt["lat"], pt["lon"])
            if dist <= radius_km:
                ports.append({
                    "name": pt["name"],
                    "city": pt["city"],
                    "state": pt["state"],
                    "distance_km": round(dist, 1),
                    "type": pt["type"],
                    "capacity_mt_yr": pt["capacity_mt_yr"],
                })
        ports.sort(key=lambda x: x["distance_km"])
        results["nearest_ports"] = ports[:limit]

    return results


# ── OpenRouteService alternative routes ─────────────────────

_ORS_BASE = "https://api.openrouteservice.org/v2/directions/driving-car"


async def find_alternative_routes(
    origin: str,
    destination: str,
    avoid_roads: Optional[list[str]] = None,
) -> dict[str, Any]:
    """Find driving routes between two Indian cities using OpenRouteService.

    Falls back to haversine estimate if ORS API is unavailable or no key configured.

    Args:
        origin: Origin city name.
        destination: Destination city name.
        avoid_roads: Optional list of road names to note as blocked (used for context,
                     ORS avoidance uses coordinate-based polygons which we approximate).
    """
    origin_coords = _resolve_city(origin)
    dest_coords = _resolve_city(destination)

    if not origin_coords:
        return {"error": f"Unknown origin '{origin}'. Use a known Indian city name."}
    if not dest_coords:
        return {"error": f"Unknown destination '{destination}'. Use a known Indian city name."}

    o_lat, o_lon = origin_coords
    d_lat, d_lon = dest_coords
    straight_km = _haversine_km(o_lat, o_lon, d_lat, d_lon)

    # Try ORS API (free tier, needs key in env)
    import os
    ors_key = os.environ.get("ORS_API_KEY", "")

    routes: list[dict[str, Any]] = []

    if ors_key:
        try:
            headers = {"Authorization": ors_key, "Content-Type": "application/json"}
            body = {
                "coordinates": [[o_lon, o_lat], [d_lon, d_lat]],
                "alternative_routes": {"target_count": 3, "weight_factor": 1.6, "share_factor": 0.6},
                "units": "km",
            }
            async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
                resp = await client.post(_ORS_BASE, json=body, headers=headers)
                resp.raise_for_status()
                data = resp.json()

            for i, route in enumerate(data.get("routes", [])):
                summary = route.get("summary", {})
                routes.append({
                    "route_index": i + 1,
                    "distance_km": round(summary.get("distance", 0), 1),
                    "duration_hrs": round(summary.get("duration", 0) / 3600, 1),
                    "source": "OpenRouteService",
                })
            logger.info(f"[route] ORS returned {len(routes)} routes: {origin} → {destination}")
        except Exception as e:
            logger.warning(f"[route] ORS API failed: {e}, falling back to estimate")

    # Fallback: haversine-based estimate (road distance ≈ 1.3× straight-line)
    if not routes:
        road_factor = 1.3
        est_km = round(straight_km * road_factor, 1)
        avg_speed = 50  # km/h average Indian highway
        est_hrs = round(est_km / avg_speed, 1)

        routes.append({
            "route_index": 1,
            "distance_km": est_km,
            "duration_hrs": est_hrs,
            "source": "estimate (haversine × 1.3)",
        })
        # Estimate a longer alternative (+30-40%)
        alt_km = round(est_km * 1.35, 1)
        alt_hrs = round(alt_km / avg_speed, 1)
        routes.append({
            "route_index": 2,
            "distance_km": alt_km,
            "duration_hrs": alt_hrs,
            "source": "estimate (alternate, +35%)",
        })

    # Enrich with nearest transport hubs at destination for multi-modal options
    hubs = await find_nearest_hubs(latitude=d_lat, longitude=d_lon, hub_type="both", radius_km=200, limit=2)

    return {
        "origin": origin,
        "destination": destination,
        "straight_line_km": round(straight_km, 1),
        "blocked_roads": avoid_roads or [],
        "road_routes": routes,
        "airlift_option": hubs.get("nearest_airports", [])[:2],
        "sea_option": hubs.get("nearest_ports", [])[:2],
    }


# ── Register tools ──────────────────────────────────────────

tool_registry.register(
    name="find_alternative_routes",
    description=(
        "Find driving routes between two Indian cities with alternative route options. "
        "Also returns nearest airports and ports at the destination for multi-modal "
        "transport (airlift, sea freight) when roads are blocked. "
        "Accepts city names like 'Bhubaneswar', 'Chennai', 'Kedarnath', etc."
    ),
    parameters={
        "type": "object",
        "properties": {
            "origin": {
                "type": "string",
                "description": "Origin city name (e.g. 'Bhubaneswar', 'Delhi')",
            },
            "destination": {
                "type": "string",
                "description": "Destination city name (e.g. 'Puri', 'Kedarnath')",
            },
            "avoid_roads": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of road names that are blocked (e.g. ['NH-16', 'NH-10'])",
            },
        },
        "required": ["origin", "destination"],
    },
    handler=find_alternative_routes,
)

tool_registry.register(
    name="find_nearest_hubs",
    description=(
        "Find nearest airports and seaports to a location within a given radius. "
        "Returns distance, airlift ETA, runway length, port capacity. "
        "Use this when road transport is blocked and you need air or sea alternatives."
    ),
    parameters={
        "type": "object",
        "properties": {
            "location_name": {
                "type": "string",
                "description": "City or state name (e.g. 'Puri', 'Uttarakhand', 'Kedarnath')",
            },
            "latitude": {
                "type": "number",
                "description": "Latitude (if location_name not provided)",
            },
            "longitude": {
                "type": "number",
                "description": "Longitude (if location_name not provided)",
            },
            "hub_type": {
                "type": "string",
                "enum": ["airport", "port", "both"],
                "description": "Type of transport hub to search for (default: both)",
            },
            "radius_km": {
                "type": "number",
                "description": "Search radius in km (default: 300)",
            },
            "limit": {
                "type": "integer",
                "description": "Max results per hub type (default: 3)",
            },
        },
        "required": [],
    },
    handler=find_nearest_hubs,
)
