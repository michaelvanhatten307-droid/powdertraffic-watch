import json
import asyncio
from datetime import datetime
from playwright.async_api import async_playwright

# REAL GOOGLE MAPS LINKS (Mouth of Canyon to Resort)
# I have provided the coordinate-based URLs for maximum accuracy
ROUTES = {
    "lcc": "https://www.google.com/maps/dir/40.5730,-111.7761/40.5888,-111.6370/",
    "bcc": "https://www.google.com/maps/dir/40.6200,-111.7890/40.5990,-111.5830/"
}

async def get_google_time(browser, url):
    # Spoof a real browser to avoid "Are you a robot?" checks
    context = await browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    page = await context.new_page()
    
    try:
        # 1. Faster Navigation: wait for the DOM, not the heavy map images
        await page.goto(url, wait_until="domcontentloaded", timeout=45000)
        
        # 2. Handle Google Consent Popup (if it appears in the Cloud)
        try:
            for btn_text in ["Accept all", "I agree", "Agree"]:
                button = page.get_by_role("button", name=btn_text)
                if await button.is_visible():
                    await button.click()
                    break
        except:
            pass

        # 3. New aggressive selectors for the travel time duration
        selectors = [
            'div.Fk3vS',                 # Desktop primary time
            'span.fontHeadlineSmall',    # Sidebar primary time
            'div[aria-label*="minute"]', # Accessibility label
            '.kdS68b',                   # Mobile duration
            '.U39P9e'                    # List view duration
        ]
        
        for selector in selectors:
            try:
                # Wait for the specific element to pop in
                element = await page.wait_for_selector(selector, timeout=12000)
                if element:
                    text = await element.inner_text()
                    # We need "min" or "hr" in the text to know it's a time
                    if "min" in text or "hr" in text:
                        # Clean "24 min" -> "24"
                        return text.split('\n')[0].replace('min', '').replace('s', '').strip()
            except:
                continue
                
        return "--"
    except Exception as e:
        print(f"SCRAPE_ERROR for {url}: {e}")
        return "--"
    finally:
        await page.close()

async def main():
    async with async_playwright() as p:
        # Launch with stability flags for GitHub Actions
        browser = await p.chromium.launch(
            headless=True, 
            args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage']
        )
        
        print("LOG: STARTING_DRIVE_TIME_SYNC...")
        lcc_val = await get_google_time(browser, ROUTES["lcc"])
        bcc_val = await get_google_time(browser, ROUTES["bcc"])
        
        try:
            # 1. Read existing data (protect your cameras!)
            with open('data.json', 'r') as f:
                data = json.load(f)
            
            # 2. Force Create/Update the drive_times block
            if 'drive_times' not in data:
                data['drive_times'] = {}
                
            data['drive_times']['lcc'] = lcc_val
            data['drive_times']['bcc'] = bcc_val
            
            # 3. Update the global timestamp
            data['metadata']['last_updated'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # 4. Save back to data.json with nice formatting
            with open('data.json', 'w') as f:
                json.dump(data, f, indent=4)
            
            print(f"SYNC_SUCCESS: LCC({lcc_val}) BCC({bcc_val}) merged into data.json")
            
        except Exception as e:
            print(f"JSON_FILE_ERROR: {e}")
            
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
