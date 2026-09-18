from __future__ import annotations

import shutil
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd

from src import maps_client
from src.batch_engine import process_dataframe
from src.cache_store import DistanceCache

# "Jalna" only resolves when ", India" is appended - simulates a real
# ambiguous small-town name that fails a bare lookup.
GEOCODE_TABLE = {
    "beed": (18.9894, 75.7601),
    "jalna, india": (19.8347, 75.8816),
}


def fake_geocode(address, api_key, region="in", timeout=10):
    coords = GEOCODE_TABLE.get(address.strip().lower())
    if coords is None:
        return None
    lat, lng = coords
    return {"lat": lat, "lng": lng, "formatted_address": address}


def fake_compute_route_matrix(origins, destinations, api_key, travel_mode="DRIVE", routing_preference="TRAFFIC_UNAWARE", timeout=30):
    out = []
    for oi, (olat, olng) in enumerate(origins):
        for di, (dlat, dlng) in enumerate(destinations):
            dist_m = int((abs(olat - dlat) + abs(olng - dlng)) * 111_000) or 1000
            out.append({"origin_index": oi, "destination_index": di, "distance_m": dist_m, "duration_s": dist_m // 10, "found": True})
    return out


class RetryBehaviorTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.cache = DistanceCache(path=f"{self.tmpdir}/cache.csv")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    @patch.object(maps_client, "compute_route_matrix", side_effect=fake_compute_route_matrix)
    @patch.object(maps_client, "geocode", side_effect=fake_geocode)
    def test_india_suffix_retry_resolves_ambiguous_name(self, _mock_geocode, _mock_matrix):
        # "Jalna" alone fails; only "Jalna, India" succeeds in GEOCODE_TABLE -
        # this proves the cascade actually reaches the suffix-retry step.
        df = pd.DataFrame({"source": ["Beed"], "destination": ["Jalna"]})
        result = process_dataframe(df, api_key="fake-key", allow_global_fallback=True, cache=self.cache)
        self.assertEqual(result["status"].iloc[0], "Found (India)")
        self.assertGreater(result["distance"].iloc[0], 0)

    @patch.object(maps_client, "compute_route_matrix", side_effect=fake_compute_route_matrix)
    @patch.object(maps_client, "geocode", side_effect=fake_geocode)
    def test_stale_not_found_cache_entry_is_retried(self, _mock_geocode, _mock_matrix):
        # Manually poison the cache with a "not found" entry for a pair that
        # would actually resolve fine - simulates the exact bug reported
        # (a past transient failure permanently cached as a negative).
        self.cache.put("Beed", "Jalna", "DRIVE", None, None, False, False)
        self.cache.save()

        reloaded = DistanceCache(path=self.cache.path)
        df = pd.DataFrame({"source": ["Beed"], "destination": ["Jalna"]})
        result = process_dataframe(df, api_key="fake-key", allow_global_fallback=True, cache=reloaded)

        self.assertEqual(result["status"].iloc[0], "Found (India)")
        self.assertGreater(result["distance"].iloc[0], 0)

    @patch.object(maps_client, "compute_route_matrix", side_effect=fake_compute_route_matrix)
    @patch.object(maps_client, "geocode", side_effect=fake_geocode)
    def test_stale_zero_distance_cache_entry_is_retried(self, _mock_geocode, _mock_matrix):
        # A cached distance of exactly 0 should also be treated as unusable
        # and retried, not trusted as a real answer.
        self.cache.put("Beed", "Jalna", "DRIVE", 0, 0, True, False)
        self.cache.save()

        reloaded = DistanceCache(path=self.cache.path)
        df = pd.DataFrame({"source": ["Beed"], "destination": ["Jalna"]})
        result = process_dataframe(df, api_key="fake-key", allow_global_fallback=True, cache=reloaded)

        self.assertGreater(result["distance"].iloc[0], 0)

    @patch.object(maps_client, "compute_route_matrix", side_effect=fake_compute_route_matrix)
    @patch.object(maps_client, "geocode", side_effect=fake_geocode)
    def test_confirmed_good_cache_entry_is_trusted_and_skips_api_call(self, mock_geocode, mock_matrix):
        # A genuine, non-zero cached result should NOT trigger a re-lookup.
        self.cache.put("Beed", "Jalna", "DRIVE", 50000, 3000, True, False)
        self.cache.save()

        reloaded = DistanceCache(path=self.cache.path)
        df = pd.DataFrame({"source": ["Beed"], "destination": ["Jalna"]})
        process_dataframe(df, api_key="fake-key", allow_global_fallback=True, cache=reloaded)

        mock_geocode.assert_not_called()
        mock_matrix.assert_not_called()


if __name__ == "__main__":
    unittest.main()