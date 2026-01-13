
#!/usr/bin/env python3
"""
Fetch UDOT traffic data for Cottonwood Canyons:
- Road conditions
- Events
- Cameras
Filters for:
- Little Cottonwood Canyon (SR-210)
- Big Cottonwood Canyon (SR-190)
Writes JSON outputs to ./data and prints summary.
"""

import os
import json
import re
import requests
from datetime import datetime, timezone
from typing import List, Dict, Any, Tuple

# Load API key from environment
API_KEY = os.getenv("UDOT_API_KEY")
BASE_URL = "https://www.udottraffic.utah.gov/api/v2"

if not API_KEY:
    raise ValueError("UDOT_API_KEY not found in environment. Set GitHub secret or .env for local testing.")

# -------------------------
# Canyon filter definitions
# -------------------------
CANYON_RULES = {
    "LCC": {
        "label": "Little Cottonwood Canyon",
        "route_numbers": {"210"},
        "name_patterns": [
            r"\bLittle\s+Cottonwood\b",
            r"\bLCC\b",
            r"\bSR[-\s]?210\b",
            r"\bUT[-\s]?210\b",
            r"\bAlta\b",
            r"\bSnowbird\b",
        ],
        "bbox": (40.53, -111.82, 40.62, -111.61),
    },
    "BCC": {
        "label": "Big Cottonwood Canyon",
        "route_numbers": {"190"},
        "name_patterns": [
            r"\bBig\s+Cottonwood\b",
            r"\bBCC\b",
            r"\bSR[-\s]?190\b",
            r"\bUT[-\s]?190\b",
            r"\bBrighton\b",
            r"\bSolitude\b",
        ],
        "bbox": (40.58, -111.80, 40.70, -111.55),
    },
}

for k in CANYON_RULES:
    CANYON_RULES[k]["compiled"] = [re.compile(p, re.IGNORECASE) for p in CANYON_RULES[k]["name_patterns"]]

COMMON_TEXT_FIELDS = ["route", "road", "roadway", "name", "title", "description", "locationDescription"]
NESTED_CANDIDATES = ["location", "properties"]

# -------------------------
# API fetch
# -------------------------
def get_udot_data(endpoint: str) -> List[Dict[str, Any]]:
    url = f"{BASE_URL}/{endpoint}?key={API_KEY}&format=json"
    print(f"[DEBUG] Fetching: {url}")
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    data = r.json()
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for v in data.values():
            if isinstance(v, list):
                return v
        return [data]
    return []

# -------------------------
# Filtering helpers
# -------------------------
def extract_coords(feature: Dict[str, Any]) -> Tuple[Any, Any]:
    def _from_dict(d):
        if not isinstance(d, dict):
            return (None, None)
        lat = d.get("lat") or d.get("latitude") or d.get("y")
        lon = d.get("lon") or d.get("longitude") or d.get("x")
        try:
            if lat and lon:
                lat_f, lon_f = float(lat), float(lon)
                if -90 <= lat_f <= 90 and -180 <= lon_f <= 180:
                    return (lat_f, lon_f)
        except:
            pass
        return (None, None)

    lat, lon = _from_dict(feature)
    if lat: return (lat, lon)
    for k in NESTED_CANDIDATES:
        lat, lon = _from_dict(feature.get(k, {}))
        if lat: return (lat, lon)
    return (None, None)

def is_in_bbox(lat, lon, bbox):
    if lat is None or lon is None: return False
    min_lat, min_lon, max_lat, max_lon = bbox
    return min_lat <= lat <= max_lat and min_lon <= lon <= max_lon

def feature_texts(feature):
    for f in COMMON_TEXT_FIELDS:
        v = feature.get(f)
        if isinstance(v, str): yield v
    for k in NESTED_CANDIDATES:
        v = feature.get(k)
        if isinstance(v, dict):
            for sub in COMMON_TEXT_FIELDS:
                if isinstance(v.get(sub), str):
                    yield v[sub]

def record_matches_canyon(feature, canyon_key):
    rule = CANYON_RULES[canyon_key]
    # Route match
    for txt in feature_texts(feature):
        if re.search(rf"\b{canyon_key == 'LCC' and '210' or '190'}\b", txt):
            return True
        if any(pat.search(txt) for pat in rule["compiled"]):
            return True
    # Coordinate fallback
    lat, lon = extract_coords(feature)
    return is_in_bbox(lat, lon, rule["bbox"])

def filter_both_canyons(records):
    lcc, bcc = [], []
    for r in records:
        if record_matches_canyon(r, "LCC"): lcc.append(r)
        if record_matches_canyon(r, "BCC"): bcc.append(r)
    return lcc, bcc

# -------------------------
# Main process
# -------------------------
def process_cottonwoods():
    conditions = get_udot_data("RoadConditions")
    events = get_udot_data("Events")
    cameras = get_udot_data("Cameras")

    lcc_cond, bcc_cond = filter_both_canyons(conditions)
    lcc_evts, bcc_evts = filter_both_canyons(events)
    lcc_cams, bcc_cams = filter_both_canyons(cameras)

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
