
#!/usr/bin/env python3
"""
Fetch UDOT traffic data for the Cottonwood Canyons (SR-210 & SR-190)
- Road Conditions (get/roadconditions)
- Events (get/event)
- Cameras (get/cameras)
Filters for Little Cottonwood Canyon (SR-210) and Big Cottonwood Canyon (SR-190),
writes JSON outputs to ./data, and prints a summary for GitHub Actions logs.
"""

import os
import json
import re
import requests
from datetime import datetime, timezone
from typing import List, Dict, Any, Tuple

# -------------------------
# Configuration
# -------------------------

API_KEY = os.getenv("UDOT_API_KEY")
BASE_URL = "https://www.udottraffic.utah.gov/api/v2"

if not API_KEY:
    raise ValueError("UDOT_API_KEY not found in environment. Set the GitHub secret (UDOT_API_KEY).")

# -------------------------
# Canyon rules
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
        # Rough bbox for LCC (Alta–mouth)
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
        # Rough bbox for BCC (Brighton–mouth)
        "bbox": (40.58, -111.80, 40.70, -111.55),
    },
}

for k in CANYON_RULES:
    CANYON_RULES[k]["compiled"] = [re.compile(p, re.IGNORECASE) for p in CANYON_RULES[k]["name_patterns"]]

# Text fields commonly present in UDOT payloads for each endpoint:
RC_TEXT_FIELDS   = ["RoadwayName", "RoadCondition", "WeatherCondition", "Restriction"]   # roadconditions
EVT_TEXT_FIELDS  = ["RoadwayName", "Location", "Description", "EventType", "EventCategory", "Name"]  # event
CAM_TEXT_FIELDS  = ["Roadway", "Location"]                                               # cameras
NESTED_CANDIDATES = ["location", "properties", "geo"]  # defensive (rarely needed)

# -------------------------
# API fetch util
# -------------------------

def get_udot_data(endpoint: str) -> List[Dict[str, Any]]:
    """
    Fetch a list of records from UDOT API v2.
    endpoint should be one of: 'get/roadconditions', 'get/event', 'get/cameras'
    """
    url = f"{BASE_URL}/{endpoint}?key={API_KEY}&format=json"  # <-- IMPORTANT: use '&' not '&amp;'
    print(f"[DEBUG] GET {url}")
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    data = r.json()

    # Normalize returned shape to a list of dicts
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        # Some endpoints may wrap the list under a key; return the first list found
        for v in data.values():
            if isinstance(v, list):
                return v
        return [data]
    return []

# -------------------------
# Filtering helpers
# -------------------------

def extract_coords(feature: Dict[str, Any]) -> Tuple[Any, Any]:
    """Try to extract latitude/longitude from common fields."""
    # Cameras/events usually have 'Latitude'/'Longitude'
    lat = feature.get("Latitude")
    lon = feature.get("Longitude")
    try:
        if lat is not None and lon is not None:
            lat_f = float(lat); lon_f = float(lon)
            if -90 <= lat_f <= 90 and -180 <= lon_f <= 180:
                return (lat_f, lon_f)
    except Exception:
        pass
    # Fallback: nested dict attempt
    for k in NESTED_CANDIDATES:
        v = feature.get(k)
        if isinstance(v, dict):
            lat = v.get("lat") or v.get("latitude") or v.get("y")
            lon = v.get("lon") or v.get("longitude") or v.get("x")
            try:
                if lat is not None and lon is not None:
                    lat_f = float(lat); lon_f = float(lon)
                    if -90 <= lat_f <= 90 and -180 <= lon_f <= 180:
                        return (lat_f, lon_f)
            except Exception:
                pass
    return (None, None)

def is_in_bbox(lat, lon, bbox):
    if lat is None or lon is None:
        return False
    min_lat, min_lon, max_lat, max_lon = bbox
    return min_lat <= lat <= max_lat and min_lon <= lon <= max_lon

def feature_texts(feature: Dict[str, Any], endpoint: str):
    """Yield relevant texts based on endpoint type."""
    if endpoint == "get/roadconditions":
        fields = RC_TEXT_FIELDS
    elif endpoint == "get/event":
        fields = EVT_TEXT_FIELDS
    elif endpoint == "get/cameras":
        fields = CAM_TEXT_FIELDS
    else:
        fields = list(feature.keys())  # last resort

    for f in fields:
        v = feature.get(f)
        if isinstance(v, (str, int)):
            yield str(v)

def route_token_match(txt: str, route_numbers: set) -> bool:
    """Recognize 210 or 190 as standalone tokens and common forms like SR-210."""
    if not txt:
        return False
    # exact number token
    for tok in route_numbers:
        if re.search(rf"\b{re.escape(tok)}\b", txt, flags=re.IGNORECASE):
            return True
    # forms like SR-210 / UT 190 / State Route 210
    if re.search(r"\b(SR|UT|State\s*Route)\s*[- ]?\s*(190|210)\b", txt, flags=re.IGNORECASE):
        return True
    return False

def record_matches_canyon(feature: Dict[str, Any], canyon_key: str, endpoint: str) -> bool:
    rule = CANYON_RULES[canyon_key]
    # Route match
    for txt in feature_texts(feature, endpoint):
        if route_token_match(txt, rule["route_numbers"]):
            return True
        if any(pat.search(txt) for pat in rule["compiled"]):
            return True
    # Coordinate fallback (events/cameras usually have Lat/Lon)
    lat, lon = extract_coords(feature)
    if is_in_bbox(lat, lon, rule["bbox"]):
        return True
    return False

def filter_both_canyons(records: List[Dict[str, Any]], endpoint: str):
    lcc, bcc = [], []
    for r in records or []:
        if not isinstance(r, dict):
            continue
        l_hit = record_matches_canyon(r, "LCC", endpoint)
        b_hit = record_matches_canyon(r, "BCC", endpoint)
        if l_hit: lcc.append(r)
        if b_hit: bcc.append(r)
    return lcc, bcc

def dedupe_by_keys(items: List[Dict[str, Any]], candidate_keys: List[str]) -> List[Dict[str, Any]]:
    seen = set(); out = []
    for it in items:
        k = None
        for key in candidate_keys:
            if key in it and it[key] is not None:
                k = (key, str(it[key])); break
        if k is None:
            out.append(it); continue
        if k in seen:
            continue
        seen.add(k); out.append(it)
    return out

# -------------------------
# Main process
# -------------------------

def process_cottonwoods():
    # Use documented endpoints:
    # - Road Conditions: get/roadconditions
    # - Events: get/event
    # - Cameras: get/cameras
    conditions = get_udot_data("get/roadconditions")
    events     = get_udot_data("get/event")
    cameras    = get_udot_data("get/cameras")

    lcc_cond, bcc_cond = filter_both_canyons(conditions, "get/roadconditions")
    lcc_evts, bcc_evts = filter_both_canyons(events, "get/event")
    lcc_cams, bcc_cams = filter_both_canyons(cameras, "get/cameras")

    # Dedupe using typical keys
    lcc_cond = dedupe_by_keys(lcc_cond, ["Id", "ID", "conditionId"])
    bcc_cond = dedupe_by_keys(bcc_cond, ["Id", "ID", "conditionId"])
    lcc_evts = dedupe_by_keys(lcc_evts, ["ID", "Id", "eventId"])
    bcc_evts = dedupe_by_keys(bcc_evts, ["ID", "Id", "eventId"])
    lcc_cams = dedupe_by_keys(lcc_cams, ["Id", "cameraId"])
    bcc_cams = dedupe_by_keys(bcc_cams, ["Id", "cameraId"])

    # Persist outputs
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

    with open("last_run.txt", "w", encoding="utf-8") as f:
        f.write(f"Last run (UTC): {ts}\n")

    print(json.dumps(outputs["data/summary.json"], indent=2))

if __name__ == "__main__":
    process_cottonwoods()
