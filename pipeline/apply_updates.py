#!/usr/bin/env python3
"""
Apply updates from data/updates to data/fluesse-* folders
Moves update files and ensures no duplicates
"""

import shutil
from pathlib import Path
import sys

# Directories
PROJECT_ROOT = Path(__file__).parent.parent
UPDATES_DIR = PROJECT_ROOT / "data" / "updates"
DATA_DIR = PROJECT_ROOT / "data"

def apply_updates():
    """
    Move update files from data/updates to their respective data folders
    """
    print("=" * 80)
    print("🔄 Applying data updates")
    print("=" * 80)
    print()
    
    # Define update mappings
    updates = [
        {
            "name": "Wasserstand",
            "source": UPDATES_DIR / "fluesse-wasserstand" / "16005701_26.12.2025_25.01.2026_ezw_0.csv",
            "target_dir": DATA_DIR / "fluesse-wasserstand",
        },
        {
            "name": "Wassertemperatur",
            "source": UPDATES_DIR / "fluesse-wassertemperatur" / "16005701_26.12.2025_25.01.2026_ezw_0.csv",
            "target_dir": DATA_DIR / "fluesse-wassertemperatur",
        }
    ]
    
    success_count = 0
    
    for update in updates:
        name = update["name"]
        source = update["source"]
        target_dir = update["target_dir"]
        target = target_dir / source.name
        
        print(f"📦 Processing {name} update...")
        print(f"   Source: {source}")
        print(f"   Target: {target}")
        
        # Check if source exists
        if not source.exists():
            print(f"   ❌ Source file not found!")
            continue
        
        # Check if target already exists
        if target.exists():
            print(f"   ⚠️  Target file already exists!")
            
            # Compare file sizes
            source_size = source.stat().st_size
            target_size = target.stat().st_size
            
            if source_size == target_size:
                print(f"   ℹ️  Files are identical (same size: {source_size} bytes)")
                print(f"   ✅ Skipping (already applied)")
                success_count += 1
                continue
            else:
                print(f"   ⚠️  Files differ (source: {source_size} bytes, target: {target_size} bytes)")
                
                # Ask user what to do
                print(f"   Options:")
                print(f"     1) Skip (keep existing)")
                print(f"     2) Overwrite (replace with update)")
                print(f"     3) Backup and overwrite")
                
                choice = input(f"   Choose [1/2/3]: ").strip()
                
                if choice == "1":
                    print(f"   ✅ Skipped (keeping existing)")
                    continue
                elif choice == "3":
                    # Backup existing
                    backup = target.with_suffix(target.suffix + '.backup')
                    shutil.copy2(target, backup)
                    print(f"   📦 Backed up to: {backup}")
                elif choice != "2":
                    print(f"   ❌ Invalid choice, skipping")
                    continue
        
        # Ensure target directory exists
        target_dir.mkdir(parents=True, exist_ok=True)
        
        # Copy file
        try:
            shutil.copy2(source, target)
            print(f"   ✅ Successfully copied update")
            success_count += 1
        except Exception as e:
            print(f"   ❌ Error copying file: {e}")
    
    print()
    print("=" * 80)
    print(f"📊 Summary: {success_count}/{len(updates)} updates applied successfully")
    print("=" * 80)
    print()
    
    if success_count == len(updates):
        print("✅ All updates applied successfully!")
        print()
        print("📋 Next steps:")
        print("   1. Run ingest script to convert updates to Parquet")
        print("   2. Verify data completeness")
        print("   3. Set up cron job for future updates")
        print()
        return 0
    else:
        print("⚠️  Some updates were not applied")
        return 1

def main():
    print()
    print("🌊 Isar Water Data - Update Manager")
    print()
    
    # Check if updates directory exists
    if not UPDATES_DIR.exists():
        print(f"❌ Updates directory not found: {UPDATES_DIR}")
        return 1
    
    # Check if update files exist
    update_files = list(UPDATES_DIR.glob("**/*.csv"))
    
    if not update_files:
        print(f"❌ No CSV update files found in: {UPDATES_DIR}")
        return 1
    
    print(f"Found {len(update_files)} update file(s):")
    for f in update_files:
        print(f"  • {f.relative_to(UPDATES_DIR)}")
    print()
    
    # Apply updates
    return apply_updates()

if __name__ == "__main__":
    sys.exit(main())
