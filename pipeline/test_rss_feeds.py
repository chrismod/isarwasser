#!/usr/bin/env python3
"""
Test for RSS/Atom feeds on hnd.bayern.de and gkd.bayern.de
"""

import requests
from bs4 import BeautifulSoup

STATION_ID = "16005701"

# Teste verschiedene RSS/Atom Feed URLs
feed_urls = [
    ("HND RSS (test 1)", f"https://www.hnd.bayern.de/rss/pegel/{STATION_ID}"),
    ("HND RSS (test 2)", f"https://www.hnd.bayern.de/pegel/isar/muenchen-{STATION_ID}/rss"),
    ("HND Atom (test 1)", f"https://www.hnd.bayern.de/atom/pegel/{STATION_ID}"),
    ("GKD RSS (test 1)", f"https://www.gkd.bayern.de/rss/fluesse/wasserstand/{STATION_ID}"),
    ("HND allgemein RSS", "https://www.hnd.bayern.de/rss"),
    ("HND Warnungen RSS", "https://www.hnd.bayern.de/warnungen/rss"),
]

print("=" * 80)
print("🔍 Testing for RSS/Atom feeds")
print("=" * 80)
print()

for name, url in feed_urls:
    print(f"Testing: {name}")
    print(f"URL: {url}")
    
    try:
        response = requests.get(url, timeout=10, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        status = response.status_code
        content_type = response.headers.get('Content-Type', 'unknown')
        
        print(f"Status: {status}")
        print(f"Content-Type: {content_type}")
        
        if status == 200:
            # Check for RSS/Atom
            if 'xml' in content_type or 'rss' in content_type or 'atom' in content_type:
                print(f"✅ Found feed!")
                print(f"First 500 chars:")
                print(response.text[:500])
                print()
            elif response.text.strip().startswith('<?xml'):
                print(f"✅ Found XML (possibly RSS/Atom without proper content-type)!")
                print(f"First 500 chars:")
                print(response.text[:500])
                print()
            else:
                print(f"❌ Not a feed (HTML response)")
        else:
            print(f"❌ Status {status}")
    
    except Exception as e:
        print(f"❌ Error: {e}")
    
    print("-" * 80)
    print()

# Check HTML pages for RSS feed links
print("\n" + "=" * 80)
print("🔍 Checking HTML pages for RSS/Atom feed links")
print("=" * 80)
print()

html_pages = [
    ("HND Hauptseite", "https://www.hnd.bayern.de/"),
    ("HND München/Isar", f"https://www.hnd.bayern.de/pegel/isar/muenchen-{STATION_ID}"),
    ("GKD Hauptseite", "https://www.gkd.bayern.de/"),
]

for name, url in html_pages:
    print(f"Checking: {name}")
    print(f"URL: {url}")
    
    try:
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Look for RSS/Atom links in <link> tags
            feeds = soup.find_all('link', {'type': ['application/rss+xml', 'application/atom+xml']})
            
            if feeds:
                print(f"✅ Found {len(feeds)} feed link(s):")
                for feed in feeds:
                    print(f"   • {feed.get('title', 'No title')}: {feed.get('href')}")
            else:
                print(f"❌ No feed links found in HTML")
        else:
            print(f"❌ Status {response.status_code}")
    
    except Exception as e:
        print(f"❌ Error: {e}")
    
    print("-" * 80)
    print()

print("\n" + "=" * 80)
print("📊 CONCLUSION")
print("=" * 80)
print("\nIf no RSS feeds were found, we need to use HTML scraping.")
print()
