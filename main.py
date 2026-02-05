import json
import os
import time
import random
from playwright.sync_api import sync_playwright

# --- CONFIGURATION ---
BASE_URL = "http://www.fawanews.sc/"
OUTPUT_FILE = "fawanews_links.json"

def run():
    with sync_playwright() as p:
        # Browser launch settings
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        )
        page = context.new_page()

        # Variable to store the m3u8 link
        found_m3u8 = None

        # --- STEP 1: SMART REFRESH LOGIC (Bypass Blocking) ---
        print(f"[-] Trying to access: {BASE_URL}")
        
        site_loaded = False
        max_retries = 10  # Maximum 10 times refresh korbe
        
        for attempt in range(max_retries):
            try:
                page.goto(BASE_URL, timeout=30000)
                
                # Check jodi "Sports News" lekha ta page e thake (Screenshot onujayi)
                if page.get_by_text("Sports News").is_visible():
                    print(f"[SUCCESS] Site loaded successfully on attempt {attempt + 1}")
                    site_loaded = True
                    break
                else:
                    print(f"[INFO] Blocked page detected. Refreshing... (Attempt {attempt + 1})")
                    time.sleep(3) # 3 seconds wait before refresh
            except Exception as e:
                print(f"[RETRY] Error loading page: {e}. Retrying...")
                time.sleep(2)

        if not site_loaded:
            print("[FAIL] Could not bypass the block page after multiple attempts.")
            browser.close()
            return

        # --- STEP 2: NETWORK LISTENER SETUP ---
        # Video play korle network tab e ja asbe ta capture korbe
        def handle_request(request):
            nonlocal found_m3u8
            url = request.url
            if ".m3u8" in url:
                print(f"[FOUND] M3U8 Link: {url}")
                found_m3u8 = url

        page.on("request", handle_request)

        # --- STEP 3: CLICK ON A MATCH ---
        try:
            print("[-] Searching for a match to click...")
            
            # Screenshot onujayi "CH 1" ba "vs" lekha ache emon link khujbe
            # Amra prothom "CH" (Channel) ba Match link e click korbo
            
            # Option A: Try to find text containing "CH" (like CH 1, CH 2)
            match_element = page.locator("text=CH").first
            
            # Option B: If A fails, click the first available link in the list
            if not match_element.is_visible():
                 match_element = page.locator("a[href*='match']").first 

            if match_element.is_visible():
                match_name = match_element.text_content().strip()
                print(f"[-] Clicking on match/channel: {match_name}")
                
                # Handling new tab if it opens in new window
                with context.expect_page() as new_page_info:
                    match_element.click()
                
                # Switch to the new player page
                player_page = new_page_info.value
                player_page.wait_for_load_state()
                print("[-] Player page loaded. Waiting for video...")
                
                # Attach listener to new page as well
                player_page.on("request", handle_request)
                
                # Wait for video to start and m3u8 to generate
                time.sleep(15) 
                
            else:
                print("[ERROR] No clickable match found.")

        except Exception as e:
            print(f"[ERROR] Interaction failed: {e}")

        # --- STEP 4: SAVE DATA ---
        if found_m3u8:
            save_data(found_m3u8)
        else:
            print("[FAIL] No M3U8 link found. Maybe video didn't play?")

        browser.close()

def save_data(link):
    data = []
    if os.path.exists(OUTPUT_FILE):
        try:
            with open(OUTPUT_FILE, "r") as f:
                data = json.load(f)
        except:
            data = []

    new_entry = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "source": "FawaNews",
        "link": link
    }
    data.append(new_entry)

    with open(OUTPUT_FILE, "w") as f:
        json.dump(data, f, indent=4)
    print(f"[SAVED] Link saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    run()
