"""
Low-level wrapper around the three Google Maps Platform APIs this project
uses: Geocoding, Places API (New) Autocomplete, and Routes API
(computeRouteMatrix + computeRoutes).

Every function here does exactly one HTTP call (with retry/backoff on
transient failures) and returns plain dicts/lists - no Streamlit, no
caching, no business logic. Higher-level behaviour (dedup, India/global
fallback, caching) lives in the other src/ modules.
"""
from __future__ import annotations

import time
from typing import Any, Optional

import requests

_session = requests.Session()
GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"
AUTOCOMPLETE_URL = "https://places.googleapis.com/v1/places:autocomplete"
ROUTE_MATRIX_URL = "https://routes.googleapis.com/distanceMatrix/v2:computeRouteMatrix"
COMPUTE_ROUTES_URL = "https://routes.googleapis.com/directions/v2:computeRoutes"

# Google's cap on origins x destinations per computeRouteMatrix request,
# for non-TRANSIT, non-TRAFFIC_AWARE_OPTIMAL requests.
MAX_ELEMENTS_PER_MATRIX_REQUEST = 625


class MapsAPIError(Exception):
    """Raised when a Google Maps Platform call fails (after retries, for
    retryable errors; immediately, for non-retryable ones)."""


class _RetryableError(Exception):
    pass


def _retry(fn, *, attempts: int = 4, base_delay: float = 1.0):
    """Call fn() with exponential backoff on transient failures (429/5xx)."""
    last_exc: Optional[Exception] = None
    for attempt in range(attempts):
        try:
            return fn()
        except _RetryableError as exc:
            last_exc = exc
            if attempt < attempts - 1:
                time.sleep(base_delay * (2 ** attempt))
    raise MapsAPIError(str(last_exc))


def geocode(address: str, api_key: str, region: Optional[str] = "in", timeout: int = 10) -> Optional[dict]:
    """
    Resolve a free-text address to {"lat":.., "lng":.., "formatted_address":..}.

    Returns None if Google found nothing (ZERO_RESULTS) - that's not an
    error, just "not found", so the caller can decide whether to retry
    with region=None (global search).
    """
    params = {"address": address, "key": api_key}
    if region:
        params["region"] = region

    def _call():
        # resp = requests.get(GEOCODE_URL, params=params, timeout=timeout)
        resp = _session.get(GEOCODE_URL, params=params, timeout=timeout)
        data = resp.json()
        status = data.get("status")
        if status == "OK":
            result = data["results"][0]
            loc = result["geometry"]["location"]
            return {
                "lat": loc["lat"],
                "lng": loc["lng"],
                "formatted_address": result.get("formatted_address", address),
            }
        if status == "ZERO_RESULTS":
            return None
        if status in ("OVER_QUERY_LIMIT", "UNKNOWN_ERROR"):
            raise _RetryableError(f"Geocoding {status}")
        raise MapsAPIError(f"Geocoding failed: {status} - {data.get('error_message', '')}")

    return _retry(_call)


def autocomplete(
    input_text: str,
    api_key: str,
    region_code: str = "IN",
    session_token: Optional[str] = None,
    timeout: int = 10,
) -> list[dict]:
    """Return up to 5 place suggestions: [{"text": ..., "place_id": ...}, ...]."""
    headers = {"Content-Type": "application/json", "X-Goog-Api-Key": api_key}
    body: dict[str, Any] = {"input": input_text, "regionCode": region_code}
    if session_token:
        body["sessionToken"] = session_token

    def _call():
        # resp = requests.post(AUTOCOMPLETE_URL, headers=headers, json=body, timeout=timeout)
        resp = _session.post(AUTOCOMPLETE_URL, headers=headers, json=body, timeout=timeout)
        if resp.status_code == 429 or resp.status_code >= 500:
            raise _RetryableError(f"Autocomplete HTTP {resp.status_code}")
        if resp.status_code != 200:
            raise MapsAPIError(f"Autocomplete failed: HTTP {resp.status_code} - {resp.text[:300]}")
        suggestions = resp.json().get("suggestions", [])
        out = []
        for s in suggestions[:5]:
            pred = s.get("placePrediction", {})
            out.append({
                "text": pred.get("text", {}).get("text", ""),
                "place_id": pred.get("placeId", ""),
            })
        return out

    return _retry(_call)


def compute_route_matrix(
    origins: list[tuple[float, float]],
    destinations: list[tuple[float, float]],
    api_key: str,
    travel_mode: str = "DRIVE",
    routing_preference: str = "TRAFFIC_UNAWARE",
    timeout: int = 30,
) -> list[dict]:
    """
    Batch distance/duration lookup for up to 625 origin x destination
    elements in a single call. Returns a list of:
        {"origin_index", "destination_index", "distance_m", "duration_s", "found"}
    """
    n_elements = len(origins) * len(destinations)
    if n_elements > MAX_ELEMENTS_PER_MATRIX_REQUEST:
        raise ValueError(
            f"{n_elements} elements exceeds Google's "
            f"{MAX_ELEMENTS_PER_MATRIX_REQUEST}-element limit per request"
        )

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "originIndex,destinationIndex,distanceMeters,duration,status,condition",
    }
    body = {
        "origins": [
            {"waypoint": {"location": {"latLng": {"latitude": lat, "longitude": lng}}}}
            for lat, lng in origins
        ],
        "destinations": [
            {"waypoint": {"location": {"latLng": {"latitude": lat, "longitude": lng}}}}
            for lat, lng in destinations
        ],
        "travelMode": travel_mode,
        "routingPreference": routing_preference,
    }

    def _call():
        # resp = requests.post(ROUTE_MATRIX_URL, headers=headers, json=body, timeout=timeout)
        resp = _session.post(ROUTE_MATRIX_URL, headers=headers, json=body, timeout=timeout)
        if resp.status_code == 429 or resp.status_code >= 500:
            raise _RetryableError(f"Route Matrix HTTP {resp.status_code}")
        if resp.status_code != 200:
            raise MapsAPIError(f"Route Matrix failed: HTTP {resp.status_code} - {resp.text[:300]}")


        # elements = resp.json()
        # out = []
        # for el in elements:
        #     found = el.get("condition") == "ROUTE_EXISTS"
        #     out.append({
        #         "origin_index": el["originIndex"],
        #         "destination_index": el["destinationIndex"],
        #         "distance_m": el.get("distanceMeters") if found else None,
        #         "duration_s": _parse_duration(el.get("duration")) if found else None,
        #         "found": found,
        #     })

        elements = resp.json()
        out = []
        for el in elements:
            if "originIndex" not in el or "destinationIndex" not in el:
                # Occasionally Google returns a per-element error without
                # indices - skip it instead of crashing the whole batch;
                # that pair just gets treated as unresolved and retried
                # on the next run.
                print(f"[maps_client] Skipping malformed route matrix element: {el}")
                continue
            found = el.get("condition") == "ROUTE_EXISTS"
            out.append({
                "origin_index": el["originIndex"],
                "destination_index": el["destinationIndex"],
                "distance_m": el.get("distanceMeters") if found else None,
                "duration_s": _parse_duration(el.get("duration")) if found else None,
                "found": found,
            })
        return out

    return _retry(_call)


def compute_route(
    origin: tuple[float, float],
    destination: tuple[float, float],
    api_key: str,
    travel_mode: str = "DRIVE",
    routing_preference: Optional[str] = "TRAFFIC_UNAWARE",
    timeout: int = 15,
) -> Optional[dict]:
    """
    Single point-to-point distance/duration for a given travel mode, used by
    the Test tab. Returns {"distance_m", "duration_s"} or None if no route.
    """
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "routes.distanceMeters,routes.duration",
    }
    body: dict[str, Any] = {
        "origin": {"location": {"latLng": {"latitude": origin[0], "longitude": origin[1]}}},
        "destination": {"location": {"latLng": {"latitude": destination[0], "longitude": destination[1]}}},
        "travelMode": travel_mode,
    }
    # routingPreference is only valid for DRIVE / TWO_WHEELER travel modes.
    if travel_mode == "DRIVE" and routing_preference:
        body["routingPreference"] = routing_preference

    def _call():
        # resp = requests.post(COMPUTE_ROUTES_URL, headers=headers, json=body, timeout=timeout)
        resp = _session.post(COMPUTE_ROUTES_URL, headers=headers, json=body, timeout=timeout)
        if resp.status_code == 429 or resp.status_code >= 500:
            raise _RetryableError(f"computeRoutes HTTP {resp.status_code}")
        if resp.status_code != 200:
            raise MapsAPIError(f"computeRoutes failed: HTTP {resp.status_code} - {resp.text[:300]}")
        routes = resp.json().get("routes", [])
        if not routes:
            return None
        route = routes[0]
        return {
            "distance_m": route.get("distanceMeters"),
            "duration_s": _parse_duration(route.get("duration")),
        }

    return _retry(_call)


def _parse_duration(duration_str: Optional[str]) -> Optional[int]:
    """Google returns durations like '361s' - convert to an int seconds."""
    if not duration_str:
        return None
    return int(str(duration_str).rstrip("s"))
