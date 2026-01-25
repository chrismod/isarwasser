#!/usr/bin/env python3
"""
Automated script to fetch current Isar water levels and append to database
Designed to run every 3 hours via cron
"""

import requests
from bs4 import BeautifulSoup
from datetime import datetime
import json
import sys
import os
from pathlib import Path

STATION_ID = "16005701"
BASE_URL = "https://www.hnd.bayern.de"
DATA_DIR = Path(__file__).parent.parent / "data" / "current"
LOG_FILE = Path(__file__).parent.parent / "log.txt"

def log(message):
    """Log message to console and file"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_message = f"[{timestamp}] {message}"
    print(log_message)
    
    # Append to log file
    try:
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(log_message + '\n')
    except Exception as e:
        print(f"Warning: Could not write to log file: {e}")

def fetch_latest_value():
    """
    Fetch only the latest water level value from HND website
    """
    url = f"{BASE_URL}/pegel/isar/muenchen-{STATION_ID}/tabelle?methode=wasserstand&setdiskr=15"
    
    log(f"Fetching data from: {url}")
    
    try:
        response = requests.get(url, timeout=15, headers={
            'User-Agent': 'IsarWasser-Monitor/1.0 (educational project)'
        })
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        table = soup.find('table')
        
        if not table:
            log("ERROR: Could not find data table")
            return None
        
        # Get first data row (most recent)
        rows = table.find_all('tr')
        
        if len(rows) < 2:
            log("ERROR: No data rows found")
            return None
        
        first_data_row = rows[1]
        cols = first_data_row.find_all('td')
        
        if len(cols) < 2:
            log("ERROR: Invalid table structure")
            return None
        
        date_time_str = cols[0].get_text(strip=True)
        value_str = cols[1].get_text(strip=True)
        
        # Parse date/time (format: "25.01.2026 16:00")
        timestamp = datetime.strptime(date_time_str, "%d.%m.%Y %H:%M")
        
        # Parse value (format: "87" in cm)
        value = int(value_str)
        
        measurement = {
            'timestamp': timestamp.isoformat(),
            'timestamp_unix': int(timestamp.timestamp()),
            'date': timestamp.strftime('%Y-%m-%d'),
            'time': timestamp.strftime('%H:%M:%S'),
            'value_cm': value,
            'unit': 'cm',
            'station_id': STATION_ID,
            'station_name': 'München / Isar',
            'source': 'hnd.bayern.de',
            'fetched_at': datetime.now().isoformat()
        }
        
        log(f"SUCCESS: Fetched latest value: {timestamp.strftime('%Y-%m-%d %H:%M')} = {value} cm")
        
        return measurement
    
    except requests.exceptions.Timeout:
        log("ERROR: Request timed out")
        return None
    except requests.exceptions.RequestException as e:
        log(f"ERROR: Request failed: {e}")
        return None
    except Exception as e:
        log(f"ERROR: Unexpected error: {e}")
        return None

def save_to_json_log(measurement):
    """
    Append measurement to a JSONL (JSON Lines) file - one JSON object per line
    """
    # Create data directory if it doesn't exist
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    # Use daily log files
    date_str = measurement['date']
    log_file = DATA_DIR / f"water_level_{date_str}.jsonl"
    
    try:
        # Append as single line
        with open(log_file, 'a', encoding='utf-8') as f:
            json.dump(measurement, f, ensure_ascii=False)
            f.write('\n')
        
        log(f"Saved to: {log_file}")
        return True
    
    except Exception as e:
        log(f"ERROR: Could not save to file: {e}")
        return False

def check_duplicate(measurement):
    """
    Check if this exact measurement already exists (avoid duplicates)
    """
    date_str = measurement['date']
    log_file = DATA_DIR / f"water_level_{date_str}.jsonl"
    
    if not log_file.exists():
        return False
    
    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    existing = json.loads(line)
                    if (existing['timestamp'] == measurement['timestamp'] and 
                        existing['value_cm'] == measurement['value_cm']):
                        return True
        return False
    
    except Exception as e:
        log(f"Warning: Could not check for duplicates: {e}")
        return False

def main():
    log("=" * 80)
    log("Starting Isar water level fetch")
    
    # Fetch latest value
    measurement = fetch_latest_value()
    
    if not measurement:
        log("FAILED: Could not fetch data")
        log("=" * 80)
        return 1
    
    # Check for duplicates
    if check_duplicate(measurement):
        log(f"SKIPPED: Measurement already exists (timestamp: {measurement['timestamp']})")
        log("=" * 80)
        return 0
    
    # Save to file
    if save_to_json_log(measurement):
        log("SUCCESS: Measurement saved")
        log("=" * 80)
        return 0
    else:
        log("FAILED: Could not save measurement")
        log("=" * 80)
        return 1

if __name__ == "__main__":
    sys.exit(main())
