# Distance Calculator (Streamlit + Google Maps)

Bulk Excel distance lookups (source/destination -> distance in km) plus a
"Test" tab for comparing car/walk/bicycle routes between two places, using
the Google Maps Platform **Routes**, **Geocoding**, and **Places (New)**
APIs.

## Project layout

```
gmaps-distance-app/
├── .streamlit/
│   ├── config.toml            # theme
│   └── secrets.toml.example   # copy to secrets.toml and fill in your key
├── app.py                     # entry point
├── ui/
│   ├── bulk_upload.py         # "Bulk Upload" tab
│   └── test_playground.py     # "Test" tab
├── src/
│   ├── maps_client.py         # raw API calls: geocode, autocomplete, route matrix, compute route
│   ├── geocode_service.py     # India-first / global-fallback resolution
│   ├── cache_store.py         # CSV cache of resolved (source, destination) pairs
│   ├── batch_engine.py        # dedup -> cache -> geocode -> batch -> broadcast
│   ├── excel_io.py            # read/validate/write Excel
│   └── cost_estimator.py      # pre-flight cost estimate
├── tests/
│   └── test_batch_engine.py   # unit tests against mocked API calls (no network needed)
├── sample_data/
│   └── sample_routes.xlsx     # small India route sample for a first test run
├── requirements.txt
└── .gitignore
```

## 1. Local setup

```bash
python -m venv .venv
# Windows:      .venv\Scripts\activate
# macOS/Linux:  source .venv/bin/activate

pip install -r requirements.txt
```

Copy the secrets template and add your key:

```bash
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# then edit .streamlit/secrets.toml and paste your real key in
```

Run it:

```bash
streamlit run app.py
```

Try the **Bulk Upload** tab first with `sample_data/sample_routes.xlsx` — it
has 6 rows but only 5 unique pairs (one exact duplicate) and a repeated
source with two different destinations, so you can watch the dedup/cache
counters do their job.

## 2. Run the tests (no API key needed)

```bash
python -m unittest tests/test_batch_engine.py -v
```

These mock out the actual Google calls, so they check the dedup / caching /
broadcast / "not found" logic in isolation, fast and free.

## 3. Excel format for the Bulk Upload tab

Required columns (case-insensitive): `source`, `destination`.
Optional: `distance` — created automatically if it isn't there, and always
(re)computed in **kilometers**. `duration_min` and `status` columns are
also added to the output.

`status` will be one of:
- `Found (India)`
- `Found (global fallback)` — only appears if "Allow global fallback search" is checked
- `Not found`

## 4. How the caching works

Results are cached to `.cache/distance_cache.csv`, keyed by normalized
`(source, destination, mode)`. Re-running the same file, or one that
overlaps with a previous run, skips API calls for pairs already resolved.

It's a plain CSV, not a database — nothing to install. On Streamlit
Community Cloud, the local disk does **not** survive app restarts or sleep,
so treat this cache as a same-session speedup rather than a permanent
store. If persistence across redeploys matters to you, two options:
- Download `.cache/distance_cache.csv` after a run and re-upload it before
  the next one (a small feature to add if you want it).
- Swap `cache_store.py` for a small hosted DB (Supabase/Neon Postgres both
  have free tiers) — nothing else in the codebase needs to change, since
  everything else talks to `DistanceCache` through `.get()` / `.put()` /
  `.save()`.

## 5. Cost

With an India billing account: Route Matrix gives 70,000 free
elements/month, and Autocomplete/Geocoding give 70,000 free requests/month
each. One "element" = one unique `(source, destination)` pair, after dedup
— so a 17,000-row file with any repeats uses fewer than 17,000 elements.
Since you're already on free-tier credits, this should cost effectively
nothing at your current scale. Figures are current as of when this project
was built — check console.cloud.google.com/billing for up-to-date rates.

## 6. Deploying to Streamlit Community Cloud

1. Push this repo to GitHub. `.streamlit/secrets.toml` stays out of it —
   it's gitignored (only `secrets.toml.example` gets committed).
2. On share.streamlit.io, create a new app pointing at this repo, with
   `app.py` as the entry point.
3. In the app's **Settings → Secrets**, paste:
   ```
   GOOGLE_MAPS_API_KEY = "your-real-key"
   ```
4. Deploy.

## 7. Known limitations / ideas for later

- Bulk distances default to `DRIVE` mode with no live traffic
  (`TRAFFIC_UNAWARE`) — this keeps batches at the 625-element cap instead of
  dropping to 100. Change `routing_preference` in `src/maps_client.py` if
  you want traffic-aware driving distances instead.
- The cache is pair-level, not place-level — geocoding results aren't
  persisted across runs yet. Worth adding a small places cache if you
  expect the same locations to reappear across many different uploads.
- No map view in the Test tab yet — distance and time only, no route drawn.
- `max_workers=8` in `process_dataframe` is a reasonable default for
  concurrency without tripping rate limits; raise it if you have a higher
  quota and want more throughput on very large files.
