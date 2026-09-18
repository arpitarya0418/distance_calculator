"""
India-first, global-fallback place resolution.

resolve_place() tries a India-biased geocode first; if that comes back
empty and global fallback is allowed, it retries with no region
restriction and flags the result accordingly.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from . import maps_client


@dataclass
class ResolvedPlace:
    query: str
    lat: Optional[float]
    lng: Optional[float]
    formatted_address: Optional[str]
    found: bool
    used_global_fallback: bool


def resolve_place(
    query: str,
    api_key: str,
    allow_global_fallback: bool = True,
    cache: Optional[dict] = None,
) -> ResolvedPlace:
    """
    Resolve one place name. `cache`, if provided, is a dict the caller keeps
    across many calls so the same place name isn't geocoded twice in a run.
    Never raises - API failures are treated the same as "not found" so a
    single bad place name can't crash a whole batch.
    """
    key = query.strip().lower()
    if cache is not None and key in cache:
        return cache[key]

    try:
        result = maps_client.geocode(query, api_key, region="in")
    except maps_client.MapsAPIError:
        result = None

    used_fallback = False
    if result is None and allow_global_fallback:
        try:
            result = maps_client.geocode(query, api_key, region=None)
            used_fallback = result is not None
        except maps_client.MapsAPIError:
            result = None

    resolved = ResolvedPlace(
        query=query,
        lat=result["lat"] if result else None,
        lng=result["lng"] if result else None,
        formatted_address=result["formatted_address"] if result else None,
        found=result is not None,
        used_global_fallback=used_fallback,
    )

    if cache is not None:
        cache[key] = resolved
    return resolved
