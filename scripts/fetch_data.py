
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
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error fetching {endpoint}: {e}")
        return []

def filter_by_route(data, routes=["SR-210", "SR-190"], key="Route"):
    return [item for item in data if any(r in str(item.get(key, "")) for r in routes)]

def process_canyons():
    # Road Conditions
    conditions = filter_by_route(get_udot_data("get/roadconditions"))
    bcc_status = next((c.get("Status") for c in conditions if "SR-190" in c.get("Route", "")), "UNKNOWN")
    lcc_status = next((c.get("Status") for c in conditions if "SR-210" in c.get("Route", "")), "UNKNOWN")

    # Drive Times
    drive_times = filter_by_route(get_udot_data("get/drivetimes"))
    bcc_time = next((str(c.get("CurrentTravelTime")) for c in drive_times if "SR-190" in c.get("Route", "")), "N/A")
    lcc_time = next((str(c.get("CurrentTravelTime")) for c in drive_times if "SR-210" in c.get("Route", "")), "N/A")

    # Snowplows
    snowplows = filter_by_route(get_udot_data("get/snowplows"), key="RouteName")
    plow_list = [
        {
            "VehicleID": p.get("VehicleID"),
            "Latitude": p.get("Latitude"),
            "Longitude": p.get("Longitude"),
            "Status": p.get("Status")
        }
        for p in snowplows
    ]

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
    print("✅ data.json updated successfully!")
