import json
import time
from playwright.sync_api import sync_playwright

BASE_URL = "http://www.fawanews.sc/"
OUTPUT_FILE = "fawanews_links.json"

# --- SMART FILTER SETTINGS ---
# Ei word gulo thakle bujhbo eta NEWS, tai nabo na.
NEWS_KEYWORDS = [
    "announce", "admit", "difficult", "retirement", "chief", 
    "report", "confirm", "interview", "says", "warns", "exit", 
    "driver", "reserve", "statement", "suspension", "injury"
]

# Ei word gulo thakle bujhbo eta KHELA.
MATCH_KEYWORDS = [
    " vs ", " v ", "cup", "league", "atp", "wta", "golf", 
    "sport", "cricket", "football", "tennis", "tour", "nba", 
    "basketball", "race", "prix"
]

def run():
    with sync_playwright() as p:
        print("[-] Launching Browser...")
        
        browser = p.chromium.launch(
            headless=True,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
                '--disable-setuid-sandbox'
            ]
        )
        
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            ignore_https_errors=True,
            viewport={"width": 1280, "height": 720}
        )
        
        page = context.new_page()

        # --- PART 1: ACCESS SITE ---
        print(f"[-] Accessing: {BASE_URL}")
        site_loaded = False
        
        for attempt in range(1, 4):
            try:
                page.goto(BASE_URL, timeout=40000, wait_until="domcontentloaded")
                if page.locator("body").is_visible():
                    print(f"[SUCCESS] Page loaded.")
                    site_loaded = True
                    break
            except Exception as e:
                print(f"[RETRY] Attempt {attempt}: {e}")
                time.sleep(2)

        if not site_loaded:
            print("[FATAL] Site not loading.")
            browser.close()
            return

        # --- PART 2: GET MATCHES (NO LENGTH LIMIT) ---
        print("[-] Scanning for matches...")
        matches_to_scan = []
        try:
            page.wait_for_timeout(3000)
            all_links = page.locator("a").all()
        except:
            all_links = []

        for link in all_links:
            try:
                text = link.text_content().strip()
                href = link.get_attribute("href")
                
                # Basic validation
                if not href or len(text) < 4: continue
                if "domain" in text.lower(): continue 
                
                text_lower = text.lower()
                
                # 1. News Filter (Bad words check)
                if any(bad_word in text_lower for bad_word in NEWS_KEYWORDS):
                    continue
                
                # 2. Match Confirm (Good words check)
                is_match = False
                if " vs " in text_lower or " v " in text_lower:
                    is_match = True
                elif any(k in text_lower for k in MATCH_KEYWORDS):
                    is_match = True
                
                # *NOTE: Length limit removed completely*
                
                if is_match:
                    full_url = href if href.startswith("http") else BASE_URL.rstrip("/") + "/" + href.lstrip("/")
                    matches_to_scan.append({"Title": text, "Link": full_url})
            except:
                continue

        # Remove duplicates
        unique_matches = list({v['Link']: v for v in matches_to_scan}.values())
        print(f"[-] Processing {len(unique_matches)} matches.")

        # --- PART 3: EXTRACT & FORMAT DATA ---
        final_data = []
        
        for index, match in enumerate(unique_matches):
            print(f"[{index+1}/{len(unique_matches)}] Scrape: {match['Title']}")
            
            match_page = context.new_page()
            m3u8_found = None
            
            def handle(req):
                nonlocal m3u8_found
                url = req.url
                if ".m3u8" in url and "favicon" not in url:
                    m3u8_found = url

            match_page.on("request", handle)
            
            try:
                match_page.goto(match['Link'], timeout=30000, wait_until="domcontentloaded")
                time.sleep(6) # Wait for player
                
                # Click logic
                try:
                    match_page.evaluate("document.elementFromPoint(640, 360).click()")
                except:
                    try:
                        match_page.mouse.click(640, 360)
                    except:
                        pass
                
                # Wait for network
                for _ in range(8):
                    if m3u8_found: break
                    time.sleep(1)
                
                if m3u8_found:
                    print(f"   -> [FOUND] Success")
                    
                    # --- JSON FORMATTING ---
                    
                    # 1. Id: Serial Number (1, 2, 3...)
                    match_id = str(len(final_data) + 1)
                    
                    # 2. Rivels: Title theke "---" er porer onsho bad deoa
                    raw_title = match['Title']
                    if "---" in raw_title:
                        rivels = raw_title.split("---")[0].strip()
                    else:
                        rivels = raw_title
                        
                    # 3. Title: Full title jemon ache temon e thakbe
                    full_title = raw_title 

                    # 4. Link: With referer
                    formatted_link = f"{m3u8_found}|referer=http://www.fawanews.sc/"

                    entry = {
                        "Id": match_id,
                        "Rivels": rivels,
                        "Title": full_title,
                        "Link": formatted_link
                    }
                    final_data.append(entry)
                else:
                    print("   -> [FAIL] No video link.")
            
            except Exception as e:
                print(f"   -> [ERROR] {e}")
            finally:
                match_page.close()

        # --- PART 4: SAVE JSON ---
        with open(OUTPUT_FILE, "w") as f:
            json.dump(final_data, f, indent=4)
        
        if final_data:
            print(f"[DONE] Saved {len(final_data)} matches to {OUTPUT_FILE}")
        else:
            print("[DONE] No live streams found.")
            with open(OUTPUT_FILE, "w") as f:
                json.dump([], f)

        browser.close()

if __name__ == "__main__":
    run()
