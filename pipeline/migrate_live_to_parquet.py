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

def read_jsonl_files(days_back: int = 7):
    """Read JSONL files from the last N days"""
    measurements = []
    
    for i in range(days_back):
        date = datetime.now() - timedelta(days=i)
        date_str = date.strftime('%Y-%m-%d')
        jsonl_file = CURRENT_DATA_DIR / f"water_level_{date_str}.jsonl"
        
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
                            'parameter': 'water_level_cm',
                            'ts': pd.Timestamp(data['timestamp']),
                            'value': float(data['value_cm']),
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

def main():
    print("=" * 80)
    print("🔄 Migrating Live JSONL Data to Parquet")
    print("=" * 80)
    print()
    
    # Read JSONL files
    measurements = read_jsonl_files(days_back=7)
    
    if not measurements:
        print("❌ No measurements found in JSONL files")
        return 1
    
    print(f"✅ Found {len(measurements)} measurements")
    print()
    
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
    parquet_file = PARQUET_DIR / "station_16005701_water_level_cm.parquet"
    
    # Merge with existing data
    final_df = merge_with_existing_parquet(df, parquet_file)
    
    # Write to Parquet
    print()
    print(f"Writing to {parquet_file}...")
    table = pa.Table.from_pandas(final_df, schema=schema, preserve_index=False)
    pq.write_table(table, parquet_file, compression='zstd')
    
    # Sync to web public folder
    print(f"Syncing to web public folder...")
    web_file = WEB_PARQUET_DIR / parquet_file.name
    web_file.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, web_file, compression='zstd')
    
    print()
    print("=" * 80)
    print("✅ Migration Complete!")
    print("=" * 80)
    print()
    print(f"📊 Final dataset:")
    print(f"   Total records: {len(final_df)}")
    print(f"   Date range: {final_df['ts'].min()} to {final_df['ts'].max()}")
    print()
    print("💡 Next steps:")
    print("   1. Run ingest_lfu_csv_to_parquet.py to regenerate daily aggregates")
    print("   2. Refresh web app to see updated data")
    print()
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
