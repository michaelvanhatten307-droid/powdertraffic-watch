import json
import requests
from datetime import datetime

# UDOT ArcGIS REST API URL for Canyon Travel Times
UDOT_API_URL = "https://services1.arcgis.com/8v6is9W66B14oN1D/arcgis/rest/services/Canyon_Travel_Times/FeatureServer/0/query"

def get_udot_times():
    params = {
        'where': '1=1',
        'outFields': 'Canyon,TravelTime,RoadCondition', # Adjust based on actual service fields
        'f': 'json'
    }
    
    try:
        response = requests.get(UDOT_API_URL, params=params, timeout=15)
        data = response.json()
        
        times = {"lcc": "--", "bcc": "--"}
        
        # Loop through the features returned by UDOT
        for feature in data.get('features', []):
            attr = feature.get('attributes', {})
            canyon = attr.get('Canyon', '').upper()
            minutes = attr.get('TravelTime', '--')
            
            if 'LITTLE' in canyon:
                times['lcc'] = str(minutes)
            elif 'BIG' in canyon:
                times['bcc'] = str(minutes)
        
        return times
    except Exception as e:
        print(f"UDOT_API_ERROR: {e}")
        return {"lcc": "--", "bcc": "--"}

def main():
    print("LOG: FETCHING_UDOT_DATA...")
    drive_times = get_udot_times()
    
    try:
        # 1. Read existing data.json
        with open('data.json', 'r') as f:
            data = json.load(f)
        
        # 2. Inject UDOT data
        data['drive_times'] = drive_times
        data['metadata']['last_updated'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 3. Save back
        with open('data.json', 'w') as f:
            json.dump(data, f, indent=4)
            
        print(f"SYNC_SUCCESS: LCC({drive_times['lcc']}) BCC({drive_times['bcc']})")
        
    except Exception as e:
        print(f"FILE_ERROR: {e}")

if __name__ == "__main__":
    main()
