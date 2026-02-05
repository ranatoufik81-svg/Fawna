import json
import os
import time
from playwright.sync_api import sync_playwright

# --- CONFIGURATION ---
BASE_URL = "http://www.fawanews.sc/"
OUTPUT_FILE = "fawanews_links.json"
MATCH_LIMIT = 5  # Sudhu matro Prothom 5 ta match check korbe

def run():
    with sync_playwright() as p:
        print("[-] Initializing Browser...")
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        
        page = context.new_page()
        
        # --- PART 1: UNLIMITED WAIT FOR HOME PAGE (Refresh Logic) ---
        print(f"[-] Trying to connect to: {BASE_URL}")
        
        attempt = 0
        site_loaded = False
        
        while not site_loaded:
            attempt += 1
            try:
                # Timeout '0' mane infinite wait for loading
                page.goto(BASE_URL, timeout=0, wait_until="domcontentloaded")
                
                # Check jodi "Sports News" ba "Schedule" lekha thake
                content_check = page.locator("text=Sports News").or_(page.locator("text=Schedule"))
                
                if content_check.is_visible():
                    print(f"[SUCCESS] Main Page Loaded after {attempt} attempts!")
                    site_loaded = True
                    break
                else:
                    # Block page ba onno kichu asle refresh
                    print(f"[INFO] Blocked/Loading... Refreshing (Attempt {attempt})")
                    time.sleep(5) # 5 seconds rest niye abar refresh
                    
            except Exception as e:
                print(f"[RETRY] Connection error. Retrying... (Attempt {attempt})")
                time.sleep(5)

        # --- PART 2: COLLECT TOP 5 MATCHES ---
        print("[-] Collecting match list...")
        time.sleep(5) # Page ta valo vabe render hote time dilam
        
        all_links = page.locator("a").all()
        matches_to_scan = []
        
        # Keyword filter (Ei word gulo thaklei match hisebe count hobe)
        keywords = ["vs", "ch ", "ch-", "league", "cup", "sport"]

        for link in all_links:
            try:
                text = link.text_content().strip()
                href = link.get_attribute("href")
                
                if not href or len(text) < 4: continue
                
                text_lower = text.lower()
                is_match = any(k in text_lower for k in keywords)
                
                # Banner link gulo bad dewar jonno
                is_not_banner = "domain" not in text_lower and "fake" not in text_lower
                
                if is_match and is_not_banner:
                    # Full URL banano
                    full_url = href if href.startswith("http") else BASE_URL.rstrip("/") + "/" + href.lstrip("/")
                    matches_to_scan.append({"Title": text, "Link": full_url})
            except:
                continue

        # Remove Duplicates
        unique_matches = list({v['Link']: v for v in matches_to_scan}.values())
        
        # --- APPLY LIMIT (TOP 5) ---
        # Jodi match 5 tar beshi thake, kete 5 ta korbe. Kom thakle ja ache tai.
        if len(unique_matches) > MATCH_LIMIT:
            print(f"[-] Found {len(unique_matches)} matches. Taking TOP {MATCH_LIMIT} for testing.")
            unique_matches = unique_matches[:MATCH_LIMIT]
        else:
            print(f"[-] Found {len(unique_matches)} matches.")

        # --- PART 3: EXTRACT M3U8 (Patiently) ---
        final_data = []
        
        for index, match in enumerate(unique_matches):
            print(f"\n[{index+1}/{len(unique_matches)}] Processing: {match['Title']}")
            
            match_page = context.new_page()
            m3u8_found = None

            # Network Listener
            def handle_request(request):
                nonlocal m3u8_found
                if ".m3u8" in request.url and "master" in request.url:
                    m3u8_found = request.url

            match_page.on("request", handle_request)

            try:
                # Match page e dhuklam
                match_page.goto(match['Link'], timeout=60000, wait_until="domcontentloaded")
                
                # Video load houar jonno 20 seconds wait korbo (No Rush)
                print("   -> Waiting for video/network...")
                for _ in range(20): 
                    if m3u8_found: break
                    time.sleep(1)
                
                if m3u8_found:
                    print(f"   -> [SUCCESS] Link Found!")
                    final_data.append({
                        "Title": match['Title'],
                        "Link": m3u8_found
                    })
                else:
                    print("   -> [FAIL] No m3u8 link generated.")
            
            except Exception as e:
                print(f"   -> [ERROR] {e}")
            
            finally:
                match_page.close()

        # --- PART 4: SAVE TO JSON ---
        if final_data:
            with open(OUTPUT_FILE, "w") as f:
                json.dump(final_data, f, indent=4)
            print(f"\n[DONE] Saved {len(final_data)} matches to {OUTPUT_FILE}")
        else:
            print("\n[DONE] No links extracted.")

        browser.close()

if __name__ == "__main__":
    run()
