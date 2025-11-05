"""
Festival Web Scraper with Multipage Support and Smart CSV Export
Dependencies:
    pip install beautifulsoup4 requests selenium webdriver-manager
"""

import csv
import time
import json
import os
from datetime import datetime
from typing import List, Dict

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup


class FestivalScraper:
    """Scraper using Selenium with WebDriver Manager"""

    def __init__(self):
        """Initialize Chrome driver with options to avoid detection"""
        print("\n🚀 Initializing Chrome WebDriver...")

        chrome_options = Options()
        chrome_options.add_argument('--headless=new')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_argument('--disable-extensions')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('window-size=1920,1080')
        chrome_options.add_argument(
            'user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36'
        )
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)

        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=chrome_options)
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        print("✓ Browser initialized successfully")

    def get_total_pages(self, soup: BeautifulSoup) -> int:
        """Detect total number of pages available"""
        pagination = soup.find('ul', class_='page-numbers')
        if not pagination:
            return 1
        page_links = pagination.find_all('a', class_='page-numbers')
        page_numbers = []
        for link in page_links:
            try:
                num = int(link.text.strip())
                page_numbers.append(num)
            except ValueError:
                continue
        return max(page_numbers) if page_numbers else 1

    def get_festival_links(self, base_url: str, max_pages: int = None) -> List[Dict[str, str]]:
        """
        Scrape multiple pages of the main festival list to get all festival links.
        If max_pages is None, scrape all available pages.
        """
        all_festivals = []
        seen_urls = set()

        # Load first page to detect total number of pages
        print(f"\n🌐 Loading main page: {base_url}")
        self.driver.get(base_url)
        time.sleep(5)
        soup = BeautifulSoup(self.driver.page_source, 'html.parser')
        total_pages = self.get_total_pages(soup)

        if max_pages is None or max_pages > total_pages:
            max_pages = total_pages

        print(f"📑 Total pages detected: {total_pages}")
        print(f"➡️  Scraping up to page {max_pages}\n")

        for page in range(1, max_pages + 1):
            if page == 1:
                url = base_url
            else:
                url = f"https://www.musicfestivalwizard.com/all-festivals/page/{page}/?festivalgenre=electronic&ranked=yes"

            print(f"📄 Fetching page {page}/{max_pages}: {url}")
            try:
                self.driver.get(url)
                time.sleep(4)
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'a[href*="/festivals/"]'))
                )

                soup = BeautifulSoup(self.driver.page_source, 'html.parser')
                festival_links = soup.find_all('a', href=lambda x: x and '/festivals/' in x)

                for link in festival_links:
                    href = link.get('href', '')
                    if not href or href.endswith('/festivals/'):
                        continue
                    if href.startswith('/'):
                        href = 'https://www.musicfestivalwizard.com' + href
                    if href in seen_urls:
                        continue
                    seen_urls.add(href)
                    name = link.get_text(strip=True)
                    if not name or len(name) < 3:
                        name = href.split('/')[-2].replace('-', ' ').title()
                    all_festivals.append({'name': name, 'url': href})

                print(f"  ✓ Found {len(festival_links)} links (total so far: {len(all_festivals)})")

            except Exception as e:
                print(f"  ✗ Error fetching page {page}: {e}")
                continue

        print(f"\n✅ Total unique festivals collected: {len(all_festivals)}")
        return all_festivals

    def scrape_festival_details(self, url: str) -> Dict:
        """Scrape individual festival page for details."""
        print(f"\n📍 Scraping: {url}")

        festival_data = {'name': '', 'date': '', 'location': '', 'artists': []}

        try:
            self.driver.get(url)
            time.sleep(3)
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')

            # Try JSON-LD
            json_ld_script = soup.find('script', type='application/ld+json')
            if json_ld_script:
                try:
                    json_data = json.loads(json_ld_script.string)
                    festival_data['name'] = json_data.get('name', '')
                    start_date = json_data.get('startDate', '')
                    end_date = json_data.get('endDate', '')
                    if start_date and end_date and start_date != end_date:
                        festival_data['date'] = f"{start_date} - {end_date}"
                    elif start_date:
                        festival_data['date'] = start_date
                    loc_data = json_data.get('location', {}).get('address', {})
                    if isinstance(loc_data, dict):
                        locality = loc_data.get('addressLocality', '')
                        region = loc_data.get('addressRegion', '')
                        festival_data['location'] = f"{locality}, {region}".strip(', ')
                except Exception:
                    pass

            # Fallback HTML parsing
            if not festival_data['name'] or not festival_data['date']:
                header_block = soup.find('div', class_='headerblock')
                if header_block:
                    h1 = header_block.find('h1')
                    if h1:
                        festival_data['name'] = h1.get_text(strip=True)
                    p_tags = header_block.find_all('p')
                    if len(p_tags) >= 1:
                        festival_data['date'] = festival_data['date'] or p_tags[0].get_text(strip=True)
                    if len(p_tags) >= 2:
                        festival_data['location'] = festival_data['location'] or p_tags[1].get_text(strip=True)

            # Artist lineup
            lineup_div = soup.find('div', class_='hublineup')
            if lineup_div:
                for li in lineup_div.find_all('li'):
                    artist = li.get_text(strip=True)
                    if artist:
                        festival_data['artists'].append(artist)

            return festival_data

        except Exception as e:
            print(f"  ✗ Error scraping {url}: {e}")
            return festival_data

    def close(self):
        """Close the browser"""
        print("\n🔒 Closing browser...")
        self.driver.quit()
        print("✓ Browser closed")


def get_unique_filename(base_name: str = "Festival Output") -> str:
    """Generate a unique CSV filename with today's date."""
    date_str = datetime.now().strftime("%m-%d-%Y")
    filename = f"{base_name} {date_str}.csv"
    counter = 1
    while os.path.exists(filename):
        counter += 1
        filename = f"{base_name} {date_str} ({counter}).csv"
    return filename


def save_to_csv(festivals_data: List[Dict], filename: str):
    """Save festival data to CSV file."""
    print(f"\n💾 Saving data to {filename}...")

    with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['Festival', 'Date', 'Location', 'Artists']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        for fest in festivals_data:
            artists_str = ', '.join(fest.get('artists', []))
            writer.writerow({
                'Festival': fest.get('name', ''),
                'Date': fest.get('date', ''),
                'Location': fest.get('location', ''),
                'Artists': artists_str
            })

    print(f"✓ Saved {len(festivals_data)} festivals to {filename}")


def main():
    print("=" * 70)
    print("🎵 FESTIVAL WEB SCRAPER — Multipage + Smart CSV Export")
    print("=" * 70)

    scraper = FestivalScraper()
    try:
        main_url = "https://www.musicfestivalwizard.com/all-festivals/?festivalgenre=electronic&ranked=yes"
        max_pages = None  # Set None for all pages, or an integer for limit (e.g., 4)

        print("\n[STEP 1] Collecting festival links...")
        festival_links = scraper.get_festival_links(main_url, max_pages=max_pages)
        if not festival_links:
            print("⚠ No festivals found.")
            return

        print(f"\n[STEP 2] Scraping {len(festival_links)} individual festival pages...")
        all_data = []
        for i, fest in enumerate(festival_links, 1):
            print(f"[{i}/{len(festival_links)}] {fest['name']}")
            data = scraper.scrape_festival_details(fest['url'])
            if data and data['name']:
                all_data.append(data)
            time.sleep(2)

        print("\n[STEP 3] Saving results...")
        filename = get_unique_filename()
        save_to_csv(all_data, filename)

        print("\n📊 SUMMARY")
        print("=" * 70)
        print(f"Total festivals scraped: {len(all_data)}")
        print(f"Festivals with lineups: {sum(1 for f in all_data if f['artists'])}")
        print(f"Total artists collected: {sum(len(f['artists']) for f in all_data)}")
        print(f"File saved as: {filename}")
        print("=" * 70)

    finally:
        scraper.close()


if __name__ == "__main__":
    main()
