"""
Turns a raw DataFrame of (source, destination[, distance]) rows into a
fully-populated distance/duration/status DataFrame, as fast and cheaply as
possible:

  1. Deduplicate to unique (source, destination) pairs.
  2. Check the on-disk cache for pairs already resolved.
  3. Geocode any places not yet resolved (India-first, global-fallback),
     concurrently.
  4. Group remaining pairs by origin, chunk each origin's destinations into
     batches of <=625 elements, and fire those batches concurrently against
     computeRouteMatrix.
  5. Broadcast each unique pair's result back onto every original row that
     shares it, and save newly-resolved pairs to the cache.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Callable, Optional

import pandas as pd

from . import maps_client
from .cache_store import DistanceCache
from .geocode_service import resolve_place, ResolvedPlace

MAX_ELEMENTS = maps_client.MAX_ELEMENTS_PER_MATRIX_REQUEST


@dataclass
class BatchProgress:
    total_pairs: int = 0
    cache_hits: int = 0
    geocoded: int = 0
    geocode_failures: int = 0
    api_calls_made: int = 0
    elements_resolved: int = 0


def process_dataframe(
    df: pd.DataFrame,
    api_key: str,
    allow_global_fallback: bool,
    cache: DistanceCache,
    max_workers: int = 8,
    on_progress: Optional[Callable[[BatchProgress, str], None]] = None,
) -> pd.DataFrame:
    """
    df must have 'source' and 'destination' columns. Returns a copy of df
    with 'distance' (km), 'duration_min', and 'status' columns populated.
    """
    progress = BatchProgress()
    out = df.copy()
    for col in ("distance", "duration_min", "status"):
        if col not in out.columns:
            out[col] = None

    def _report(msg: str) -> None:
        if on_progress:
            on_progress(progress, msg)

    # --- 1. unique pairs ---
    pairs = out[["source", "destination"]].drop_duplicates().reset_index(drop=True)
    progress.total_pairs = len(pairs)
    _report(f"{len(pairs)} unique source/destination pairs out of {len(out)} rows")

    # --- 2. cache lookup ---
    pair_results: dict[tuple[str, str], dict] = {}
    uncached_pairs: list[tuple[str, str]] = []
    for _, row in pairs.iterrows():
        cached = cache.get(row["source"], row["destination"])
        if cached is not None:
            pair_results[(row["source"], row["destination"])] = cached
            progress.cache_hits += 1
        else:
            uncached_pairs.append((row["source"], row["destination"]))
    _report(f"{progress.cache_hits} pairs already in cache, {len(uncached_pairs)} need lookup")

    if uncached_pairs:
        # --- 3. geocode unique places (source + destination combined), concurrently ---
        unique_places = sorted({p[0] for p in uncached_pairs} | {p[1] for p in uncached_pairs})
        place_cache: dict[str, ResolvedPlace] = {}
        _report(f"Geocoding {len(unique_places)} unique place names")

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(resolve_place, place, api_key, allow_global_fallback, None): place
                for place in unique_places
            }
            for future in as_completed(futures):
                place = futures[future]
                resolved = future.result()
                place_cache[place.strip().lower()] = resolved
                if resolved.found:
                    progress.geocoded += 1
                else:
                    progress.geocode_failures += 1
        _report(f"Geocoded {progress.geocoded}, failed to resolve {progress.geocode_failures}")

        # --- 4. group by origin, chunk to <=625 elements, batch concurrently ---
        by_origin: dict[str, list[str]] = {}
        for src, dst in uncached_pairs:
            by_origin.setdefault(src, []).append(dst)

        batch_jobs: list[tuple[str, list[str]]] = []
        for origin, dests in by_origin.items():
            dests = list(dict.fromkeys(dests))  # dedupe, preserve order
            for i in range(0, len(dests), MAX_ELEMENTS):
                batch_jobs.append((origin, dests[i:i + MAX_ELEMENTS]))

        _report(f"Running {len(batch_jobs)} batched Route Matrix request(s)")

        def _run_batch(origin: str, dests: list[str]):
            origin_place = place_cache.get(origin.strip().lower())
            if not origin_place or not origin_place.found:
                return origin, dests, None  # can't route an unresolved origin

            dest_places = [place_cache.get(d.strip().lower()) for d in dests]
            valid = [(d, p) for d, p in zip(dests, dest_places) if p and p.found]
            if not valid:
                return origin, dests, None

            valid_dests, valid_places = zip(*valid)
            try:
                elements = maps_client.compute_route_matrix(
                    origins=[(origin_place.lat, origin_place.lng)],
                    destinations=[(p.lat, p.lng) for p in valid_places],
                    api_key=api_key,
                )
            except maps_client.MapsAPIError:
                return origin, list(valid_dests), None
            return origin, list(valid_dests), elements

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(_run_batch, origin, dests) for origin, dests in batch_jobs]
            for future in as_completed(futures):
                origin, dests, elements = future.result()
                progress.api_calls_made += 1

                if elements is None:
                    for dst in dests:
                        result = {"distance_m": None, "duration_s": None, "found": False, "used_global_fallback": False}
                        pair_results[(origin, dst)] = result
                        cache.put(origin, dst, "DRIVE", None, None, False, False)
                    continue

                origin_place = place_cache.get(origin.strip().lower())
                for el in elements:
                    dst = dests[el["destination_index"]]
                    dst_place = place_cache.get(dst.strip().lower())
                    used_fallback = bool(
                        (origin_place and origin_place.used_global_fallback)
                        or (dst_place and dst_place.used_global_fallback)
                    )
                    result = {
                        "distance_m": el["distance_m"], "duration_s": el["duration_s"],
                        "found": el["found"], "used_global_fallback": used_fallback,
                    }
                    pair_results[(origin, dst)] = result
                    cache.put(origin, dst, "DRIVE", el["distance_m"], el["duration_s"], el["found"], used_fallback)
                    progress.elements_resolved += 1

                _report(f"{progress.elements_resolved}/{len(uncached_pairs)} pairs resolved")

        cache.save()

    # --- 5. broadcast back onto every row ---
    def _status_for(res: dict) -> str:
        if not res.get("found"):
            return "Not found"
        return "Found (global fallback)" if res.get("used_global_fallback") else "Found (India)"

    for idx, row in out.iterrows():
        res = pair_results.get((row["source"], row["destination"]))
        if res is None:
            out.at[idx, "status"] = "Not found"
            continue
        out.at[idx, "status"] = _status_for(res)
        if pd.notna(res.get("distance_m")):
            out.at[idx, "distance"] = round(res["distance_m"] / 1000, 2)
        if pd.notna(res.get("duration_s")):
            out.at[idx, "duration_min"] = round(res["duration_s"] / 60, 1)

    _report("Done")
    return out
