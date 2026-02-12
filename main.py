import json
import time
from playwright.sync_api import sync_playwright

BASE_URL = "http://www.fawanews.sc/"
OUTPUT_FILE = "fawanews_links.json"

# --- SMART FILTER SETTINGS ---
# Ei word gulo thakle bujhbo eta NEWS, Khela na. Tai click korbo na.
NEWS_KEYWORDS = [
    "announce", "admit", "difficult", "retirement", "chief", 
    "report", "confirm", "interview", "says", "warns", "exit", 
    "driver", "reserve"
]

# Ei word gulo thakle bujhbo eta KHELA.
MATCH_KEYWORDS = [
    " vs ", " v ", "cup", "league", "atp", "wta", "golf", 
    "sport", "cricket", "football", "tennis", "tour"
]

def run():
    with sync_playwright() as p:
        print("[-] Launching Smart Browser...")
        
        # Anti-detection setup
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
        
        for attempt in range(1, 4): # Max 3 tries
            try:
                page.goto(BASE_URL, timeout=35000, wait_until="domcontentloaded")
                # Body load holei hobe
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

        # --- PART 2: GET ALL MATCHES (NO LIMIT + NEWS FILTER) ---
        print("[-] Scanning for matches (Ignoring News)...")
        
        matches_to_scan = []
        try:
            page.wait_for_timeout(3000) # Link gulo render hote time dilam
            all_links = page.locator("a").all()
        except:
            all_links = []

        print(f"[-] Total links found: {len(all_links)}")

        for link in all_links:
            try:
                text = link.text_content().strip()
                href = link.get_attribute("href")
                
                # Basic check
                if not href or len(text) < 4: continue
                if "domain" in text.lower(): continue # Domain sell ads bad
                
                text_lower = text.lower()
                
                # --- LOGIC 1: NEWS FILTER (BAD WORDS) ---
                # Jodi news er word thake, bad dau
                if any(bad_word in text_lower for bad_word in NEWS_KEYWORDS):
                    continue
                
                # --- LOGIC 2: LENGTH CHECK ---
                # News headline sadharonoto onek boro hoy. Khela (Team A vs Team B) choto hoy.
                # 65 character er beshi holei news hobar chance beshi
                if len(text) > 65:
                    continue

                # --- LOGIC 3: MATCH CONFIRMATION ---
                # "vs" thakle confirm khela. Othoba Match keyword thakle nabo.
                is_match = False
                
                if " vs " in text_lower or " v " in text_lower:
                    is_match = True
                elif any(k in text_lower for k in MATCH_KEYWORDS):
                    is_match = True
                
                # Jodi match hoy, list e add koro
                if is_match:
                    full_url = href if href.startswith("http") else BASE_URL.rstrip("/") + "/" + href.lstrip("/")
                    matches_to_scan.append({"Title": text, "Link": full_url})
                    
            except:
                continue

        # Duplicate remove
        unique_matches = list({v['Link']: v for v in matches_to_scan}.values())
        
        # EKHANE KONO LIMIT NEI (Sob match nibe)
        print(f"[-] Processing {len(unique_matches)} confirmed matches (News skipped).")

        # --- PART 3: EXTRACT LINKS ---
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
                match_page.goto(match['Link'], timeout=25000, wait_until="domcontentloaded")
                time.sleep(6) # Player load time
                
                # Click logic
                try:
                    # JS click (Best for overlay)
                    match_page.evaluate("document.elementFromPoint(640, 360).click()")
                except:
                    try:
                        match_page.mouse.click(640, 360)
                    except:
                        pass
                
                # Wait for link
                for _ in range(8):
                    if m3u8_found: break
                    time.sleep(1)
                
                if m3u8_found:
                    print(f"   -> [FOUND] Success")
                    
                    # --- NEW FORMATTING HERE ---
                    
                    # 1. ID Generate
                    match_id = str(len(final_data) + 1)
                    
                    # 2. Rivels (Title theke --- bad deoa)
                    raw_title = match['Title']
                    if "---" in raw_title:
                        rivels = raw_title.split("---")[0].strip()
                    else:
                        rivels = raw_title
                    
                    # 3. Link (Referer add kora)
                    formatted_link = f"{m3u8_found}|referer=http://www.fawanews.sc/"

                    # Data entry
                    entry = {
                        "Id": match_id,
                        "Rivels": rivels,
                        "Title": raw_title, # Full title jemon chilo
                        "Link": formatted_link
                    }
                    final_data.append(entry)
                else:
                    print("   -> [FAIL] No video link.")
            
            except Exception as e:
                print(f"   -> [ERROR] {e}")
            finally:
                match_page.close()

        # --- PART 4: SAVE ---
        with open(OUTPUT_FILE, "w") as f:
            json.dump(final_data, f, indent=4)
        
        if final_data:
            print(f"[DONE] Saved {len(final_data)} matches to {OUTPUT_FILE}")
        else:
            print("[DONE] No live streams found.")
            # Khali file banano jate error na hoy
            with open(OUTPUT_FILE, "w") as f:
                json.dump([], f)

        browser.close()

if __name__ == "__main__":
    run()
