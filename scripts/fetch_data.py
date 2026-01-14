import requests
import os
import json
from datetime import datetime

API_KEY = os.getenv("UDOT_API_KEY")
# Ensure there is no trailing slash here
BASE_URL = "https://www.udottraffic.utah.gov/api/v2"

def get_udot_data(endpoint):
    # The URL structure must be exactly: base/get/resource
    url = f"{BASE_URL}/get/{endpoint}?key={API_KEY}&format=json"
    try:
        response = requests.get(url)
        if response.status_code == 403:
            print(f"⚠️ 403 Forbidden for {endpoint}. Check UDOT portal for permissions.")
            return []
        response.raise_for_status()
        data = response.json()
        print(f"📡 Found {len(data)} items for {endpoint}")
        return data
    except Exception as e:
        print(f"❌ Error for {endpoint}: {e}")
        return []

def process_canyons():
    # Endpoints confirmed by UDOT documentation format
    conditions_data = get_udot_data("roadconditions")
    camera_data = get_udot_data("cameras")
    plow_data = get_udot_data("snowplows")  # or 'servicevehicles'
    alert_data = get_udot_data("alerts")

    bcc_status, lcc_status = "UNKNOWN", "UNKNOWN"
    
    # Process Road Conditions
    for i in conditions_data:
        roadway = str(i.get("RoadwayName", ""))
        if "SR-190" in roadway:
            bcc_status = i.get("RoadCondition", "UNKNOWN")
        if "SR-210" in roadway:
            lcc_status = i.get("RoadCondition", "UNKNOWN")

    # Filter Cameras
    cameras = [
        {"name": c.get("Name"), "lat": c.get("Latitude"), "lng": c.get("Longitude"), "url": c.get("ViewUrl")}
        for c in camera_data if any(r in str(c.get("RoadwayName", "")) for r in ["SR-190", "SR-210"])
    ]

    # Filter Snowplows
    plows = [
        {"id": p.get("VehicleNumber"), "lat": p.get("Latitude"), "lng": p.get("Longitude"), "status": p.get("CurrentStatus")}
        for p in plow_data if any(r in str(p.get("RouteName", "")) for r in ["SR-190", "SR-210"])
    ]

    # Filter Alerts
    alerts = [
        {"text": a.get("FullText"), "severity": a.get("Severity")}
        for a in alert_data if any(r in str(a.get("FullText", "")) for r in ["SR-190", "SR-210", "Big Cottonwood", "Little Cottonwood"])
    ]

    return {
        "last_updated": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "bcc_status": bcc_status,
        "lcc_status": lcc_status,
        "alerts": alerts,
        "cameras": cameras,
        "plows": plows
    }

if __name__ == "__main__":
    results = process_canyons()
    with open("data.json", "w") as f:
        json.dump(results, f, indent=2)
    print("✅ data.json update complete.")
