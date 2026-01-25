#!/usr/bin/env python3
"""
Scraper für aktuelle Pegeldaten von München/Isar
Holt die neuesten Werte von hnd.bayern.de
"""

import requests
from bs4 import BeautifulSoup
from datetime import datetime
import json
import sys

STATION_ID = "16005701"  # München/Isar
BASE_URL = "https://www.hnd.bayern.de"

def fetch_current_water_level():
    """
    Holt den aktuellen Wasserstand von der HND-Webseite
    """
    # URL zur Tabellenseite (15-Minuten-Werte)
    url = f"{BASE_URL}/pegel/isar/muenchen-{STATION_ID}/tabelle?methode=wasserstand&setdiskr=15"
    
    print(f"🌊 Fetching data from: {url}")
    
    try:
        response = requests.get(url, timeout=15, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find the data table
        table = soup.find('table')
        
        if not table:
            print("❌ Error: Could not find data table")
            return None
        
        # Parse table rows
        rows = table.find_all('tr')
        
        measurements = []
        
        for row in rows[1:]:  # Skip header row
            cols = row.find_all('td')
            
            if len(cols) >= 2:
                date_time_str = cols[0].get_text(strip=True)
                value_str = cols[1].get_text(strip=True)
                
                try:
                    # Parse date/time (format: "25.01.2026 16:00")
                    timestamp = datetime.strptime(date_time_str, "%d.%m.%Y %H:%M")
                    
                    # Parse value (format: "87" in cm)
                    value = int(value_str)
                    
                    measurements.append({
                        'timestamp': timestamp.isoformat(),
                        'timestamp_unix': int(timestamp.timestamp()),
                        'value_cm': value,
                        'unit': 'cm',
                        'station_id': STATION_ID,
                        'station_name': 'München / Isar',
                        'source': 'hnd.bayern.de'
                    })
                except (ValueError, AttributeError) as e:
                    # Skip rows that can't be parsed
                    continue
        
        if measurements:
            # Sort by timestamp (newest first)
            measurements.sort(key=lambda x: x['timestamp'], reverse=True)
            
            print(f"✅ Successfully fetched {len(measurements)} measurements")
            print(f"   Latest: {measurements[0]['timestamp']} - {measurements[0]['value_cm']} cm")
            print(f"   Oldest: {measurements[-1]['timestamp']} - {measurements[-1]['value_cm']} cm")
            
            return measurements
        else:
            print("❌ Error: No measurements found in table")
            return None
    
    except requests.exceptions.Timeout:
        print("❌ Error: Request timed out")
        return None
    except requests.exceptions.RequestException as e:
        print(f"❌ Error fetching data: {e}")
        return None
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return None

def get_latest_value():
    """
    Holt nur den neuesten Wert
    """
    measurements = fetch_current_water_level()
    
    if measurements and len(measurements) > 0:
        return measurements[0]
    return None

def main():
    print("=" * 80)
    print("🌊 München/Isar - Current Water Level Scraper")
    print("=" * 80)
    print()
    
    # Fetch all recent measurements
    measurements = fetch_current_water_level()
    
    if measurements:
        print("\n" + "-" * 80)
        print("📊 Latest 10 measurements:")
        print("-" * 80)
        
        for i, m in enumerate(measurements[:10], 1):
            dt = datetime.fromisoformat(m['timestamp'])
            print(f"{i:2}. {dt.strftime('%d.%m.%Y %H:%M')} | {m['value_cm']:3} cm")
        
        # Save to JSON file
        output_file = "current_water_level.json"
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump({
                'station_id': STATION_ID,
                'station_name': 'München / Isar',
                'source': 'hnd.bayern.de',
                'fetched_at': datetime.now().isoformat(),
                'measurements': measurements
            }, f, indent=2, ensure_ascii=False)
        
        print(f"\n✅ Saved {len(measurements)} measurements to {output_file}")
        
        # Return success
        return 0
    else:
        print("\n❌ Failed to fetch measurements")
        return 1

if __name__ == "__main__":
    sys.exit(main())
