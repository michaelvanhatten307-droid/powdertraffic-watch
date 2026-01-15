import json
import requests
from datetime import datetime

# Official UDOT Canyon Travel Time Service
UDOT_GIS_URL = "https://services1.arcgis.com/8v6is9W66B14oN1D/arcgis/rest/services/Canyon_Travel_Times/FeatureServer/0/query"

def fetch_udot_times():
    params = {
        'where': "1=1", # Get all segments to be safe
        'outFields': 'Route_Segment,Current_Travel_Time',
        'f': 'json'
    }
    
    try:
        response = requests.get(UDOT_GIS_URL, params=params, timeout=20)
        data = response.json()
        
        times = {"lcc": "--", "bcc": "--"}
        
        for feature in data.get('features', []):
            attrs = feature['attributes']
            segment = attrs.get('Route_Segment', '')
            time_val = attrs.get('Current_Travel_Time', '--')

            # Search for the "Full Canyon" strings
            if "9000 S to Alta" in segment:
                times['lcc'] = str(time_val)
            elif "9000 S to Brighton" in segment:
                times['bcc'] = str(time_val)
                
        return times
    except Exception as e:
        print(f"GIS_ERROR: {e}")
        return {"lcc": "--", "bcc": "--"}

def main():
    new_times = fetch_udot_times()
    try:
        with open('data.json', 'r') as f:
            data = json.load(f)
        
        data['drive_times'] = new_times
        data['metadata']['last_updated'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with open('data.json', 'w') as f:
            json.dump(data, f, indent=4)
        print(f"LOG: Saved {new_times}")
    except Exception as e:
        print(f"FILE_ERROR: {e}")

if __name__ == "__main__":
    main()
