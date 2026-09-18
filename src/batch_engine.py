"""
Turns a raw DataFrame of (source, destination[, distance]) rows into a
fully-populated distance/duration/status DataFrame, as fast and cheaply as
possible:

  1. Deduplicate to unique (source, destination) pairs.
  2. Check the on-disk cache for pairs already resolved - but only trust a
     cached entry if it's a genuine, non-zero result. A cached "not found"
     or a distance of 0 is treated as unresolved and retried, since either
     one is more likely to be a past failure (rate limit, a bad element,
     an ambiguous name) than a confirmed answer.
  3. Geocode any places not yet resolved (India-first, then global, then
     retried with ", India" appended to the query - see geocode_service),
     concurrently.
  4. Group remaining pairs by origin, chunk into batches sized so there are
     at least max_workers of them (so worker threads actually run in
     parallel instead of a few oversized requests dominating), and fire
     those batches concurrently against computeRouteMatrix.
  5. Broadcast each unique pair's result back onto every original row that
     shares it, saving newly-resolved pairs to the cache periodically so a
     mid-run failure doesn't lose everything resolved so far.
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
SAVE_EVERY_N_BATCHES = 25


@dataclass
class BatchProgress:
    total_pairs: int = 0
    cache_hits: int = 0
    geocoded: int = 0
    geocode_failures: int = 0
    api_calls_made: int = 0
    elements_resolved: int = 0


def _cached_result_is_usable(cached: Optional[dict]) -> bool:
    """A cached row is only trustworthy if it's a confirmed, non-zero find.
    A cached "not found" or a 0 distance is treated as unresolved so it
    gets retried instead of permanently stuck."""
    if cached is None:
        return False
    if not cached.get("found"):
        return False
    distance = cached.get("distance_m")
    if pd.isna(distance) or distance in (0, None):
        return False
    return True


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

    # --- 2. cache lookup (only trusting confirmed, non-zero results) ---
    pair_results: dict[tuple[str, str], dict] = {}
    uncached_pairs: list[tuple[str, str]] = []
    for _, row in pairs.iterrows():
        cached = cache.get(row["source"], row["destination"])
        if _cached_result_is_usable(cached):
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

        # --- 4. group by origin, chunk for parallelism, batch concurrently ---
        by_origin: dict[str, list[str]] = {}
        for src, dst in uncached_pairs:
            by_origin.setdefault(src, []).append(dst)

        total_dests = sum(len(d) for d in by_origin.values())
        # Aim for at least max_workers batches so every worker thread has
        # something to do concurrently, instead of a few oversized requests
        # running one after another in effect.
        chunk_size = min(MAX_ELEMENTS, max(total_dests // max_workers, 1))

        batch_jobs: list[tuple[str, list[str]]] = []
        for origin, dests in by_origin.items():
            dests = list(dict.fromkeys(dests))  # dedupe, preserve order
            for i in range(0, len(dests), chunk_size):
                batch_jobs.append((origin, dests[i:i + chunk_size]))

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

        try:
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = [executor.submit(_run_batch, origin, dests) for origin, dests in batch_jobs]
                for i, future in enumerate(as_completed(futures), start=1):
                    origin, dests, elements = future.result()
                    progress.api_calls_made += 1

                    if elements is None:
                        for dst in dests:
                            result = {"distance_m": None, "duration_s": None, "found": False, "used_global_fallback": False}
                            pair_results[(origin, dst)] = result
                            # Deliberately NOT cached: a failed/empty batch is
                            # indistinguishable here from a transient error, so
                            # leaving it out of the cache means it gets a fresh
                            # attempt on the next run instead of being stuck.
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
                        if el["found"] and el["distance_m"]:
                            # Only cache confirmed, non-zero results.
                            cache.put(origin, dst, "DRIVE", el["distance_m"], el["duration_s"], True, used_fallback)
                        progress.elements_resolved += 1

                    _report(f"{progress.elements_resolved}/{len(uncached_pairs)} pairs resolved")

                    # Save periodically so a crash mid-run only risks losing
                    # the last partial stretch of batches, not everything so far.
                    if i % SAVE_EVERY_N_BATCHES == 0:
                        cache.save()
        finally:
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