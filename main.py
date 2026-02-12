import json
import time
from playwright.sync_api import sync_playwright

BASE_URL = "http://www.fawanews.sc/"
OUTPUT_FILE = "fawanews_links.json"

# --- SMART FILTER SETTINGS ---
NEWS_KEYWORDS = [
    "announce", "admit", "difficult", "retirement", "chief", 
    "report", "confirm", "interview", "says", "warns", "exit", 
    "driver", "reserve", "statement", "suspension", "injury"
]

MATCH_KEYWORDS = [
    " vs ", " v ", "cup", "league", "atp", "wta", "golf", 
    "sport", "cricket", "football", "tennis", "tour", "nba", 
    "basketball", "race", "prix", "games", "olympic", "match", "live"
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

        # --- PART 2: GET MATCHES (PARENT TEXT LOGIC) ---
        print("[-] Scanning for matches...")
        matches_to_scan = []
        try:
            page.wait_for_timeout(3000)
            all_links = page.locator("a").all()
        except:
            all_links = []

        for link in all_links:
            try:
                # IMPORTANT FIX: Sudhu link er text na niye, tar Parent er text nicchi
                # Jate Bold Text (Team Name) + Small Text (Title) duto e ase.
                parent_element = link.locator("xpath=..")
                full_text = parent_element.inner_text().strip()
                
                href = link.get_attribute("href")
                
                if not href or len(full_text) < 4: continue
                if "domain" in full_text.lower(): continue 
                
                text_lower = full_text.lower()
                
                # News Filter
                if any(bad_word in text_lower for bad_word in NEWS_KEYWORDS):
                    continue
                
                # Match Confirm
                is_match = False
                if " vs " in text_lower or " v " in text_lower:
                    is_match = True
                elif any(k in text_lower for k in MATCH_KEYWORDS):
                    is_match = True
                
                if is_match:
                    # Line split logic (Top line = Rivels, Bottom line = Title)
                    lines = [line.strip() for line in full_text.split('\n') if line.strip()]
                    
                    if len(lines) >= 2:
                        # 1st Line = Team Name (Rivels) - Jemon: Sri Lanka vs Oman --- CH 1
                        rivels_text = lines[0]
                        # 2nd Line = Title - Jemon: Cricket T20 World Cup
                        title_text = lines[1]
                    else:
                        # Jodi ek line thake, tobe otai Rivels, Title hobe "Live Match"
                        rivels_text = lines[0]
                        title_text = "Live Match"

                    full_url = href if href.startswith("http") else BASE_URL.rstrip("/") + "/" + href.lstrip("/")
                    
                    matches_to_scan.append({
                        "Rivels": rivels_text, 
                        "Title": title_text, 
                        "Link": full_url
                    })
            except:
                continue

        # Duplicate remove based on Link
        unique_matches = list({v['Link']: v for v in matches_to_scan}.values())
        print(f"[-] Processing {len(unique_matches)} matches.")

        # --- PART 3: EXTRACT & FORMAT DATA ---
        final_data = []
        
        for index, match in enumerate(unique_matches):
            print(f"[{index+1}/{len(unique_matches)}] Scrape: {match['Rivels']}")
            
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
                time.sleep(6) 
                
                try:
                    match_page.evaluate("document.elementFromPoint(640, 360).click()")
                except:
                    try:
                        match_page.mouse.click(640, 360)
                    except:
                        pass
                
                for _ in range(8):
                    if m3u8_found: break
                    time.sleep(1)
                
                if m3u8_found:
                    print(f"   -> [FOUND] Success")
                    
                    # 1. ID
                    match_id = str(len(final_data) + 1)
                    
                    # 2. Link with Referer
                    formatted_link = f"{m3u8_found}|referer=http://www.fawanews.sc/"

                    # 3. Data Entry (Format Fixed)
                    entry = {
                        "Id": match_id,
                        "Rivels": match['Rivels'], # Screenshot er UPPER BOLD text ekhane ashbe
                        "Title": match['Title'],   # Screenshot er LOWER GREY text ekhane ashbe
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
