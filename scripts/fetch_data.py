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
        # Fallback to CamelCase if lowercase fails
        if response.status_code == 404:
            url = f"{BASE_URL}/Get{endpoint.capitalize()}?key={API_KEY}&format=json"
            response = requests.get(url)
        
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"❌ Error fetching {endpoint}: {e}")
        return []

def process_canyons():
    # 1. Road Conditions
    conditions_data = get_udot_data("roadconditions")
    bcc_status = next((i.get("RoadCondition") for i in conditions_data if "SR-190" in str(i.get("RoadwayName"))), "UNKNOWN")
    lcc_status = next((i.get("RoadCondition") for i in conditions_data if "SR-210" in str(i.get("RoadwayName"))), "UNKNOWN")

    # 2. Alerts (New Section)
    # Ref: https://prod-ut.ibi511.com/help/endpoint/alerts
    alert_data = get_udot_data("alerts")
    canyon_alerts = []
    for a in alert_data:
        text = str(a.get("FullText", ""))
        # We search the alert text for canyon identifiers
        if any(id in text for id in ["SR-190", "SR-210", "Big Cottonwood", "Little Cottonwood"]):
            canyon_alerts.append({
                "id": a.get("Id"),
                "headline": a.get("Headline"),
                "text": text,
                "severity": a.get("Severity"), # e.g., "Major", "Minor"
                "start": a.get("StartTime"),
                "category": a.get("CategoryName") # e.g., "Road Weather Alert" or "Incident"
            })

    # 3. Cameras
    camera_data = get_udot_data("cameras")
    canyon_cameras = []
    for cam in camera_data:
        road = str(cam.get("RoadwayName", ""))
        if "SR-190" in road or "SR-210" in road:
            canyon_cameras.append({
                "id": cam.get("Id"),
                "name": cam.get("Name"),
                "lat": cam.get("Latitude"),
                "lng": cam.get("Longitude"),
                "view_url": cam.get("ViewUrl")
            })

    # 4. Snowplows (Service Vehicles)
    plow_data = get_udot_data("servicevehicles")
    plow_list = []
    for p in plow_data:
        route = str(p.get("RouteName", ""))
        if "SR-190" in route or "SR-210" in route:
            plow_list.append({
                "id": p.get("Id"),
                "vehicle_number": p.get("VehicleNumber"),
                "lat": p.get("Latitude"),
                "lng": p.get("Longitude"),
                "speed": p.get("Speed"),
                "heading": p.get("Heading"),
                "plow_status": p.get("CurrentStatus")
            })

    return {
        "last_updated": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "bcc_status": bcc_status,
        "lcc_status": lcc_status,
        "alerts": canyon_alerts,
        "cameras": canyon_cameras,
        "plows": plow_list
    }

if __name__ == "__main__":
    data = process_canyons()
    with open("data.json", "w") as f:
        json.dump(data, f, indent=2)
    print(f"✅ Success! Found {len(data['alerts'])} alerts, {len(data['cameras'])} cameras, and {len(data['plows'])} plows.")
