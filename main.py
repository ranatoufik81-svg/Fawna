import json
import os
import time
from playwright.sync_api import sync_playwright

BASE_URL = "http://www.fawanews.sc/"
OUTPUT_FILE = "fawanews_links.json"
MATCH_LIMIT = 5

def run():
    with sync_playwright() as p:
        print("[-] Launching Browser...")
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            ignore_https_errors=True
        )
        page = context.new_page()

        # --- PART 1: LOAD PAGE WITH LIMIT (NO INFINITE LOOP) ---
        print(f"[-] Accessing: {BASE_URL}")
        site_loaded = False
        
        # Max 15 attempts (Approx 2-3 mins max)
        for attempt in range(1, 16):
            try:
                print(f"[*] Attempt {attempt}/15...")
                page.goto(BASE_URL, timeout=30000, wait_until="domcontentloaded")
                
                # Take a screenshot to debug later
                page.screenshot(path=f"debug_attempt_{attempt}.png")

                # Logic: Blocked page e link kom thake. Main page e onek link thake.
                link_count = page.locator("a").count()
                
                # Jodi "Sports News" lekha thake OTHOBA 20 tar beshi link thake
                if page.locator("text=Sports News").is_visible() or link_count > 20:
                    print(f"[SUCCESS] Main page loaded! (Found {link_count} links)")
                    site_loaded = True
                    break
                else:
                    print(f"[INFO] Still blocked/loading. Links found: {link_count}. Retrying...")
                    time.sleep(5)
            except Exception as e:
                print(f"[ERROR] {e}")
                time.sleep(5)

        if not site_loaded:
            print("[FATAL] Could not bypass the block after 15 attempts.")
            # Save final screenshot
            page.screenshot(path="final_fail_state.png")
            browser.close()
            # Force exit so workflow doesn't run extra logic
            return

        # --- PART 2: COLLECT MATCHES ---
        print("[-] Collecting matches...")
        matches_to_scan = []
        all_links = page.locator("a").all()
        keywords = ["vs", "ch ", "ch-", "league", "cup"]

        for link in all_links:
            try:
                text = link.text_content().strip()
                href = link.get_attribute("href")
                if not href or len(text) < 4: continue
                
                # Check keywords
                if any(k in text.lower() for k in keywords) and "domain" not in text.lower():
                    full_url = href if href.startswith("http") else BASE_URL.rstrip("/") + "/" + href.lstrip("/")
                    matches_to_scan.append({"Title": text, "Link": full_url})
            except:
                continue

        # Unique & Limit
        unique_matches = list({v['Link']: v for v in matches_to_scan}.values())
        if len(unique_matches) > MATCH_LIMIT:
            unique_matches = unique_matches[:MATCH_LIMIT]
        
        print(f"[-] Found {len(unique_matches)} matches to process.")

        # --- PART 3: EXTRACT LINKS ---
        final_data = []
        for index, match in enumerate(unique_matches):
            print(f"[{index+1}/{len(unique_matches)}] checking: {match['Title']}")
            page_match = context.new_page()
            m3u8_found = None
            
            def handle(req):
                nonlocal m3u8_found
                if ".m3u8" in req.url and "master" in req.url:
                    m3u8_found = req.url
            
            page_match.on("request", handle)
            
            try:
                page_match.goto(match['Link'], timeout=40000)
                # Wait 15s for video
                for _ in range(15):
                    if m3u8_found: break
                    time.sleep(1)
                
                if m3u8_found:
                    print(f"   -> FOUND: {m3u8_found}")
                    final_data.append({"Title": match['Title'], "Link": m3u8_found})
                else:
                    print("   -> Not found")
                    # Screenshot failure page
                    page_match.screenshot(path=f"fail_match_{index}.png")
            except:
                pass
            finally:
                page_match.close()

        # Save
        if final_data:
            with open(OUTPUT_FILE, "w") as f:
                json.dump(final_data, f, indent=4)
            print("[DONE] Saved data.")
        
        browser.close()

if __name__ == "__main__":
    run()
