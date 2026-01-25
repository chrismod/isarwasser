#!/usr/bin/env python3
"""
Test script to check if München/Isar is available on PEGELONLINE API
"""

import requests
import json
from datetime import datetime

# PEGELONLINE API base URL
BASE_URL = "https://www.pegelonline.wsv.de/webservices/rest-api/v2"

def search_station():
    """Search for München/Isar station"""
    print("🔍 Searching for München/Isar station on PEGELONLINE...\n")
    
    # Try different search methods
    searches = [
        ("by water name", f"{BASE_URL}/stations.json?waters=ISAR"),
        ("by fuzzy name", f"{BASE_URL}/stations.json?fuzzyId=münchen"),
        ("by fuzzy name (alternative)", f"{BASE_URL}/stations.json?fuzzyId=muenchen"),
    ]
    
    stations = []
    
    for search_name, url in searches:
        print(f"Trying: {search_name}")
        print(f"URL: {url}")
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if data:
                print(f"✅ Found {len(data)} station(s)\n")
                stations.extend(data)
            else:
                print(f"❌ No stations found\n")
        except requests.exceptions.Timeout:
            print(f"⏱️  Request timed out\n")
        except Exception as e:
            print(f"❌ Error: {e}\n")
    
    # Remove duplicates based on UUID
    unique_stations = {s['uuid']: s for s in stations}.values()
    
    return list(unique_stations)

def print_station_info(station):
    """Print detailed station information"""
    print("\n" + "="*70)
    print(f"📍 Station: {station.get('longname', 'N/A')}")
    print("="*70)
    print(f"UUID:       {station.get('uuid', 'N/A')}")
    print(f"Number:     {station.get('number', 'N/A')}")
    print(f"Shortname:  {station.get('shortname', 'N/A')}")
    print(f"Water:      {station.get('water', {}).get('longname', 'N/A')}")
    print(f"Agency:     {station.get('agency', 'N/A')}")
    print(f"Km:         {station.get('km', 'N/A')}")
    print(f"Latitude:   {station.get('latitude', 'N/A')}")
    print(f"Longitude:  {station.get('longitude', 'N/A')}")

def get_current_measurement(station_uuid):
    """Get current water level measurement"""
    print("\n" + "-"*70)
    print("📊 Fetching current measurement...")
    print("-"*70)
    
    url = f"{BASE_URL}/stations/{station_uuid}/W/currentmeasurement.json"
    
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        timestamp = data.get('timestamp', 'N/A')
        value = data.get('value', 'N/A')
        
        print(f"✅ Current water level: {value} cm")
        print(f"   Timestamp: {timestamp}")
        print(f"   State (MNW/MHW): {data.get('stateMnwMhw', 'N/A')}")
        
        return data
    except Exception as e:
        print(f"❌ Error fetching measurement: {e}")
        return None

def get_timeseries_info(station_uuid):
    """Get information about available timeseries"""
    print("\n" + "-"*70)
    print("📈 Fetching timeseries information...")
    print("-"*70)
    
    url = f"{BASE_URL}/stations/{station_uuid}.json?includeTimeseries=true&includeCharacteristicValues=true"
    
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        timeseries = data.get('timeseries', [])
        
        if timeseries:
            print(f"✅ Found {len(timeseries)} timeseries:")
            for ts in timeseries:
                print(f"\n   • {ts.get('longname', 'N/A')}")
                print(f"     Shortname: {ts.get('shortname', 'N/A')}")
                print(f"     Unit: {ts.get('unit', 'N/A')}")
                print(f"     Interval: every {ts.get('equidistance', 'N/A')} minutes")
                
                # Characteristic values
                char_values = ts.get('characteristicValues', [])
                if char_values:
                    print(f"     Characteristic values:")
                    for cv in char_values[:5]:  # Show first 5
                        print(f"       - {cv.get('shortname', 'N/A')}: {cv.get('value', 'N/A')} {cv.get('unit', 'N/A')}")
        else:
            print("❌ No timeseries found")
        
        return timeseries
    except Exception as e:
        print(f"❌ Error fetching timeseries: {e}")
        return None

def main():
    print("\n" + "🌊 "*20)
    print("PEGELONLINE API Test - München/Isar")
    print("🌊 "*20 + "\n")
    
    # Search for stations
    stations = search_station()
    
    if not stations:
        print("\n❌ No stations found for München/Isar on PEGELONLINE")
        print("\n💡 This means München/Isar is likely only available on:")
        print("   • https://www.hnd.bayern.de (Hochwassernachrichtendienst Bayern)")
        print("   • https://www.gkd.bayern.de (Gewässerkundlicher Dienst Bayern)")
        print("\n⚠️  These sites don't have a documented public API.")
        print("   Consider contacting: hnd@lfu.bayern.de")
        return
    
    # Print all found stations
    print(f"\n✅ Found {len(stations)} station(s) total:")
    for i, station in enumerate(stations, 1):
        print(f"{i}. {station.get('longname', 'N/A')} ({station.get('water', {}).get('longname', 'N/A')})")
    
    # Get details for each station
    for station in stations:
        print_station_info(station)
        
        uuid = station.get('uuid')
        if uuid:
            get_current_measurement(uuid)
            get_timeseries_info(uuid)
    
    print("\n" + "="*70)
    print("✅ Test completed!")
    print("="*70 + "\n")
    
    # Print API usage examples
    if stations:
        uuid = stations[0].get('uuid')
        print("\n💡 Example API calls:")
        print(f"   Current value:  {BASE_URL}/stations/{uuid}/W/currentmeasurement.json")
        print(f"   Last 24 hours:  {BASE_URL}/stations/{uuid}/W/measurements.json?start=P1D")
        print(f"   Last 7 days:    {BASE_URL}/stations/{uuid}/W/measurements.json?start=P7D")
        print(f"   CSV format:     {BASE_URL}/stations/{uuid}/W/measurements.csv?start=P7D")
        print()

if __name__ == "__main__":
    main()
