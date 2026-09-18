"""
Unit tests for src/batch_engine.py - runs with plain stdlib unittest, no
network calls: maps_client.geocode and maps_client.compute_route_matrix are
mocked out.

Run with:
    python -m unittest tests/test_batch_engine.py -v
"""
from __future__ import annotations

import shutil
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd

from src import maps_client
from src.batch_engine import process_dataframe
from src.cache_store import DistanceCache

# Fake coordinates for three India cities, keyed by lowercase name.
FAKE_COORDS = {
    "mumbai": (19.0760, 72.8777),
    "pune": (18.5204, 73.8567),
    "nagpur": (21.1458, 79.0882),
    "atlantis": None,  # deliberately unresolvable, to test "Not found"
}


def fake_geocode(address, api_key, region="in", timeout=10):
    coords = FAKE_COORDS.get(address.strip().lower())
    if coords is None:
        return None
    lat, lng = coords
    return {"lat": lat, "lng": lng, "formatted_address": address}


def fake_compute_route_matrix(origins, destinations, api_key, travel_mode="DRIVE", routing_preference="TRAFFIC_UNAWARE", timeout=30):
    # Deterministic fake distance: proportional to lat/lng offset, just needs
    # to be consistent and non-zero for the test to check dedup behaviour.
    out = []
    for oi, (olat, olng) in enumerate(origins):
        for di, (dlat, dlng) in enumerate(destinations):
            dist_m = int((abs(olat - dlat) + abs(olng - dlng)) * 111_000) or 1000
            out.append({
                "origin_index": oi, "destination_index": di,
                "distance_m": dist_m, "duration_s": dist_m // 10,
                "found": True,
            })
    return out


class BatchEngineTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.cache = DistanceCache(path=f"{self.tmpdir}/cache.csv")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    @patch.object(maps_client, "compute_route_matrix", side_effect=fake_compute_route_matrix)
    @patch.object(maps_client, "geocode", side_effect=fake_geocode)
    def test_dedup_and_broadcast(self, _mock_geocode, _mock_matrix):
        # 4 rows, but only 2 unique (source, destination) pairs -> Mumbai/Pune
        # repeats 3 times and should only cost one API call, not three.
        df = pd.DataFrame({
            "source": ["Mumbai", "Mumbai", "Mumbai", "Nagpur"],
            "destination": ["Pune", "Pune", "Pune", "Pune"],
        })

        result = process_dataframe(df, api_key="fake-key", allow_global_fallback=True, cache=self.cache)

        self.assertEqual(len(result), 4)
        self.assertTrue((result["status"] == "Found (India)").all())
        # All Mumbai->Pune rows should have the identical distance (broadcast worked).
        mumbai_rows = result[result["source"] == "Mumbai"]
        self.assertEqual(mumbai_rows["distance"].nunique(), 1)
        self.assertGreater(result["distance"].iloc[0], 0)

    @patch.object(maps_client, "compute_route_matrix", side_effect=fake_compute_route_matrix)
    @patch.object(maps_client, "geocode", side_effect=fake_geocode)
    def test_cache_hit_skips_api_call(self, mock_geocode, mock_matrix):
        df = pd.DataFrame({"source": ["Mumbai"], "destination": ["Pune"]})
        process_dataframe(df, api_key="fake-key", allow_global_fallback=True, cache=self.cache)
        first_call_count = mock_matrix.call_count

        # Second run with a fresh DistanceCache instance pointed at the same
        # file should hit the cache and make zero further Route Matrix calls.
        reloaded_cache = DistanceCache(path=self.cache.path)
        process_dataframe(df, api_key="fake-key", allow_global_fallback=True, cache=reloaded_cache)

        self.assertGreater(first_call_count, 0)
        self.assertEqual(mock_matrix.call_count, first_call_count)  # no new calls

    @patch.object(maps_client, "compute_route_matrix", side_effect=fake_compute_route_matrix)
    @patch.object(maps_client, "geocode", side_effect=fake_geocode)
    def test_unresolvable_place_marked_not_found(self, _mock_geocode, _mock_matrix):
        df = pd.DataFrame({"source": ["Mumbai"], "destination": ["Atlantis"]})
        result = process_dataframe(df, api_key="fake-key", allow_global_fallback=True, cache=self.cache)
        self.assertEqual(result["status"].iloc[0], "Not found")
        self.assertTrue(pd.isna(result["distance"].iloc[0]))

    @patch.object(maps_client, "compute_route_matrix", side_effect=fake_compute_route_matrix)
    @patch.object(maps_client, "geocode", side_effect=fake_geocode)
    def test_missing_distance_column_is_created(self, _mock_geocode, _mock_matrix):
        df = pd.DataFrame({"source": ["Mumbai"], "destination": ["Pune"]})
        self.assertNotIn("distance", df.columns)
        result = process_dataframe(df, api_key="fake-key", allow_global_fallback=True, cache=self.cache)
        self.assertIn("distance", result.columns)
        self.assertIn("duration_min", result.columns)
        self.assertIn("status", result.columns)


if __name__ == "__main__":
    unittest.main()
