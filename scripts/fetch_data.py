import requests
import json
import os
from datetime import datetime

# 1. Setup - This uses the Secret Key you saved in Settings earlier
API_KEY = os.environ.get('UDOT_API_KEY')
DATA_FILE = 'data.json'

def fetch_traffic():
    # This is a placeholder URL - UDOT usually provides a specific 'Traffic Speed' endpoint
    # For now, we will simulate the logic so you can see it work on your site
    print("Connecting to UDOT...")
    
    # In a real scenario, you'd do: response = requests.get(f"URL?key={API_KEY}")
    # Let's create some 'live' looking data for your dashboard
    new_data = {
        "bcc_status": "OPEN",
        "lcc_status": "RESTRICTED",
        "bcc_travel_time": "24 mins",
        "lcc_travel_time": "45 mins",
        "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "message": "UDOT: Traction Law in Effect for LCC."
    }
    
    # Save it to your data.json file
    with open(DATA_FILE, 'w') as f:
        json.dump(new_data, f, indent=4)
    print("Data updated successfully!")

if __name__ == "__main__":
    fetch_traffic()
