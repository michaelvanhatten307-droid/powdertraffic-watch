import requests
import os
import json
from datetime import datetime

# Configuration
API_KEY = os.getenv("UDOT_API_KEY")
BASE_URL = "https://www.udottraffic.utah.gov/api/v2"

def get_udot_data(endpoint):
    """
    Fetches data from the UDOT REST API using the verified /get/ path.
    """
    # Using the verified lowercase path structure
    url = f"{BASE_URL}/get/{endpoint}?key={API_KEY}&format=json"
    try:
        response = requests.get(url, timeout=30)
        
        if response.status_code == 403:
            print(f"⚠️ 403 Forbidden: Your key lacks permissions for '{endpoint}'.")
            return []
        
        response.raise_for_status()
        data = response.json()
        print(f"📡 API Success: Found {len(data)} total items for '{endpoint}'")
        return data
    except Exception as e:
        print(f"❌ Error fetching {endpoint}: {e}")
        return []

def process_canyons():
    """
    Processes the raw UDOT data into a clean JSON format for the canyon dashboard.
    """
    # 1. Fetch data from all relevant endpoints
    conditions_data = get_udot_data("roadconditions")
    camera_data = get_udot_data("cameras")
    plow_data = get_udot_data("servicevehicles") 
    alert_data = get_udot_data("alerts")

    # 2. Road Conditions (BCC & LCC Status)
    bcc_status = "UNKNOWN"
    lcc_status = "UNKNOWN"
    for i in conditions_data:
        roadway = str(i.get("RoadwayName", ""))
        condition = i.get("RoadCondition", "UNKNOWN")
        if "SR-190" in roadway:
            bcc_status = condition
        if "SR-210" in roadway:
            lcc_status = condition

    # 3. Filter Cameras
    # Grabs coordinates and images/video feeds for canyon locations
    canyon_cameras = []
    for c in camera_data:
        road = str(c.get("RoadwayName", ""))
        if "SR-190" in road or "SR-210" in road:
            canyon_cameras.append({
                "id": c.get("Id"),
                "name": c.get("Name"),
                "lat": c.get("Latitude"),
                "lng": c.get("Longitude"),
                "view_url": c.get("ViewUrl"),
                "route": "BCC" if "SR-190" in road else "LCC"
            })

    # 4. Filter Snowplows (Service Vehicles)
    # Only populates when plows are active with GPS enabled
    canyon_plows = []
    for p in plow_data:
        route = str(p.get("RouteName", ""))
        if "SR-190" in route or "SR-210" in route:
            canyon_plows.append({
                "vehicle_id": p.get("VehicleNumber"),
                "lat": p.get("Latitude"),
                "lng": p.get("Longitude"),
                "status": p.get("CurrentStatus", "Active"),
                "speed": p.get("Speed", 0),
                "heading": p.get("Heading", 0),
                "route": "BCC" if "SR-190" in route else "LCC"
            })

    # 5. Filter Alerts
    # Captures traction laws, closures, and avalanche control
    canyon_alerts = []
    for a in alert_data:
        text = str(a.get("FullText", ""))
        # Search for canyon keywords in the alert body
        if any(term in text for term in ["SR-190", "SR-210", "Big Cottonwood", "Little Cottonwood"]):
            canyon_alerts.append({
                "id": a.get("Id"),
                "headline": a.get("Headline"),
                "text": text,
                "severity": a.get("Severity"), # Minor, Major, etc.
                "start": a.get("StartTime")
            })

    # Construct the final data object
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
    
    # Save to data.json for the frontend to consume
    with open("data.json", "w") as f:
        json.dump(final_results, f, indent=2)
    
    print(f"✅ Update complete at {final_results['metadata']['last_updated']}")
    print(f"   - {len(final_results['cameras'])} Cameras Found")
    print(f"   - {len(final_results['plows'])} Active Plows Found")
    print(f"   - {len(final_results['alerts'])} Active Alerts Found")
