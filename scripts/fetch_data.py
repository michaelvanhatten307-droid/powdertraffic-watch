
import requests
import os

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
    """Filter UDOT data by route names."""
    return [item for item in data if any(r in str(item.get(key, "")) for r in routes)]

def process_canyons():
    # 1. Road Conditions
    conditions = filter_by_route(get_udot_data("get/roadconditions"))

    # 2. Drive Times
    drive_times = filter_by_route(get_udot_data("get/drivetimes"))

    # 3. Cameras
    cameras = filter_by_route(get_udot_data("get/cameras"))

    # 4. Snowplows
    snowplows = filter_by_route(get_udot_data("get/snowplows"), key="RouteName")

    # 5. Events & Alerts
    events = filter_by_route(get_udot_data("get/events"))
    alerts = filter_by_route(get_udot_data("get/alerts"))

    # Combine results
    canyon_data = {
        "road_conditions": conditions,
        "drive_times": drive_times,
        "cameras": cameras,
        "snowplows": snowplows,
        "events": events,
        "alerts": alerts
    }

    return canyon_data

if __name__ == "__main__":
    data = process_canyons()
    print("Filtered Canyon Data:")
    print(data)
