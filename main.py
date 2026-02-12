import json
import os
import time
from playwright.sync_api import sync_playwright

BASE_URL = "http://www.fawanews.sc/"
OUTPUT_FILE = "fawanews_links.json"
MATCH_LIMIT = 10 

def run():
    with sync_playwright() as p:
        print("[-] Launching Optimized Browser...")
        
        # FIX 1: Anti-Bot Arguments (Headless mode e site jate block na kore)
        browser = p.chromium.launch(
            headless=True,
            args=[
                '--disable-blink-features=AutomationControlled', # Bot flag off kora
                '--no-sandbox',
                '--disable-setuid-sandbox'
            ]
        )
        
        context = browser.new_context(
            # Latest User Agent
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            ignore_https_errors=True,
            viewport={"width": 1280, "height": 720}
        )
        
        # Script pakda jaoa bondho korar jonno extra settings
        context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        page = context.new_page()

        # --- PART 1: ACCESS SITE ---
        print(f"[-] Accessing: {BASE_URL}")
        site_loaded = False
        
        # FIX 2: Retry Loop reduced from 15 to 3 (Time save hobe)
        for attempt in range(1, 4):
            try:
                # FIX 3: Timeout reduced to 30s
                response = page.goto(BASE_URL, timeout=30000, wait_until="domcontentloaded")
                
                # Check 1: HTTP Status
                if response and response.status > 399:
                    print(f"[INFO] Server returned error {response.status}. Retrying...")
                    time.sleep(2)
                    continue

                # Check 2: Content
                # Kichu site "Sports News" text soriye fele, tai "Home" ba generic text check kora better
                if page.locator("body").is_visible(): 
                    print(f"[SUCCESS] Main page loaded on attempt {attempt}")
                    site_loaded = True
                    break
            except Exception as e:
                print(f"[RETRY] Attempt {attempt} failed: {e}")
                time.sleep(2)

        if not site_loaded:
            print("[FATAL] Could not load main page. Site might be blocking IP.")
            browser.close()
            return

        # --- PART 2: GET MATCH LINKS ---
        print("[-] Collecting matches...")
        matches_to_scan = []
        
        try:
            # Wait slighty for dynamic content
            page.wait_for_timeout(2000)
            all_links = page.locator("a").all()
        except:
            all_links = []

        keywords = ["vs", "ch ", "ch-", "league", "cup", "sport"]

        for link in all_links:
            try:
                text = link.text_content().strip()
                href = link.get_attribute("href")
                if not href or len(text) < 4: continue
                
                text_lower = text.lower()
                if any(k in text_lower for k in keywords) and "domain" not in text_lower:
                    full_url = href if href.startswith("http") else BASE_URL.rstrip("/") + "/" + href.lstrip("/")
                    matches_to_scan.append({"Title": text, "Link": full_url})
            except:
                continue

        unique_matches = list({v['Link']: v for v in matches_to_scan}.values())
        
        if len(unique_matches) > MATCH_LIMIT:
            unique_matches = unique_matches[:MATCH_LIMIT]
        
        print(f"[-] Found {len(unique_matches)} matches to process.")

        # --- PART 3: EXTRACT LINKS ---
        final_data = []
        
        for index, match in enumerate(unique_matches):
            print(f"[{index+1}/{len(unique_matches)}] Checking: {match['Title']}")
            
            match_page = context.new_page()
            m3u8_found = None
            
            def handle(req):
                nonlocal m3u8_found
                url = req.url
                # Filter strict kora holo jate fake link na ase
                if ".m3u8" in url and "favicon" not in url:
                    m3u8_found = url

            match_page.on("request", handle)
            
            try:
                match_page.goto(match['Link'], timeout=30000, wait_until="domcontentloaded")
                
                # Ektu beshi wait kora holo jate player load hoy (Agertay 5 chilo, ekhon 7)
                time.sleep(7)
                
                # Try Click: Center
                try:
                    # Force click (JavaScript diye) jodi overlay thake
                    match_page.evaluate("document.elementFromPoint(640, 360).click()")
                    # Normal mouse click backup
                    match_page.mouse.click(640, 360)
                except:
                    pass
                
                # Network Wait reduced slightly
                for _ in range(10): # 10 seconds max wait per link
                    if m3u8_found: break
                    time.sleep(1)
                
                if m3u8_found:
                    print(f"   -> [FOUND] {m3u8_found}")
                    final_data.append({"Title": match['Title'], "Link": m3u8_found})
                else:
                    print("   -> [FAIL] No m3u8 captured.")
            
            except Exception as e:
                print(f"   -> [ERROR] {e}")
            finally:
                match_page.close()

        # --- PART 4: SAVE JSON ---
        if final_data:
            with open(OUTPUT_FILE, "w") as f:
                json.dump(final_data, f, indent=4)
            print(f"[DONE] Success! Saved {len(final_data)} links.")
        else:
            print("[DONE] No links found.")
            with open(OUTPUT_FILE, "w") as f:
                json.dump([], f)

        browser.close()

if __name__ == "__main__":
    run()
