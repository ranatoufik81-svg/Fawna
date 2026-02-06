import json
import os
import time
from playwright.sync_api import sync_playwright

BASE_URL = "http://www.fawanews.sc/"
OUTPUT_FILE = "fawanews_links.json"
MATCH_LIMIT = 10 # Check top 10 matches

def run():
    with sync_playwright() as p:
        print("[-] Launching Browser...")
        # Headless=True rakhun, github actions e visual dorkar nei
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            ignore_https_errors=True,
            viewport={"width": 1280, "height": 720} # Screen size fix kora holo jate click thik jaygay pore
        )
        page = context.new_page()

        # --- PART 1: ACCESS SITE ---
        print(f"[-] Accessing: {BASE_URL}")
        site_loaded = False
        
        for attempt in range(1, 16):
            try:
                page.goto(BASE_URL, timeout=60000, wait_until="domcontentloaded")
                
                # Check based on your screenshot content
                if page.locator("text=Sports News").is_visible():
                    print(f"[SUCCESS] Main page loaded on attempt {attempt}")
                    site_loaded = True
                    break
                else:
                    print(f"[INFO] Blocked/Loading... Retrying ({attempt}/15)")
                    time.sleep(3)
            except Exception as e:
                print(f"[RETRY] Error: {e}")
                time.sleep(3)

        if not site_loaded:
            print("[FATAL] Could not load main page.")
            browser.close()
            return

        # --- PART 2: GET MATCH LINKS ---
        print("[-] Collecting matches...")
        matches_to_scan = []
        all_links = page.locator("a").all()
        # Common keywords for matches
        keywords = ["vs", "ch ", "ch-", "league", "cup", "sport"]

        for link in all_links:
            try:
                text = link.text_content().strip()
                href = link.get_attribute("href")
                if not href or len(text) < 4: continue
                
                # Filter logic
                text_lower = text.lower()
                if any(k in text_lower for k in keywords) and "domain" not in text_lower:
                    full_url = href if href.startswith("http") else BASE_URL.rstrip("/") + "/" + href.lstrip("/")
                    matches_to_scan.append({"Title": text, "Link": full_url})
            except:
                continue

        # Remove duplicates
        unique_matches = list({v['Link']: v for v in matches_to_scan}.values())
        
        # Limit processing
        if len(unique_matches) > MATCH_LIMIT:
            unique_matches = unique_matches[:MATCH_LIMIT]
        
        print(f"[-] Found {len(unique_matches)} matches to process.")

        # --- PART 3: EXTRACT LINKS (WITH CLICK ACTION) ---
        final_data = []
        
        for index, match in enumerate(unique_matches):
            print(f"[{index+1}/{len(unique_matches)}] Checking: {match['Title']}")
            
            match_page = context.new_page()
            m3u8_found = None
            
            def handle(req):
                nonlocal m3u8_found
                # Strict 'master' bad diyechi, jekono .m3u8 capture korbe
                if ".m3u8" in req.url:
                    m3u8_found = req.url

            match_page.on("request", handle)
            
            try:
                match_page.goto(match['Link'], timeout=60000, wait_until="domcontentloaded")
                
                # --- NEW: CLICK TO PLAY ---
                # Screen render houar jonno ektu time dei
                time.sleep(5)
                
                # Try 1: Click on generic generic video tag if exists
                try:
                    match_page.locator("video").click(timeout=2000)
                    print("   -> Clicked <video> tag")
                except:
                    pass
                
                # Try 2: Click center of the screen (Universal Play Method)
                # Apnar screenshot e player ta majhkhane ache
                try:
                    match_page.mouse.click(640, 360) # Clicking center of 1280x720 viewport
                    print("   -> Clicked center of screen")
                except:
                    pass
                
                # Wait for network request
                print("   -> Waiting for network...")
                for _ in range(15):
                    if m3u8_found: break
                    time.sleep(1)
                
                if m3u8_found:
                    print(f"   -> [FOUND] {m3u8_found}")
                    final_data.append({"Title": match['Title'], "Link": m3u8_found})
                else:
                    print("   -> [FAIL] Video didn't start or no m3u8.")
            
            except Exception as e:
                print(f"   -> [ERROR] {e}")
            finally:
                match_page.close()

        # --- PART 4: SAVE JSON ---
        if final_data:
            with open(OUTPUT_FILE, "w") as f:
                json.dump(final_data, f, indent=4)
            print(f"[DONE] Success! Saved {len(final_data)} links to {OUTPUT_FILE}")
        else:
            print("[DONE] No links found. Check debug logs.")
            # Create empty file to avoid file not found error
            with open(OUTPUT_FILE, "w") as f:
                json.dump([], f)

        browser.close()

if __name__ == "__main__":
    run()
