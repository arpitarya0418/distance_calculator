#!/usr/bin/env python3
"""
test_api_key.py

Sanity-checks a Google Maps Platform API key against the three APIs this
project needs:
    1. Geocoding API
    2. Places API (New) - Autocomplete
    3. Routes API - computeRouteMatrix (bulk) and computeRoutes (test tab)

Usage:
    pip install requests
    export GOOGLE_MAPS_API_KEY="your-key-here"
    python test_api_key.py

    # or pass the key directly as an argument:
    python test_api_key.py YOUR_KEY_HERE
"""

import os
import sys
import requests

# Fixed coordinates (Mumbai -> Pune) so the Routes tests don't depend on
# Geocoding working first.
MUMBAI = {"latitude": 19.0760, "longitude": 72.8777}
PUNE = {"latitude": 18.5204, "longitude": 73.8567}


def get_api_key() -> str:
    if len(sys.argv) > 1:
        return sys.argv[1]
    # key = os.environ.get("GOOGLE_MAPS_API_KEY")
    key = "AIzaSyBPb2tGOz-FNdr6ZeXCwaZaJovbqEYHXzE"

    if not key:
        print("No API key found.")
        print('Set it with: export GOOGLE_MAPS_API_KEY="your-key-here"')
        print("...or run: python test_api_key.py YOUR_KEY_HERE")
        sys.exit(1)
    return key


def print_result(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}")
    if detail:
        print(f"       {detail}")


def test_geocoding(api_key: str) -> bool:
    url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {"address": "Bandra Kurla Complex, Mumbai", "region": "in", "key": api_key}
    resp = requests.get(url, params=params, timeout=10)
    data = resp.json()
    if data.get("status") == "OK":
        loc = data["results"][0]["geometry"]["location"]
        print_result("Geocoding API", True, f"Resolved to {loc['lat']}, {loc['lng']}")
        return True
    print_result(
        "Geocoding API", False,
        f"status={data.get('status')}, error={data.get('error_message', 'n/a')}"
    )
    return False


def test_places_autocomplete(api_key: str) -> bool:
    url = "https://places.googleapis.com/v1/places:autocomplete"
    headers = {"Content-Type": "application/json", "X-Goog-Api-Key": api_key}
    body = {"input": "Bandra Kurla", "regionCode": "IN"}
    resp = requests.post(url, headers=headers, json=body, timeout=10)
    if resp.status_code == 200:
        n = len(resp.json().get("suggestions", []))
        print_result("Places API (New) - Autocomplete", True, f"{n} suggestion(s) returned")
        return True
    print_result("Places API (New) - Autocomplete", False, f"HTTP {resp.status_code}: {resp.text[:300]}")
    return False


def test_route_matrix(api_key: str) -> bool:
    url = "https://routes.googleapis.com/distanceMatrix/v2:computeRouteMatrix"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "originIndex,destinationIndex,distanceMeters,duration,status,condition",
    }
    body = {
        "origins": [{"waypoint": {"location": {"latLng": MUMBAI}}}],
        "destinations": [{"waypoint": {"location": {"latLng": PUNE}}}],
        "travelMode": "DRIVE",
        "routingPreference": "TRAFFIC_UNAWARE",
    }
    resp = requests.post(url, headers=headers, json=body, timeout=10)
    if resp.status_code == 200:
        data = resp.json()
        if data and "distanceMeters" in data[0]:
            km = data[0]["distanceMeters"] / 1000
            print_result("Routes API - computeRouteMatrix", True, f"Mumbai -> Pune = {km:.1f} km")
            return True
        print_result("Routes API - computeRouteMatrix", False, f"Unexpected response: {data}")
        return False
    print_result("Routes API - computeRouteMatrix", False, f"HTTP {resp.status_code}: {resp.text[:300]}")
    return False


def test_compute_routes(api_key: str) -> bool:
    url = "https://routes.googleapis.com/directions/v2:computeRoutes"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "routes.distanceMeters,routes.duration",
    }
    body = {
        "origin": {"location": {"latLng": MUMBAI}},
        "destination": {"location": {"latLng": PUNE}},
        "travelMode": "DRIVE",
        "routingPreference": "TRAFFIC_UNAWARE",
    }
    resp = requests.post(url, headers=headers, json=body, timeout=10)
    if resp.status_code == 200:
        routes = resp.json().get("routes", [])
        if routes:
            km = routes[0]["distanceMeters"] / 1000
            print_result("Routes API - computeRoutes", True, f"Mumbai -> Pune = {km:.1f} km")
            return True
        print_result("Routes API - computeRoutes", False, f"No routes in response: {resp.json()}")
        return False
    print_result("Routes API - computeRoutes", False, f"HTTP {resp.status_code}: {resp.text[:300]}")
    return False


def main() -> None:
    api_key = get_api_key()
    print("Testing Google Maps Platform API key...\n")

    results = [
        test_geocoding(api_key),
        test_places_autocomplete(api_key),
        test_route_matrix(api_key),
        test_compute_routes(api_key),
    ]

    print()
    if all(results):
        print("All checks passed - your key is good to go for this project.")
    else:
        print("Some checks failed. Common causes:")
        print("  - The API isn't enabled on this key's project (Cloud Console > APIs & Services > Library)")
        print("  - Billing isn't enabled on the linked Cloud project")
        print("  - Key restrictions (HTTP referrer / IP / API restrictions) are blocking this request")
    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    main()