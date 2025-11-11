# python scripts/scarper.py -s "Астана Зона отдыха" -t 50 --timeout 120 --headless False

"""
Robust Google Maps scraper using Playwright.

Features:
- safe parsing of rating strings like "4.3-звездочные"
- safe parsing of reviews counts like "123 отзыва"
- max items limit and max duration (seconds)
- CLI options: search, total, timeout, headless, wait (per-card wait)
- saves CSV and XLSX into output/
- prints progress and errors

Usage:
python3 scarper.py -s "Астана Зона отдыха" -t 100 --timeout 180 --headless True --wait 3
"""

from playwright.sync_api import sync_playwright
from dataclasses import dataclass, asdict, field
import pandas as pd
import argparse
import os
import re
import time
from typing import Tuple

# ---------- Data classes ----------
@dataclass
class Business:
    name: str = ""
    address: str = ""
    website: str = ""
    phone_number: str = ""
    reviews_count: int = None
    reviews_average: float = None
    latitude: float = None
    longitude: float = None
    raw_url: str = ""

@dataclass
class BusinessList:
    business_list: list[Business] = field(default_factory=list)
    save_at: str = "output"

    def dataframe(self) -> pd.DataFrame:
        # convert dataclass list to dataframe
        return pd.json_normalize((asdict(b) for b in self.business_list), sep="_")

    def save_to_excel(self, filename: str) -> str:
        os.makedirs(self.save_at, exist_ok=True)
        path = os.path.join(self.save_at, f"{filename}.xlsx")
        self.dataframe().to_excel(path, index=False)
        return path

    def save_to_csv(self, filename: str) -> str:
        os.makedirs(self.save_at, exist_ok=True)
        path = os.path.join(self.save_at, f"{filename}.csv")
        self.dataframe().to_csv(path, index=False)
        return path

# ---------- Helpers ----------
def extract_coordinates_from_url(url: str) -> Tuple[float, float]:
    """
    Extract coordinates from a Google Maps URL like:
    https://www.google.com/maps/place/.../@51.16,71.47,17z/...
    Returns (lat, lon) or (None, None)
    """
    try:
        if '/@' not in url:
            return None, None
        coords_part = url.split('/@')[-1].split('/')[0]
        lat_str, lon_str = coords_part.split(',')[:2]
        return float(lat_str), float(lon_str)
    except Exception:
        return None, None

def parse_rating(text: str):
    """
    Normalize rating text into float.
    Accepts variants like:
    - "4.5"
    - "4,5"
    - "4.5-звезды" / "4.5-звездочные" / "4.5 of 5" / "4.5 (отзывов...)"
    Returns float or None.
    """
    if not text:
        return None
    # find first occurrence of number like 4.5 or 4,5 or 4
    m = re.search(r'(\d+(?:[.,]\d+)?)', text)
    if not m:
        return None
    num = m.group(1).replace(',', '.')
    try:
        return float(num)
    except ValueError:
        return None

def parse_reviews_count(text: str):
    """
    Extract integer reviews count from strings like:
    - "123 отзыв"
    - "1,234 reviews"
    - "123"
    Returns int or None.
    """
    if not text:
        return None
    # remove non-digit characters except comma/dot, then extract digits
    digits = ''.join(ch for ch in text if ch.isdigit())
    if not digits:
        return None
    try:
        return int(digits)
    except ValueError:
        return None

def safe_inner_text(page, xpath: str) -> str:
    """
    Return element inner_text if exists, else empty string.
    """
    try:
        locator = page.locator(xpath)
        if locator.count() > 0:
            return locator.all()[0].inner_text().strip()
        return ""
    except Exception:
        return ""

# ---------- Main scraper ----------
def scrape_google_maps(
    query: str,
    total: int = 100,
    max_duration_sec: int = 120,
    headless: bool = True,
    per_card_wait: float = 3.0
) -> BusinessList:
    """
    Scrape Google Maps for `query`.
    - total: max number of cards to process
    - max_duration_sec: overall time limit in seconds
    - headless: run browser headless or visible
    - per_card_wait: wait after clicking card to let details load
    Returns BusinessList
    """
    start_time = time.time()
    b_list = BusinessList()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        page = browser.new_page()
        page.set_default_timeout(60000)

        print("▶ Opening Google Maps...")
        page.goto("https://www.google.com/maps", timeout=60000)
        time.sleep(2)

        # Fill search box and submit
        print(f"▶ Searching for: {query}")
        # Ensure search box present
        search_input = page.locator('//input[@id="searchboxinput"]')
        if search_input.count() == 0:
            print("⚠️ Search input not found on page. Trying to reload and continue...")
            page.reload()
            time.sleep(3)
        page.locator('//input[@id="searchboxinput"]').fill(query)
        time.sleep(0.5)
        page.keyboard.press("Enter")
        time.sleep(4)  # wait for results to load

        # try to hover results to trigger lazy load
        try:
            page.hover('//a[contains(@href, "https://www.google.com/maps/place")]')
        except Exception:
            pass

        # Scrolling loop to collect listing anchors
        previously_counted = 0
        listings = []
        scroll_tries = 0
        print("▶ Scrolling results to load cards...")
        while True:
            # safety: time check
            if time.time() - start_time > max_duration_sec:
                print("⏳ Time limit reached while scrolling.")
                break

            page.mouse.wheel(0, 10000)
            time.sleep(1.2)

            anchors = page.locator('//a[contains(@href, "https://www.google.com/maps/place")]')
            count = anchors.count()
            # If count hasn't changed, increase tries, else reset
            if count == previously_counted:
                scroll_tries += 1
            else:
                scroll_tries = 0
                previously_counted = count

            print(f" - currently found anchors: {count}")

            if count >= total:
                print(f"✔ Desired amount reached ({count} >= {total})")
                break

            # If we've tried several times and nothing more loads, stop
            if scroll_tries >= 6:
                print("✔ No more items loading after scrolling.")
                break

            # safety small sleep
            time.sleep(0.8)

        # Collect anchors (limit to total)
        try:
            anchor_elements = anchors.all()[:total]
            # For each anchor, use its parent element if clickable area differs
            # We'll store the anchor element for click
            listings = anchor_elements
            print(f"✅ Total anchors to consider: {len(listings)}")
        except Exception as e:
            print("⚠️ Failed to gather anchor elements:", e)
            listings = []

        # Process each listing
        processed = 0
        for idx, listing in enumerate(listings):
            # time limit check
            if time.time() - start_time > max_duration_sec:
                print("⏳ Overall time limit reached. Stopping processing.")
                break
            if processed >= total:
                break

            try:
                # Some anchors may require their parent clickable; try click robustly
                try:
                    listing.click()
                except Exception:
                    # fallback: click via JS on href
                    href = listing.get_attribute("href") or ""
                    if href:
                        page.goto(href)
                    else:
                        # try click parent
                        try:
                            listing.locator("xpath=..").click()
                        except Exception:
                            raise

                # wait for details pane to load
                time.sleep(per_card_wait)

                # Create business and extract fields
                biz = Business()
                # store current url (useful for coords)
                current_url = page.url
                biz.raw_url = current_url

                # name: try aria-label of the active marker or the top title
                try:
                    # Many times the marker or title has aria-label with name
                    name_attr = listing.get_attribute("aria-label") or ""
                    if name_attr.strip():
                        biz.name = name_attr.strip()
                    else:
                        # alternative: select title text from side panel
                        title_text = safe_inner_text(page, '//h1[contains(@class, "fontHeadlineLarge")]') \
                                     or safe_inner_text(page, '//h1[@data-testid="title"]') \
                                     or safe_inner_text(page, '//h1')
                        biz.name = title_text
                except Exception:
                    biz.name = ""

                # address, website, phone
                biz.address = safe_inner_text(page, '//button[@data-item-id="address"]//div[contains(@class, "fontBodyMedium")]') \
                              or safe_inner_text(page, '//button[contains(@data-item-id, "address")]') \
                              or safe_inner_text(page, '//div[@data-item-id="address"]')

                biz.website = safe_inner_text(page, '//a[@data-item-id="authority"]//div[contains(@class, "fontBodyMedium")]') \
                              or safe_inner_text(page, '//a[contains(@href, "http") and contains(@data-item-id, "authority")]') \
                              or safe_inner_text(page, '//a[contains(@href, "http") and contains(@class, "website")]')

                biz.phone_number = safe_inner_text(page, '//button[contains(@data-item-id, "phone:tel:")]//div[contains(@class, "fontBodyMedium")]') \
                                    or safe_inner_text(page, '//button[contains(@aria-label, "Позвонить")]') \
                                    or safe_inner_text(page, '//a[contains(@href, "tel:")]')

                # rating and reviews: multiple possible selectors; try several
                rating_text_candidates = [
                    safe_inner_text(page, '//span[contains(@aria-label, "звезд")]'),
                    safe_inner_text(page, '//div[@role="img" and contains(@aria-label, "звезд")]'),
                    safe_inner_text(page, '//span[contains(@class, "section-star-display")]'),
                    safe_inner_text(page, '//div[contains(@aria-label, "out of 5")]'),
                ]
                rating_text = next((c for c in rating_text_candidates if c), "")
                biz.reviews_average = parse_rating(rating_text)

                # reviews count candidates
                reviews_text_candidates = [
                    safe_inner_text(page, '//button[@jsaction="pane.reviewChart.moreReviews"]//span'),
                    safe_inner_text(page, '//button[contains(@aria-label, "отзыв")]'),
                    safe_inner_text(page, '//span[contains(text(), "отзыв")]'),
                    safe_inner_text(page, '//span[contains(text(), "reviews")]'),
                ]
                reviews_text = next((c for c in reviews_text_candidates if c), "")
                biz.reviews_count = parse_reviews_count(reviews_text)

                # coords
                lat, lon = extract_coordinates_from_url(current_url)
                biz.latitude, biz.longitude = lat, lon

                # append and increment counters
                b_list.business_list.append(biz)
                processed += 1
                print(f"[{processed}] {biz.name} | {biz.address} | rating={biz.reviews_average} reviews={biz.reviews_count}")

            except Exception as e:
                print(f"Error occured while processing listing #{idx}: {e}")

        browser.close()
        print(f"✔ Scraping finished. Processed {processed} items.")

    return b_list

# ---------- CLI ----------
def parse_args():
    parser = argparse.ArgumentParser(description="Google Maps scraper (Playwright)")
    parser.add_argument("-s", "--search", type=str, help="Search query (e.g. 'Астана кафе')", required=False)
    parser.add_argument("-t", "--total", type=int, help="Max items to process (default 100)", default=100)
    parser.add_argument("--timeout", type=int, help="Max duration in seconds (default 120)", default=120)
    parser.add_argument("--headless", type=lambda x: (str(x).lower() in ("true", "1", "yes")), default=True, help="Run headless: True/False")
    parser.add_argument("--wait", type=float, help="Seconds to wait after opening a card (default 3.0)", default=3.0)
    return parser.parse_args()

def main():
    args = parse_args()

    # Prepare search list
    if args.search:
        search_list = [args.search]
    else:
        # fallback to input.txt lines if exists
        input_file_name = 'input.txt'
        if os.path.exists(input_file_name):
            with open(input_file_name, 'r', encoding='utf-8') as f:
                search_list = [line.strip() for line in f if line.strip()]
        else:
            print("❗ No search provided and input.txt not found. Use -s or create input.txt.")
            return

    for query in search_list:
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        safe_name = query.replace(' ', '_').replace('/', '_')
        filename = f"google_maps_{safe_name}_{timestamp}"
        print(f"\n=== Starting scraping for: {query} ===")
        b_list = scrape_google_maps(
            query=query,
            total=args.total,
            max_duration_sec=args.timeout,
            headless=args.headless,
            per_card_wait=args.wait
        )

        csv_path = b_list.save_to_csv(filename)
        xlsx_path = b_list.save_to_excel(filename)
        print(f"Saved CSV: {csv_path}")
        print(f"Saved XLSX: {xlsx_path}")
        print(f"Total saved rows: {len(b_list.business_list)}")

if __name__ == "__main__":
    main()


@dataclass
class Business:
    # данные о месте
    name: str = None
    address: str = None
    website: str = None
    phone_number: str = None
    reviews_count: int = None
    reviews_average: float = None
    latitude: float = None
    longitude: float = None


@dataclass
class BusinessList:
    business_list: list[Business] = field(default_factory=list)
    save_at = 'output'

    def dataframe(self):
        return pd.json_normalize(
            (asdict(business) for business in self.business_list), sep="_"
        )

    def save_to_excel(self, filename):
        if not os.path.exists(self.save_at):
            os.makedirs(self.save_at)
        self.dataframe().to_excel(f"output/{filename}.xlsx", index=False)

    def save_to_csv(self, filename):
        if not os.path.exists(self.save_at):
            os.makedirs(self.save_at)
        self.dataframe().to_csv(f"output/{filename}.csv", index=False)


def extract_coordinates_from_url(url: str) -> tuple[float, float]:
    coordinates = url.split('/@')[-1].split('/')[0]
    return float(coordinates.split(',')[0]), float(coordinates.split(',')[1])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-s", "--search", type=str)
    parser.add_argument("-t", "--total", type=int)
    args = parser.parse_args()

    if args.search:
        search_list = [args.search]

    if args.total:
        total = args.total
    else:
        total = 1_000_000

    if not args.search:
        search_list = []
        input_file_name = 'input.txt'
        input_file_path = os.path.join(os.getcwd(), input_file_name)
        if os.path.exists(input_file_path):
            with open(input_file_path, 'r') as file:
                search_list = file.readlines()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()

        page.goto("https://www.google.com/maps", timeout=60000)
        page.wait_for_timeout(5000)

        for search_for_index, search_for in enumerate(search_list):
            print(f"-----\n{search_for_index} - {search_for}".strip())

            page.locator('//input[@id="searchboxinput"]').fill(search_for)
            page.wait_for_timeout(3000)

            page.keyboard.press("Enter")
            page.wait_for_timeout(5000)

            page.hover('//a[contains(@href, "https://www.google.com/maps/place")]')
            previously_counted = 0
            while True:
                page.mouse.wheel(0, 10000)
                page.wait_for_timeout(3000)

                if (
                        page.locator(
                            '//a[contains(@href, "https://www.google.com/maps/place")]'
                        ).count()
                        >= total
                ):
                    listings = page.locator(
                        '//a[contains(@href, "https://www.google.com/maps/place")]'
                    ).all()[:total]
                    listings = [listing.locator("xpath=..") for listing in listings]
                    print(f"Total Scraped: {len(listings)}")
                    break
                else:
                    if (
                            page.locator(
                                '//a[contains(@href, "https://www.google.com/maps/place")]'
                            ).count()
                            == previously_counted
                    ):
                        listings = page.locator(
                            '//a[contains(@href, "https://www.google.com/maps/place")]'
                        ).all()
                        print(f"Arrived at all available\nTotal Scraped: {len(listings)}")
                        break
                    else:
                        previously_counted = page.locator(
                            '//a[contains(@href, "https://www.google.com/maps/place")]'
                        ).count()
                        print(
                            f"Currently Scraped: ",
                            page.locator(
                                '//a[contains(@href, "https://www.google.com/maps/place")]'
                            ).count(),
                        )

            business_list = BusinessList()

            for listing in listings:
                try:
                    listing.click()
                    page.wait_for_timeout(5000)

                    name_attibute = 'aria-label'
                    address_xpath = '//button[@data-item-id="address"]//div[contains(@class, "fontBodyMedium")]'
                    website_xpath = '//a[@data-item-id="authority"]//div[contains(@class, "fontBodyMedium")]'
                    phone_number_xpath = '//button[contains(@data-item-id, "phone:tel:")]//div[contains(@class, "fontBodyMedium")]'
                    review_count_xpath = '//button[@jsaction="pane.reviewChart.moreReviews"]//span'
                    reviews_average_xpath = '//div[@jsaction="pane.reviewChart.moreReviews"]//div[@role="img"]'

                    business = Business()

                    if len(listing.get_attribute(name_attibute)) >= 1:

                        business.name = listing.get_attribute(name_attibute)
                    else:
                        business.name = ""
                    if page.locator(address_xpath).count() > 0:
                        business.address = page.locator(address_xpath).all()[0].inner_text()
                    else:
                        business.address = ""
                    if page.locator(website_xpath).count() > 0:
                        business.website = page.locator(website_xpath).all()[0].inner_text()
                    else:
                        business.website = ""
                    if page.locator(phone_number_xpath).count() > 0:
                        business.phone_number = page.locator(phone_number_xpath).all()[0].inner_text()
                    else:
                        business.phone_number = ""
                    if page.locator(review_count_xpath).count() > 0:
                        business.reviews_count = int(
                            page.locator(review_count_xpath).inner_text()
                            .split()[0]
                            .replace(',', '')
                            .strip()
                        )
                    else:
                        business.reviews_count = ""

                    if page.locator(reviews_average_xpath).count() > 0:
                        business.reviews_average = float(
                            page.locator(reviews_average_xpath).get_attribute(name_attibute)
                            .split()[0]
                            .replace(',', '.')
                            .strip())
                    else:
                        business.reviews_average = ""

                    business.latitude, business.longitude = extract_coordinates_from_url(page.url)

                    business_list.business_list.append(business)
                except Exception as e:
                    print(f'Error occured: {e}')

            #здесь вывод
            business_list.save_to_excel(f"google_maps_data_{search_for}".replace(' ', '_'))
            business_list.save_to_csv(f"google_maps_data_{search_for}".replace(' ', '_'))

        browser.close()


if __name__ == "__main__":
    main()