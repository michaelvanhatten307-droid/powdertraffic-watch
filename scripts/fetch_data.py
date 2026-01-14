import requests
import os
import json
from datetime import datetime

API_KEY = os.getenv("UDOT_API_KEY")
BASE_URL = "https://www.udottraffic.utah.gov/api/v2"

def get_udot_data(endpoint):
    url = f"{BASE_URL}/get/{endpoint}?key={API_KEY}&format=json"
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        data = response.json()
        print(f"📡 Found {len(data)} total items for '{endpoint}'")
        return data
    except Exception as e:
        print(f"❌ Error fetching {endpoint}: {e}")
        return []

def process_canyons():
    conditions_data = get_udot_data("roadconditions")
    camera_data = get_udot_data("cameras")
    plow_data = get_udot_data("servicevehicles") 
    alert_data = get_udot_data("alerts")

    bcc_status, lcc_status = "UNKNOWN", "UNKNOWN"
    
    # 1. Road Conditions (Normalizing to Title Case for the Dashboard)
    for i in conditions_data:
        road = str(i.get("RoadwayName", i.get("Roadway", "")))
        condition = str(i.get("RoadCondition", "UNKNOWN")).title()
        if any(x in road for x in ["SR-190", "SR190", "Big Cottonwood"]):
            bcc_status = condition
        if any(x in road for x in ["SR-210", "SR210", "Little Cottonwood"]):
            lcc_status = condition

    # 2. Filter Cameras (Fixing the Null URL issue)
    canyon_cameras = []
    for c in camera_data:
        search_blob = f"{c.get('Roadway', '')} {c.get('Name', '')} {c.get('Location', '')}"
        
        # Check if it's one of our canyons
        route = None
        if any(x in search_blob for x in ["SR-190", "SR190", "Big Cottonwood"]):
            route = "BCC"
        elif any(x in search_blob for x in ["SR-210", "SR210", "Little Cottonwood"]):
            route = "LCC"
            
        if route:
            # Reach into the 'Views' list to get the actual image URL
            views = c.get("Views", [])
            image_url = views[0].get("Url") if views else None
            
            canyon_cameras.append({
                "id": c.get("Id"),
                "name": str(c.get("Name", c.get("Location"))).strip(),
                "lat": c.get("Latitude"),
                "lng": c.get("Longitude"),
                "url": image_url, # Now should be a real https link
                "route": route
            })

    # 3. Filter Snowplows
    canyon_plows = []
    for p in plow_data:
        route_name = str(p.get("RouteName", ""))
        if any(x in route_name for x in ["190", "210"]):
            canyon_plows.append({
                "id": p.get("VehicleNumber"),
                "lat": p.get("Latitude"),
                "lng": p.get("Longitude"),
                "status": p.get("CurrentStatus", "Active"),
                "speed": p.get("Speed", 0),
                "route": "BCC" if "190" in route_name else "LCC"
            })

    # 4. Filter Alerts
    canyon_alerts = []
    for a in alert_data:
        text = str(a.get("FullText", ""))
        if any(x in text for x in ["SR-190", "SR-210", "Big Cottonwood", "Little Cottonwood"]):
            canyon_alerts.append({
                "text": text,
                "severity": a.get("Severity"),
                "start": a.get("StartTime")
            })

    return {
        "metadata": {
            "last_updated": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "status": "success"
        },
        "canyons": {
            "bcc": {"status": bcc_status, "route_id": "SR-190"},
            "lcc": {"status": lcc_status, "route_id": "SR-210"}
        },
        "alerts": canyon_alerts,
        "cameras": canyon_cameras,
        "plows": canyon_plows
    }

if __name__ == "__main__":
    final_results = process_canyons()
    with open("data.json", "w") as f:
        json.dump(final_results, f, indent=2)
    print(f"✅ Update complete. Found {len(final_results['cameras'])} cameras with valid URLs.")
