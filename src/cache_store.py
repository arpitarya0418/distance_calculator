"""
Flat-file CSV cache for resolved distances, so re-running the same (or an
overlapping) spreadsheet doesn't re-pay for API calls already made.

This is intentionally NOT a database - just a small CSV loaded into a
DataFrame at the start of a run and saved back at the end. Nothing to
install. Note that Streamlit Community Cloud's local disk does not persist
across app restarts/sleeps, so treat this as a same-session speedup rather
than a permanent store (see README for options if you want it to persist).
"""
from __future__ import annotations

import os
from typing import Optional

import pandas as pd

CACHE_COLUMNS = [
    "source_key", "destination_key", "mode",
    "distance_m", "duration_s", "found", "used_global_fallback",
]


class DistanceCache:
    def __init__(self, path: str = ".cache/distance_cache.csv"):
        self.path = path
        self._df = self._load()

    def _load(self) -> pd.DataFrame:
        if os.path.exists(self.path):
            return pd.read_csv(self.path)
        return pd.DataFrame(columns=CACHE_COLUMNS)

    @staticmethod
    def _norm(text: str) -> str:
        return " ".join(str(text).strip().lower().split())

    def get(self, source: str, destination: str, mode: str = "DRIVE") -> Optional[dict]:
        if self._df.empty:
            return None
        s, d = self._norm(source), self._norm(destination)
        match = self._df[
            (self._df["source_key"] == s)
            & (self._df["destination_key"] == d)
            & (self._df["mode"] == mode)
        ]
        if match.empty:
            return None
        return match.iloc[0].to_dict()

    def put(
        self,
        source: str,
        destination: str,
        mode: str,
        distance_m: Optional[float],
        duration_s: Optional[float],
        found: bool,
        used_global_fallback: bool,
    ) -> None:
        s, d = self._norm(source), self._norm(destination)
        if not self._df.empty:
            self._df = self._df[
                ~(
                    (self._df["source_key"] == s)
                    & (self._df["destination_key"] == d)
                    & (self._df["mode"] == mode)
                )
            ]
        new_row = pd.DataFrame([{
            "source_key": s, "destination_key": d, "mode": mode,
            "distance_m": distance_m, "duration_s": duration_s,
            "found": bool(found), "used_global_fallback": bool(used_global_fallback),
        }])
        self._df = pd.concat([self._df, new_row], ignore_index=True)

    def save(self) -> None:
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        self._df.to_csv(self.path, index=False)

    def __len__(self) -> int:
        return len(self._df)
