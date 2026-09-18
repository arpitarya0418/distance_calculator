"""
Excel read/validate/write helpers for the bulk-upload tab.
"""
from __future__ import annotations

import io

import pandas as pd

REQUIRED_COLUMNS = {"source", "destination"}


class ExcelValidationError(Exception):
    pass


def read_excel(file) -> pd.DataFrame:
    """Read an uploaded .xlsx/.xls into a DataFrame with normalized column names."""
    df = pd.read_excel(file)
    df.columns = [str(c).strip().lower() for c in df.columns]
    return df


def validate_columns(df: pd.DataFrame) -> None:
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ExcelValidationError(
            f"Missing required column(s): {', '.join(sorted(missing))}. "
            f"Found columns: {', '.join(df.columns)}"
        )


def prepare_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Validate, clean, and make sure a 'distance' column exists."""
    validate_columns(df)
    out = df.copy()
    out["source"] = out["source"].astype(str).str.strip()
    out["destination"] = out["destination"].astype(str).str.strip()
    out = out[(out["source"] != "") & (out["destination"] != "") & (out["source"].str.lower() != "nan") & (out["destination"].str.lower() != "nan")]
    if "distance" not in out.columns:
        out["distance"] = None
    return out.reset_index(drop=True)


def to_excel_bytes(df: pd.DataFrame) -> bytes:
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="results")
    return buffer.getvalue()
