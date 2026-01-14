import requests
import os
import json
from datetime import datetime

API_KEY = os.getenv("UDOT_API_KEY")
BASE_URL = "https://www.udottraffic.utah.gov/api/v2"

def get_udot_data(endpoint):
    # Removed the '/' between get and the endpoint name based on common UDOT API patterns
    url = f"{BASE_URL}/{endpoint}?key={API_KEY}&format=json"
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error fetching {endpoint}: {e}")
        return []

def process_canyons():
    # 1. Road Conditions (using 'getroadconditions')
    conditions_data = get_udot_data("getroadconditions")
    
    # We look for SR-190 (BCC) and SR-210 (LCC) inside "RoadwayName"
    bcc_status = "UNKNOWN"
    lcc_status = "UNKNOWN"
    
    for item in conditions_data:
        road_name = str(item.get("RoadwayName", ""))
        if "SR-190" in road_name:
            bcc_status = item.get("RoadCondition", "UNKNOWN")
        if "SR-210" in road_name:
            lcc_status = item.get("RoadCondition", "UNKNOWN")

    # 2. Drive Times (Endpoint is usually 'getdrivetimes')
    # Note: If this still 404s, UDOT may require a specific MapLayer ID
    drive_data = get_udot_data("getdrivetimes")
    bcc_time = "N/A"
    lcc_time = "N/A"
    
    for item in drive_data:
        # Drive times usually use 'Label' or 'RouteName'
        label = str(item.get("Label", item.get("RouteName", "")))
        if "190" in label:
            bcc_time = f"{item.get('CurrentTravelTime', 'N/A')} mins"
        if "210" in label:
            lcc_time = f"{item.get('CurrentTravelTime', 'N/A')} mins"

    # 3. Snowplows (Endpoint is usually 'getsnowplows')
    plow_data = get_udot_data("getsnowplows")
    plow_list = []
    for p in plow_data:
        # Check if the plow is on the canyon routes
        route = str(p.get("RouteName", ""))
        if "SR-190" in route or "SR-210" in route:
            plow_list.append({
                "VehicleID": p.get("VehicleID"),
                "Latitude": p.get("Latitude"),
                "Longitude": p.get("Longitude"),
                "Status": p.get("Status", "Active")
            })

    # Build final JSON
    canyon_data = {
        "bcc_status": bcc_status,
        "lcc_status": lcc_status,
        "bcc_travel_time": bcc_time,
        "lcc_travel_time": lcc_time,
        "last_updated": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "plows": plow_list
    }

    return canyon_data

if __name__ == "__main__":
    data = process_canyons()
    with open("data.json", "w") as f:
        json.dump(data, f, indent=2)
    print("✅ data.json updated successfully with real API keys!")
