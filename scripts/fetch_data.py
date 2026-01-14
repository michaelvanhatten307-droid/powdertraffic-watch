import requests
import os
import json
from datetime import datetime

API_KEY = os.getenv("UDOT_API_KEY")
BASE_URL = "https://www.udottraffic.utah.gov/api/v2"

def get_udot_data(endpoint):
    url = f"{BASE_URL}/{endpoint}?key={API_KEY}&format=json"
    try:
        response = requests.get(url)
        # Try CamelCase if lowercase fails (Common UDOT quirk)
        if response.status_code == 404:
            alt_endpoint = "".join([word.capitalize() for word in endpoint.split('/')])
            url = f"{BASE_URL}/{alt_endpoint}?key={API_KEY}&format=json"
            response = requests.get(url)
            
        response.raise_for_status()
        data = response.json()
        print(f"📡 API Success: Found {len(data)} total items for '{endpoint}'")
        return data
    except Exception as e:
        print(f"❌ API Error for {endpoint}: {e}")
        return []

def process_canyons():
    # Endpoints based on UDOT v2 help docs
    conditions_data = get_udot_data("roadconditions")
    alert_data = get_udot_data("alerts")
    camera_data = get_udot_data("cameras")
    plow_data = get_udot_data("servicevehicles")

    bcc_status = "UNKNOWN"
    lcc_status = "UNKNOWN"
    
    # Check Road Conditions
    for i in conditions_data:
        roadway = str(i.get("RoadwayName", ""))
        # We use flexible matching: if '190' is in 'SR-190' or 'Big Cottonwood'
        if "190" in roadway or "Big Cottonwood" in roadway:
            bcc_status = i.get("RoadCondition", "UNKNOWN")
        if "210" in roadway or "Little Cottonwood" in roadway:
            lcc_status = i.get("RoadCondition", "UNKNOWN")

    # Filter Alerts
    canyon_alerts = [
        {"text": a.get("FullText"), "severity": a.get("Severity")}
        for a in alert_data 
        if any(term in str(a.get("FullText", "")) for term in ["190", "210", "Cottonwood"])
    ]

    # Filter Cameras
    canyon_cameras = [
        {"name": c.get("Name"), "lat": c.get("Latitude"), "lng": c.get("Longitude"), "url": c.get("ViewUrl")}
        for c in camera_data 
        if any(term in str(c.get("RoadwayName", "")) for term in ["190", "210"])
    ]

    # Filter Plows
    canyon_plows = [
        {"id": p.get("VehicleNumber"), "lat": p.get("Latitude"), "lng": p.get("Longitude"), "status": p.get("CurrentStatus")}
        for p in plow_data 
        if any(term in str(p.get("RouteName", "")) for term in ["190", "210"])
    ]

    return {
        "last_updated": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "bcc_status": bcc_status,
        "lcc_status": lcc_status,
        "alerts": canyon_alerts,
        "cameras": canyon_cameras,
        "plows": canyon_plows
    }

if __name__ == "__main__":
    results = process_canyons()
    with open("data.json", "w") as f:
        json.dump(results, f, indent=2)
    print("✅ data.json written.")
