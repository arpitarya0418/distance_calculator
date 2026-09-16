import requests
from config import GEOCODER_URL, REQUEST_TIMEOUT, USER_AGENT

def search_places(query, limit=5):
    if not query or len(query.strip()) < 3:
        return []

    params={
        "q": query.strip(),
        "limit": limit,
        "lang": "en"
    }

    headers={
        "User-Agent": USER_AGENT
    }

    response=requests.get(
        GEOCODER_URL,
        params=params,
        headers=headers,
        timeout=REQUEST_TIMEOUT
    )

    response.raise_for_status()

    data=response.json()
    results=[]

    for feature in data.get("features", []):
        properties=feature.get("properties", {})
        geometry=feature.get("geometry", {})
        coordinates=geometry.get("coordinates", [])

        if len(coordinates) < 2:
            continue

        results.append({
            "name": build_place_name(properties),
            "latitude": coordinates[1],
            "longitude": coordinates[0]
        })

    return results

def build_place_name(properties):
    name=properties.get("name", "")
    city=properties.get("city") or properties.get("town") or properties.get("village") or ""
    state=properties.get("state", "")
    country=properties.get("country", "")

    parts=[]

    for value in [name, city, state, country]:
        if value and value not in parts:
            parts.append(value)

    return ", ".join(parts)