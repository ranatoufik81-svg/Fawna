import json
import os
import time
from playwright.sync_api import sync_playwright

# --- CONFIGURATION ---
BASE_URL = "http://www.fawanews.sc/"
OUTPUT_FILE = "fawanews_links.json"

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        
        # --- PART 1: LOAD HOMEPAGE & BYPASS BLOCK ---
        page = context.new_page()
        print(f"[-] Accessing Home: {BASE_URL}")
        
        site_loaded = False
        for attempt in range(1, 11): # 10 times retry
            try:
                page.goto(BASE_URL, timeout=60000, wait_until="domcontentloaded")
                # Check for specific content that indicates success
                if page.locator("text=Sports News").is_visible() or page.locator("text=Schedule").is_visible():
                    print(f"[SUCCESS] Site loaded on attempt {attempt}")
                    site_loaded = True
                    break
                else:
                    print(f"[INFO] Blocked/Loading... Refreshing ({attempt}/10)")
                    time.sleep(3)
            except Exception as e:
                print(f"[RETRY] Error: {e}")
                time.sleep(3)
        
        if not site_loaded:
            print("[FATAL] Could not load the site content.")
            browser.close()
            return

        # --- PART 2: COLLECT ALL MATCH LINKS ---
        print("[-] Collecting match links...")
        # Waiting a bit for lists to render
        time.sleep(3) 
        
        # Get all anchor tags
        all_links = page.locator("a").all()
        matches_to_scan = []

        for link in all_links:
            try:
                text = link.text_content().strip()
                href = link.get_attribute("href")
                
                # FILTER LOGIC:
                # 1. Must have an href
                # 2. Ignore the "Please note" warning banner
                # 3. Must contain typical match keywords like "vs", "CH", "League" or exist inside the main list
                # Since structure is variable, we check if text length is decent and not the warning
                
                if href and "javascript" not in href and len(text) > 5:
                    if "domain changed" in text or "fake" in text:
                        continue # Skip the banner
                    
                    # Logic: Assuming matches have "vs" or "CH" or are just valid links in the body
                    # To be safe, let's take links that likely point to internal match pages
                    # Usually internal links are relative (start with /) or contain the domain
                    
                    # Store Title and Full URL
                    full_url = href if href.startswith("http") else BASE_URL.rstrip("/") + "/" + href.lstrip("/")
                    
                    # Only add if it looks like a match link (simple heuristic)
                    if "http" in full_url:
                        matches_to_scan.append({"Title": text, "Link": full_url})
            except:
                continue

        # Remove duplicates based on URL
        unique_matches = {v['Link']: v for v in matches_to_scan}.values()
        print(f"[-] Found {len(unique_matches)} potential matches.")

        # --- PART 3: VISIT EACH MATCH & EXTRACT M3U8 ---
        final_data = []
        
        for index, match in enumerate(unique_matches):
            print(f"\n[{index+1}/{len(unique_matches)}] Processing: {match['Title']}")
            
            # Open a new page for each match to keep it clean
            match_page = context.new_page()
            m3u8_found = None

            # Listener for this specific page
            def handle_request(request):
                nonlocal m3u8_found
                if ".m3u8" in request.url and "master" in request.url:
                    m3u8_found = request.url

            match_page.on("request", handle_request)

            try:
                # Go to the match link directly
                match_page.goto(match['Link'], timeout=40000, wait_until="domcontentloaded")
                
                # Wait for player/network to trigger
                # Just waiting is enough as you said player loads automatically
                for _ in range(10): # Wait up to 10 seconds
                    if m3u8_found:
                        break
                    time.sleep(1)
                
                if m3u8_found:
                    print(f"   -> [FOUND] {m3u8_found}")
                    final_data.append({
                        "Title": match['Title'],
                        "Link": m3u8_found
                    })
                else:
                    print("   -> [FAIL] No m3u8 detected.")
            
            except Exception as e:
                print(f"   -> [ERROR] {e}")
            
            finally:
                match_page.close()

        # --- PART 4: SAVE JSON ---
        if final_data:
            with open(OUTPUT_FILE, "w") as f:
                json.dump(final_data, f, indent=4)
            print(f"\n[SUCCESS] Saved {len(final_data)} matches to {OUTPUT_FILE}")
        else:
            print("\n[WARN] No m3u8 links were extracted from any match.")

        browser.close()

if __name__ == "__main__":
    run()
