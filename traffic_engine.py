import json
import asyncio
from datetime import datetime
from playwright.async_api import async_playwright

# Google Maps Directions: Mouth of Canyon -> Top of Resort
ROUTES = {
    "lcc": "https://www.google.com/maps/dir/Little+Cottonwood+Canyon+Park+%26+Ride/Alta+Ski+Area",
    "bcc": "https://www.google.com/maps/dir/Big+Cottonwood+Canyon+Park+%26+Ride/Brighton+Resort"
}

async def get_google_time(browser, url):
    # Setup context with a standard desktop User Agent
    context = await browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    page = await context.new_page()
    
    try:
        # Navigate to the route
        await page.goto(url, wait_until="networkidle", timeout=60000)
        
        # 1. Handle Google's Consent/Cookie Popup if it appears
        try:
            # Targets the 'Accept all' button commonly found in EU/US cloud IPs
            buttons = page.get_by_role("button")
            consent_button = buttons.filter(has_text="Accept all")
            if await consent_button.is_visible():
                await consent_button.click()
                await page.wait_for_load_state("networkidle")
        except:
            pass

        # 2. Extract Travel Time
        # We try multiple selectors because Google Maps layout can vary by region/IP
        selectors = [
            'span.fontHeadlineSmall', # Common for primary time
            '.U39P9e',                # Directions pane duration
            'div[aria-label*="minutes"]', 
            'div[aria-label*="hour"]'
        ]
        
        for selector in selectors:
            try:
                element = await page.wait_for_selector(selector, timeout=8000)
                if element:
                    text = await element.inner_text()
                    # Example: "24 min" or "1 hr 5 min"
                    if "min" in text or "hr" in text:
                        # Return just the cleaned string (e.g., "24" or "1 hr 5")
                        return text.split('\n')[0].replace('min', '').strip()
            except:
                continue
                
        return "--"
    except Exception as e:
        print(f"SCRAPE_ERROR: {e}")
        return "--"
    finally:
        await page.close()

async def main():
    async with async_playwright() as p:
        # Launching with specific arguments to ensure it runs on GitHub's Linux servers
        browser = await p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-setuid-sandbox'])
        
        print("LOG: INITIATING_TRAFFIC_SCRAPE...")
        lcc_val = await get_google_time(browser, ROUTES["lcc"])
        bcc_val = await get_google_time(browser, ROUTES["bcc"])
        
        # Load, Update, and Save data.json
        try:
            with open('data.json', 'r') as f:
                data = json.load(f)
            
            # Inject new drive times
            data['drive_times'] = {
                "lcc": lcc_val,
                "bcc": bcc_val
            }
            
            # Update the global timestamp
            data['metadata']['last_updated'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            with open('data.json', 'w') as f:
                json.dump(data, f, indent=4)
            
            print(f"SUCCESS: LCC({lcc_val}m) BCC({bcc_val}m) updated in data.json")
            
        except Exception as e:
            print(f"JSON_FILE_ERROR: {e}")
            
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
