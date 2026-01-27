#!/usr/bin/env python3
"""
Migrate live JSONL data to Parquet format
Run this daily/weekly to incorporate live measurements into the main dataset
"""

import json
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from pathlib import Path
from datetime import datetime, timedelta
import sys

PROJECT_ROOT = Path(__file__).parent.parent
CURRENT_DATA_DIR = PROJECT_ROOT / "data" / "current"
PARQUET_DIR = PROJECT_ROOT / "data" / "parquet" / "raw"
WEB_PARQUET_DIR = PROJECT_ROOT / "web" / "public" / "data" / "parquet" / "raw"

def read_jsonl_files(parameter: str, days_back: int = 7):
    """Read JSONL files from the last N days for a specific parameter"""
    measurements = []
    
    # Determine filename pattern and value field based on parameter
    if parameter == 'water_level_cm':
        file_prefix = 'water_level'
        value_field = 'value_cm'
    elif parameter == 'water_temperature_c':
        file_prefix = 'water_temperature'
        value_field = 'value_celsius'
    else:
        raise ValueError(f"Unknown parameter: {parameter}")
    
    for i in range(days_back):
        date = datetime.now() - timedelta(days=i)
        date_str = date.strftime('%Y-%m-%d')
        jsonl_file = CURRENT_DATA_DIR / f"{file_prefix}_{date_str}.jsonl"
        
        if not jsonl_file.exists():
            continue
        
        print(f"Reading {jsonl_file.name}...")
        
        with open(jsonl_file, 'r') as f:
            for line in f:
                if line.strip():
                    try:
                        data = json.loads(line)
                        measurements.append({
                            'station_id': int(data['station_id']),
                            'parameter': parameter,
                            'ts': pd.Timestamp(data['timestamp']),
                            'value': float(data[value_field]),
                            'status': 'Rohdaten',  # Live data status
                        })
                    except Exception as e:
                        print(f"  Warning: Could not parse line: {e}")
    
    return measurements

def merge_with_existing_parquet(new_data: pd.DataFrame, parquet_file: Path):
    """Merge new data with existing Parquet file, removing duplicates"""
    
    if parquet_file.exists():
        print(f"Reading existing data from {parquet_file.name}...")
        existing_df = pd.read_parquet(parquet_file)
        
        # Combine and remove duplicates based on timestamp
        combined = pd.concat([existing_df, new_data], ignore_index=True)
        combined = combined.drop_duplicates(subset=['ts'], keep='last')
        combined = combined.sort_values('ts')
        
        print(f"  Existing records: {len(existing_df)}")
        print(f"  New records: {len(new_data)}")
        print(f"  After dedup: {len(combined)}")
        print(f"  Net new: +{len(combined) - len(existing_df)}")
        
        return combined
    else:
        print(f"Creating new file {parquet_file.name}...")
        return new_data.sort_values('ts')

def migrate_parameter(parameter: str, days_back: int = 7):
    """Migrate a single parameter (water_level_cm or water_temperature_c)"""
    print(f"\n--- Migrating {parameter} ---")
    
    # Read JSONL files
    measurements = read_jsonl_files(parameter, days_back=days_back)
    
    if not measurements:
        print(f"⚠️  No measurements found for {parameter}")
        return 0
    
    print(f"✅ Found {len(measurements)} measurements")
    
    # Convert to DataFrame
    df = pd.DataFrame(measurements)
    
    # Define Parquet schema
    schema = pa.schema([
        ('station_id', pa.int32()),
        ('parameter', pa.string()),
        ('ts', pa.timestamp('ns')),
        ('value', pa.float64()),
        ('status', pa.string()),
    ])
    
    # Parquet file path
    parquet_file = PARQUET_DIR / f"station_16005701_{parameter}.parquet"
    
    # Ensure directories exist
    PARQUET_DIR.mkdir(parents=True, exist_ok=True)
    WEB_PARQUET_DIR.mkdir(parents=True, exist_ok=True)
    
    # Merge with existing data
    final_df = merge_with_existing_parquet(df, parquet_file)
    
    # Write to Parquet
    print(f"Writing to {parquet_file}...")
    table = pa.Table.from_pandas(final_df, schema=schema, preserve_index=False)
    pq.write_table(table, parquet_file, compression='zstd')
    
    # Sync to web public folder
    print(f"Syncing to web public folder...")
    web_file = WEB_PARQUET_DIR / parquet_file.name
    pq.write_table(table, web_file, compression='zstd')
    
    print(f"📊 {parameter}:")
    print(f"   Total records: {len(final_df)}")
    print(f"   Date range: {final_df['ts'].min()} to {final_df['ts'].max()}")
    
    return len(final_df)

def main():
    print("=" * 80)
    print("🔄 Migrating Live JSONL Data to Parquet")
    print("=" * 80)
    
    total_records = 0
    
    # Migrate water level
    total_records += migrate_parameter('water_level_cm', days_back=7)
    
    # Migrate water temperature
    total_records += migrate_parameter('water_temperature_c', days_back=7)
    
    print()
    print("=" * 80)
    print("✅ Migration Complete!")
    print("=" * 80)
    print(f"   Total records processed: {total_records}")
    print()
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
