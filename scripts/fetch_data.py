
#!/usr/bin/env python3
"""
UDOT Data Updater for Cottonwood Canyons
- Fetches road conditions, events, and cameras from UDOT API
- Filters for Little Cottonwood Canyon (SR-210) and Big Cottonwood Canyon (SR-190)
- Writes JSON outputs into ./data for your site or downstream processing

Requirements:
- requests (install via pip)
- (optional for local dev) python-dotenv if you want to load a local .env

Environment:
- Expects UDOT_API_KEY in the environment (GitHub Actions: Secrets → UDOT_API_KEY)

Author: Michael Van Hatten
"""

import os
import json
import re
import sys
from datetime import datetime, timezone
from typing import Tuple, List, Dict, Any

try:
    import requests
except ImportError:
    print("Missing dependency: requests. Install with `pip install requests`.", file=sys.stderr)
    sys.exit(1)

# If you also run locally and use a .env file, uncomment these lines:
# try:
#     from dotenv import load_dotenv
#     load_dotenv()
# except ImportError:
#     pass

API_KEY = os.getenv("UDOT_API_KEY")
BASE_URL = "https://www.udottraffic.utah.gov/api/v2"

# -------------------------
# Canyon filter definitions
# -------------------------

CANYON_RULES: Dict[str, Dict[str, Any]] = {
    "LCC": {
        "label": "Little Cottonwood Canyon",
        "route_numbers": {"210"},  # SR-210
        "name_patterns": [
            r"\bLittle\s+Cottonwood\b",
            r"\bLittle\s+Cottonwood\s+Canyon\b",
            r"\bLittle\s+Cottonwood\s+Canyon\s+Rd\b",
            r"\bLCC\b",
            r"\bSR[-\s]?210\b",
            r"\bUT[-\s]?210\b",
            r"\bState\s*Route\s*210\b",
            r"\bHighway\s*210\b",
            r"\bHwy\s*210\b",
            r"\bAlta\b",
            r"\bSnowbird\b",
        ],
        # Broad bbox that covers the canyon area (Alta to mouth). Adjust if needed.
        "bbox": (40.53, -111.82, 40.62, -111.61),
    },
    "BCC": {
        "label": "Big Cottonwood Canyon",
        "route_numbers": {"190"},  # SR-190
        "name_patterns": [
            r"\bBig\s+Cottonwood\b",
            r"\bBig\s+Cottonwood\s+Canyon\b",
            r"\bBig\s+Cottonwood\s+Canyon\s+Rd\b",
            r"\bBCC\b",
            r"\bSR[-\s]?190\b",
            r"\bUT[-\s]?190\b",
            r"\bState\s*Route\s*190\b",
            r"\bHighway\s*190\b",
            r"\bHwy\s*190\b",
            r"\bBrighton\b",
            r"\bSolitude\b",
        ],
        # Broad bbox that covers the canyon area (Brighton to mouth). Adjust if needed.
        "bbox": (40.58, -111.80, 40.70, -111.55),
    },
}

# Precompile regexes
for k in CANYON_RULES:
    CANYON_RULES[k]["compiled"] = [re.compile(p, re.IGNORECASE) for p in CANYON_RULES[k]["name_patterns"]]

# Fields where UDOT often places road/route/name/location text
COMMON_TEXT_FIELDS = [
    "route", "road", "roadway", "highway",
    "segment", "name", "title",
    "description", "locationDescription",
    "direction", "headline"
]
NESTED_CANDIDATES = ["location", "properties", "geo", "place", "area"]

# -------------------------
# HTTP/API utilities
# -------------------------

def get_udot_data(endpoint: str) -> List[Dict[str, Any]]:
    """
    Fetch a list of records from UDOT API.
    Returns an empty list upon failure.
    """
    if not API_KEY:
        raise ValueError("UDOT_API_KEY not found in environment. Set the GitHub secret or local .env.")

    url = f"{BASE_URL}/{endpoint}?key={API_KEY}&format=json"
    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"[ERROR] Fetch failed for {endpoint}: {e}", file=sys.stderr)
        return []

    # UDOT APIs may return a list or a dict with lists inside; try to extract list-like payloads
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        # Heuristic: return the first list found among values
        for v in data.values():
            if isinstance(v, list):
                return v
        # If nothing suitable, wrap dict for downstream inspection
        return [data]
    # Unknown shape
    return []

# -------------------------
# Filtering helpers
# -------------------------

def extract_coords(feature: Dict[str, Any]) -> Tuple[Any, Any]:
    """
    Try to pull (lat, lon) from common shapes:
      - flat: { 'lat': .., 'lon': .. } or { 'latitude': .., 'longitude': .. }
      - flat x/y (accept if looks like lon/lat degrees)
      - nested dicts under 'location', 'geo', 'properties'
    Returns (lat, lon) or (None, None).
    """
    def _from_dict(d: Dict[str, Any]) -> Tuple[Any, Any]:
        if not isinstance(d, dict):
            return (None, None)
        lat = d.get("lat") or d.get("latitude") or d.get("y")
        lon = d.get("lon") or d.get("longitude") or d.get("x")
        try:
            if lat is not None and lon is not None:
                lat_f = float(lat)
                lon_f = float(lon)
                if -90 <= lat_f <= 90 and -180 <= lon_f <= 180:
                    return (lat_f, lon_f)
        except Exception:
            pass
        return (None, None)

    # flat
    lat, lon = _from_dict(feature)
    if lat is not None:
        return (lat, lon)
    # nested
    for k in NESTED_CANDIDATES:
        lat, lon = _from_dict(feature.get(k, {}))
        if lat is not None:
            return (lat, lon)
    return (None, None)

def is_in_bbox(lat: Any, lon: Any, bbox: Tuple[float, float, float, float]) -> bool:
    if lat is None or lon is None:
        return False
    min_lat, min_lon, max_lat, max_lon = bbox
    return (min_lat <= lat <= max_lat) and (min_lon <= lon <= max_lon)

def feature_texts(feature: Dict[str, Any]):
    """Yield relevant texts from common fields and nested candidates."""
    # Top-level fields
    for f in COMMON_TEXT_FIELDS:
        v = feature.get(f)
        if isinstance(v, (str, int)):
            yield str(v)
        elif isinstance(v, dict):
            for sub in ("road", "name", "route", "title", "description", "locationDescription"):
                sv = v.get(sub)
                if isinstance(sv, (str, int)):
                    yield str(sv)
    # Nested groups
    for k in NESTED_CANDIDATES:
        v = feature.get(k)
        if isinstance(v, dict):
            for sub in ("road", "name", "route", "title", "description", "locationDescription"):
                sv = v.get(sub)
                if isinstance(sv, (str, int)):
                    yield str(sv)

def text_hits_any(text: str, compiled_patterns: List[re.Pattern]) -> bool:
    if not text:
        return False
    for pat in compiled_patterns:
        if pat.search(text):
            return True
    return False

def route_matches(feature: Dict[str, Any], route_numbers: set) -> bool:
    """
    Detect 190/210 in route-ish fields while avoiding false positives like '2100 S'.
    Accepts SR-210, UT 190, State Route 210, etc.
    """
    token_pattern = re.compile(r"\b(1|2)\d{2}\b")  # three-digit tokens
    for txt in feature_texts(feature):
        # Exact token match
        for tok in route_numbers:
            if re.search(rf"\b{re.escape(tok)}\b", txt):
                return True
        # SR/UT/State Route forms
        m = re.search(r"\b(SR|UT|State\s*Route)\s*[- ]?\s*(190|210)\b", txt, flags=re.IGNORECASE)
        if m:
            num = m.group(2)
            if num in route_numbers:
                return True
        # Generic 3-digit fallback
        m2 = token_pattern.search(txt)
        if m2 and m2.group(0) in route_numbers:
            return True
    return False

def record_matches_canyon(feature: Dict[str, Any], canyon_key: str) -> bool:
    rule = CANYON_RULES[canyon_key]
    # Route match
    if route_matches(feature, rule["route_numbers"]):
        return True
    # Name-based match
    for txt in feature_texts(feature):
        if text_hits_any(txt, rule["compiled"]):
            return True
    # Coordinate fallback
    lat, lon = extract_coords(feature)
    if is_in_bbox(lat, lon, rule["bbox"]):
        return True
    return False

def filter_both_canyons(records: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    lcc, bcc = [], []
    for r in (records or []):
        if not isinstance(r, dict):
            continue
        l_hit = record_matches_canyon(r, "LCC")
        b_hit = record_matches_canyon(r, "BCC")
        if l_hit:
            lcc.append(r)
        if b_hit:
            bcc.append(r)
    return lcc, bcc

# -------------------------
# Utility: dedupe lists
# -------------------------

def dedupe_by_first_present_key(items: List[Dict[str, Any]], candidate_keys: List[str]) -> List[Dict[str, Any]]:
    """Dedupe items using the first key that exists (e.g., eventId, id, cameraId)."""
    seen = set()
    out = []
    for it in items:
        key_val = None
        for k in candidate_keys:
            if k in it and it[k] is not None:
                key_val = (k, str(it[k]))
                break
        if key_val is None:
            # No suitable key—include it but don't dedupe further
            out.append(it)
            continue
        if key_val in seen:
            continue
        seen.add(key_val)
        out.append(it)
    return out

# -------------------------
# Main processing
# -------------------------

def process_cottonwoods() -> Dict[str, Dict[str, int]]:
    # Fetch
    conditions = get_udot_data("get/roadconditions")
    events     = get_udot_data("get/events")
    cameras    = get_udot_data("get/cameras")

    # Filter
    lcc_cond, bcc_cond = filter_both_canyons(conditions)
    lcc_evts, bcc_evts = filter_both_canyons(events)
    lcc_cams, bcc_cams = filter_both_canyons(cameras)

    # Dedupe by typical keys
    lcc_cond = dedupe_by_first_present_key(lcc_cond, ["id", "conditionId"])
    bcc_cond = dedupe_by_first_present_key(bcc_cond, ["id", "conditionId"])
    lcc_evts = dedupe_by_first_present_key(lcc_evts, ["eventId", "id"])
    bcc_evts = dedupe_by_first_present_key(bcc_evts, ["eventId", "id"])
    lcc_cams = dedupe_by_first_present_key(lcc_cams, ["cameraId", "id"])
    bcc_cams = dedupe_by_first_present_key(bcc_cams, ["cameraId", "id"])

    # Persist
    os.makedirs("data", exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    outputs = {
        "data/LCC_conditions.json": lcc_cond,
        "data/BCC_conditions.json": bcc_cond,
        "data/LCC_events.json": lcc_evts,
        "data/BCC_events.json": bcc_evts,
        "data/LCC_cameras.json": lcc_cams,
        "data/BCC_cameras.json": bcc_cams,
        "data/summary.json": {
            "timestamp_utc": ts,
            "LCC": {"conditions": len(lcc_cond), "events": len(lcc_evts), "cameras": len(lcc_cams)},
            "BCC": {"conditions": len(bcc_cond), "events": len(bcc_evts), "cameras": len(bcc_cams)},
            "source": "UDOT API v2"
        }
    }

    for path, payload in outputs.items():
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)

    # Also write last_run.txt (useful for your existing workflow commit step)
    with open("last_run.txt", "w", encoding="utf-8") as f:
        f.write(f"Last run (UTC): {ts}\n")

    return outputs["data/summary.json"]

def main():
    try:
        summary = process_cottonwoods()
        print(json.dumps(summary, indent=2))
    except Exception as e:
        print(f"[FATAL] {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
