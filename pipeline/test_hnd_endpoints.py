#!/usr/bin/env python3
"""
Test verschiedene potenzielle API-Endpoints auf hnd.bayern.de und gkd.bayern.de
"""

import requests
import json
from datetime import datetime

STATION_ID = "16005701"  # München/Isar

# Teste verschiedene potenzielle Endpoints
endpoints = [
    # HND Bayern Webservices
    ("HND Webservice graphik.php", f"https://www.hnd.bayern.de/webservices/graphik.php?statnr={STATION_ID}"),
    ("HND Webservice JSON (test 1)", f"https://www.hnd.bayern.de/webservices/daten.php?statnr={STATION_ID}"),
    ("HND Webservice JSON (test 2)", f"https://www.hnd.bayern.de/webservices/messwerte.php?statnr={STATION_ID}"),
    ("HND Webservice JSON (test 3)", f"https://www.hnd.bayern.de/webservices/api.php?statnr={STATION_ID}"),
    ("HND Webservice JSON (test 4)", f"https://www.hnd.bayern.de/webservices/json.php?statnr={STATION_ID}"),
    ("HND Webservice JSON (test 5)", f"https://www.hnd.bayern.de/webservices/rest/pegel/{STATION_ID}"),
    ("HND Webservice JSON (test 6)", f"https://www.hnd.bayern.de/webservices/v1/stations/{STATION_ID}"),
    ("HND Webservice JSON (test 7)", f"https://www.hnd.bayern.de/api/pegel/{STATION_ID}"),
    ("HND Webservice JSON (test 8)", f"https://www.hnd.bayern.de/api/v1/stations/{STATION_ID}"),
    
    # GKD Bayern Webservices
    ("GKD Webservice JSON (test 1)", f"https://www.gkd.bayern.de/api/fluesse/wasserstand/{STATION_ID}"),
    ("GKD Webservice JSON (test 2)", f"https://www.gkd.bayern.de/webservices/stations/{STATION_ID}"),
    ("GKD Webservice JSON (test 3)", f"https://www.gkd.bayern.de/webservices/messwerte.php?statnr={STATION_ID}"),
    
    # Teste auch mit pgnr Parameter
    ("HND with pgnr param", f"https://www.hnd.bayern.de/webservices/daten.php?pgnr={STATION_ID}"),
    ("HND with pgnr param 2", f"https://www.hnd.bayern.de/webservices/messwerte.php?pgnr={STATION_ID}"),
]

print("=" * 80)
print("🔍 Testing potential API endpoints for München/Isar")
print("=" * 80)
print()

successful_endpoints = []

for name, url in endpoints:
    print(f"Testing: {name}")
    print(f"URL: {url}")
    
    try:
        response = requests.get(url, timeout=10, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        content_type = response.headers.get('Content-Type', 'unknown')
        status = response.status_code
        
        print(f"Status: {status}")
        print(f"Content-Type: {content_type}")
        
        if status == 200:
            # Check if it's JSON
            if 'json' in content_type:
                try:
                    data = response.json()
                    print(f"✅ SUCCESS! Got JSON data:")
                    print(json.dumps(data, indent=2, ensure_ascii=False)[:500])
                    successful_endpoints.append((name, url, 'json', data))
                except:
                    print(f"⚠️  Response claims to be JSON but couldn't parse")
            # Check if it's an image (the graphik.php endpoint)
            elif 'image' in content_type:
                print(f"📊 Image endpoint (graphik.php works but returns image, not data)")
            # Check if response looks like JSON even without proper content-type
            elif response.text.strip().startswith('{') or response.text.strip().startswith('['):
                try:
                    data = json.loads(response.text)
                    print(f"✅ SUCCESS! Got JSON data (wrong content-type):")
                    print(json.dumps(data, indent=2, ensure_ascii=False)[:500])
                    successful_endpoints.append((name, url, 'json', data))
                except:
                    print(f"⚠️  Looks like JSON but couldn't parse")
                    print(f"First 200 chars: {response.text[:200]}")
            # Check for HTML
            elif 'html' in content_type or response.text.strip().startswith('<'):
                print(f"📄 HTML response (not an API endpoint)")
            # Check for XML
            elif 'xml' in content_type or response.text.strip().startswith('<?xml'):
                print(f"📋 XML response")
                print(f"First 300 chars: {response.text[:300]}")
            else:
                print(f"❓ Unknown content type")
                print(f"First 200 chars: {response.text[:200]}")
        elif status == 404:
            print(f"❌ 404 Not Found")
        elif status == 403:
            print(f"❌ 403 Forbidden")
        else:
            print(f"❌ Status {status}")
    
    except requests.exceptions.Timeout:
        print(f"⏱️  Timeout")
    except requests.exceptions.ConnectionError:
        print(f"❌ Connection Error")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    print("-" * 80)
    print()

print()
print("=" * 80)
print("📊 SUMMARY")
print("=" * 80)

if successful_endpoints:
    print(f"\n✅ Found {len(successful_endpoints)} working endpoint(s):\n")
    for name, url, data_type, data in successful_endpoints:
        print(f"• {name}")
        print(f"  URL: {url}")
        print(f"  Type: {data_type}")
        print()
else:
    print("\n❌ No JSON/API endpoints found.")
    print("\n💡 Next steps:")
    print("   1. Contact LfU Bayern: hnd@lfu.bayern.de")
    print("   2. Use web scraping of the HTML tables")
    print("   3. Check if there's an RSS feed")
    print()
