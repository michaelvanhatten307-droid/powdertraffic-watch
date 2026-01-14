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
        await page.goto(url, wait_until="networkidle", timeout=60000)
        
        # Handle the common Google 'Consent' or 'Accept all' pop-up
        try:
            accept_button = page.get_by_role("button", name="Accept all")
            if await accept_button.is_visible():
                await accept_button.click()
                await page.wait_for_load_state("networkidle")
        except:
            pass

        # Selectors for the duration text
        selectors = [
            'span.fontHeadlineSmall', 
            '.U39P9e', 
            'div[aria-label*="minutes"]',
            'div.section-directions-trip-duration'
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
        # Launch browser with arguments for cloud stability
        browser = await p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-setuid-sandbox'])
        
        print("LOG: STARTING_DRIVE_TIME_SYNC...")
        lcc_val = await get_google_time(browser, ROUTES["lcc"])
        bcc_val = await get_google_time(browser, ROUTES["bcc"])
        
        try:
            # 1. READ the existing file (don't lose your camera data!)
            with open('data.json', 'r') as f:
                data = json.load(f)
            
            # 2. UPDATE only the drive_times key
            # If the key doesn't exist yet, this creates it
            data['drive_times'] = {
                "lcc": lcc_val,
                "bcc": bcc_val
            }
            
            # 3. UPDATE metadata timestamp
            data['metadata']['last_updated'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # 4. SAVE everything back to the file
            with open('data.json', 'w') as f:
                json.dump(data, f, indent=4)
            
            print(f"SUCCESS: LCC({lcc_val}) BCC({bcc_val}) recorded.")
            
        except Exception as e:
            print(f"FILE_PROCESS_ERROR: {e}")
            
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
