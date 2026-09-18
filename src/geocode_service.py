"""
Place resolution with an escalating cascade of attempts, so short or
ambiguous place names (small towns, local spellings) get more than one
shot before being marked unresolved:

  1. The query as given, India-biased.
  2. The query as given, no region restriction (global) - only if
     allow_global_fallback is True.
  3. The query with ", India" appended, India-biased.
  4. The query with ", India" appended, no region restriction - only if
     allow_global_fallback is True.

The first attempt that returns a result wins. used_global_fallback is only
True if the winning attempt was one of the unrestricted ones (2 or 4).
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
    Never raises - API failures are treated the same as "no result from
    this attempt" so a single bad call can't crash a whole batch; the
    cascade just moves on to the next attempt.
    """
    key = query.strip().lower()
    if cache is not None and key in cache:
        return cache[key]

    attempts: list[tuple[str, Optional[str]]] = [(query, "in")]
    if allow_global_fallback:
        attempts.append((query, None))
    attempts.append((f"{query}, India", "in"))
    if allow_global_fallback:
        attempts.append((f"{query}, India", None))

    result = None
    used_fallback = False
    for attempt_query, region in attempts:
        try:
            result = maps_client.geocode(attempt_query, api_key, region=region)
        except maps_client.MapsAPIError:
            result = None
        if result is not None:
            used_fallback = region is None
            break

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