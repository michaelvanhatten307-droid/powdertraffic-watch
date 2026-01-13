import requests
import json
import os

API_KEY = os.environ.get('0a63926dde414fa2b2477ce76aa134de')
# Official UDOT Base URL from your research
BASE_URL = "https://www.udottraffic.utah.gov/api/v2"

def get_udot_data(endpoint):
    url = f"{BASE_URL}/{endpoint}?key={API_KEY}&format=json"
    try:
        response = requests.get(url)
        return response.json()
    except:
        return []

def process_canyons():
    # 1. Fetch Road Conditions
    conditions = get_udot_data("get/roadconditions")
    
    # 2. Fetch Alerts/Events
    alerts = get_udot_data("get/events")
    
    # 3. Fetch Cameras
    cameras = get_udot_data("get/cameras")

    # Filter logic for SR-210 and SR-190 goes here...
    # (We will write this tomorrow once your key arrives!)
