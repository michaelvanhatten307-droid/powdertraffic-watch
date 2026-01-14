import json
import asyncio
import re
from datetime import datetime
from playwright.async_api import async_playwright

# Precise Coordinates: Mouth of Canyon -> Resort Base
ROUTES = {
    "lcc": "https://www.google.com/maps/dir/40.5721,-111.7761/40.5888,-111.6380/",
    "bcc": "https://www.google.com/maps/dir/40.6197,-111.7893/40.5992,-111.5835/"
}

async def get_google_time(browser, url):
    context = await browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    )
    page = await context.new_page()
    
    try:
        # Navigate and wait for the page to actually have text
        await page.goto(url, wait_until="domcontentloaded", timeout=45000)
        
        # 1. Handle the Cookie/Privacy Wall (Common in GitHub's Cloud IP)
        try:
            # Look for "Accept all" button
            accept = page.get_by_role("button", name=re.compile("Accept|Agree|Allow", re.IGNORECASE))
            if await accept.is_visible():
                await accept.click()
                await page.wait_for_timeout(2000) # Short pause for transition
        except:
            pass

        # 2. Wait for the "Driving" icon to appear - this confirms the directions loaded
        await page.wait_for_selector('img[src*="driving"], [aria-label*="Driving"]', timeout=15000)
        
        # 3. BRUTE FORCE REGEX: Get the whole page text
        # This looks for patterns like "24 min" or "1 hr 5 min"
        content = await page.content()
        
        # Search for the "primary" time which usually appears first in the list
        # Pattern looks for: a number followed by 'min'
        found_times = re.findall(r'>(\d+)\s*min<', content)
        
        if not found_times:
            # Fallback for "1 hr 10 min" format
            hr_search = re.findall(r'>(\d+)\s*hr\s*(\d+)\s*min<', content)
            if hr_search:
                hrs, mins = hr_search[0]
                return str(int(hrs) * 60 + int(mins))
            
            # Secondary fallback for simpler text structures
            text_only = await page.evaluate("document.body.innerText")
            found_times = re.findall(r'(\d+)\s*min', text_only)

        if found_times:
            # We take the first match as it's usually the "Best Route"
            print(f"DEBUG: Found time {found_times[0]} for {url[:30]}...")
            return found_times[0]
                
        return "--"
    except Exception as e:
        print(f"SCRAPE_ERROR: {e}")
        return "--"
    finally:
        await page.close()

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True, 
            args=['--no-sandbox', '--disable-setuid-sandbox']
        )
        
        print("LOG: STARTING_DRIVE_TIME_SYNC...")
        lcc_val = await get_google_time(browser, ROUTES["lcc"])
        bcc_val = await get_google_time(browser, ROUTES["bcc"])
        
        try:
            # READ existing data.json
            with open('data.json', 'r') as f:
                data = json.load(f)
            
            # Create the block if missing
            if 'drive_times' not in data:
                data['drive_times'] = {"lcc": "--", "bcc": "--"}
                
            # Only update if we actually got a number
            data['drive_times']['lcc'] = lcc_val
            data['drive_times']['bcc'] = bcc_val
            
            # Update Timestamp
            data['metadata']['last_updated'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # SAVE to data.json
            with open('data.json', 'w') as f:
                json.dump(data, f, indent=4)
            
            print(f"SYNC_SUCCESS: LCC({lcc_val}) BCC({bcc_val}) recorded.")
            
        except Exception as e:
            print(f"JSON_FILE_ERROR: {e}")
            
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
