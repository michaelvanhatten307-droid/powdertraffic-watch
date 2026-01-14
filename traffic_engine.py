import json
import asyncio
from datetime import datetime
from playwright.async_api import async_playwright

# Google Maps Directions (Mouth of Canyon to Resorts)
# These URLs are pre-configured for the fastest driving route
ROUTES = {
    "lcc": "https://www.google.com/maps/dir/40.5721,-111.7761/Alta+Ski+Area,+Utah/@40.5818,-111.7088,13z/",
    "bcc": "https://www.google.com/maps/dir/40.6196,-111.7892/Brighton+Resort,+Utah/@40.6133,-111.6872,12z/"
}

async def get_google_time(browser, url):
    # Use a high-quality User Agent so Google doesn't think we are a basic bot
    context = await browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
    )
    page = await context.new_page()
    try:
        await page.goto(url, wait_until="networkidle", timeout=30000)
        
        # This selector targets the "Primary" time result in the sidebar (e.g. "24 min")
        # We wait for the element that contains the word "min" or "hr"
        selector = 'span:has-text("min"), span:has-text("hr")'
        await page.wait_for_selector(selector, timeout=15000)
        
        # Get all matching elements and pick the first one (the fastest route)
        time_elements = await page.query_selector_all(selector)
        if time_elements:
            time_text = await time_elements[0].inner_text()
            # Clean up: "24 min" -> "24"
            return time_text.split(' ')[0]
        return "--"
    except Exception as e:
        print(f"SCRAPE_ERROR: {e}")
        return "--"
    finally:
        await page.close()

async def main():
    async with async_playwright() as p:
        # Launch Chromium (Cloud-compatible settings)
        browser = await p.chromium.launch(headless=True)
        
        print("LOG: INITIATING_TRAFFIC_SCRAPE...")
        lcc_val = await get_google_time(browser, ROUTES["lcc"])
        bcc_val = await get_google_time(browser, ROUTES["bcc"])
        
        # Load the existing data.json
        try:
            with open('data.json', 'r') as f:
                data = json.load(f)
            
            # Update the drive_times object
            data['drive_times'] = {
                "lcc": lcc_val,
                "bcc": bcc_val
            }
            
            # Record the update timestamp
            data['metadata']['last_updated'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Save back to the root
            with open('data.json', 'w') as f:
                json.dump(data, f, indent=4)
            
            print(f"SUCCESS: LCC({lcc_val}m) BCC({bcc_val}m)")
            
        except Exception as e:
            print(f"JSON_FILE_ERROR: {e}")
            
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
