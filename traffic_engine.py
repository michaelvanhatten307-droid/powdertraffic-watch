import json
import asyncio
from datetime import datetime
from playwright.async_api import async_playwright

# Exact Google Maps Directions: Park & Ride Lot -> Resort Base
ROUTES = {
    "lcc": "https://www.google.com/maps/dir/Little+Cottonwood+Park+%26+Ride,+UT/Alta+Ski+Area,+UT",
    "bcc": "https://www.google.com/maps/dir/Big+Cottonwood+Canyon+Park+%26+Ride,+UT/Brighton+Resort,+UT"
}

async def get_google_time(browser, url):
    context = await browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    page = await context.new_page()
    
    try:
        # Navigate and wait for network to settle
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        
        # Handle the common Google 'Consent' or 'Accept all' pop-up
        try:
            accept_button = page.get_by_role("button", name="Accept all")
            if await accept_button.is_visible():
                await accept_button.click()
                await page.wait_for_load_state("networkidle")
        except:
            pass

       # selectors list:
        selectors = [
            'div.Fk3vS',                 # Desktop layout primary time
            'span.fontHeadlineSmall',    # Sidebar layout primary time
            '.kdS68b',                   # Mobile-style duration
            'div[aria-label*="minute"]', # Accessibility label
            'div.section-directions-trip-duration',
            '.U39P9e'                    # Directions list duration
        ]
        
        for selector in selectors:
            try:
                element = await page.wait_for_selector(selector, timeout=7000)
                if element:
                    text = await element.inner_text()
                    # Example cleanup: "24 min" -> "24" or "1 hr 5 min" -> "65"
                    if "min" in text or "hr" in text:
                        clean_time = text.split('\n')[0].replace('min', '').strip()
                        return clean_time
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
        browser = await p.chromium.launch(headless=True)
        lcc_val = await get_google_time(browser, ROUTES["lcc"])
        bcc_val = await get_google_time(browser, ROUTES["bcc"])
        
        try:
            with open('data.json', 'r') as f:
                data = json.load(f)
            
            # This ensures the key exists before we try to write to it
            if 'drive_times' not in data:
                data['drive_times'] = {}
                
            data['drive_times']['lcc'] = lcc_val
            data['drive_times']['bcc'] = bcc_val
            data['metadata']['last_updated'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            with open('data.json', 'w') as f:
                json.dump(data, f, indent=4)
            
            print(f"MERGE_SUCCESS: LCC:{lcc_val} BCC:{bcc_val}")
        except Exception as e:
            print(f"MERGE_FAILED: {e}")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
