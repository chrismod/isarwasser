#!/bin/bash
set -e

echo "🔧 Setting up Isarwasser data pipeline..."

# Check if we're in the right directory
if [ ! -f "pipeline/ingest_lfu_csv_to_parquet.py" ]; then
    echo "❌ Error: Must be run from the isarwasser root directory"
    exit 1
fi

# Install Python dependencies if not already installed
echo "📦 Checking Python dependencies..."
python3 -m pip install -q --break-system-packages -r pipeline/requirements.txt

# Create data directories
echo "📁 Creating data directories..."
mkdir -p data/parquet
mkdir -p data/current
mkdir -p web/public/data/parquet
mkdir -p web/public/data/current

# Generate Parquet files from CSV
echo "🔄 Converting CSV data to Parquet format..."
python3 pipeline/ingest_lfu_csv_to_parquet.py

# Copy to web public directory
echo "📋 Copying Parquet files to web directory..."
if [ -d "data/parquet" ]; then
    cp -v data/parquet/*.parquet web/public/data/parquet/ 2>/dev/null || echo "No parquet files found yet"
fi

# Run initial scraper
echo "🌐 Fetching initial live data..."
python3 pipeline/fetch_and_store_isar.py || echo "Warning: Initial fetch failed, will retry on next cron run"

# Copy live data to web directory
echo "📋 Copying live data to web directory..."
if [ -d "data/current" ]; then
    cp -v data/current/*.jsonl web/public/data/current/ 2>/dev/null || echo "No live data yet"
fi

echo "✅ Data pipeline setup complete!"
echo ""
echo "📊 Generated files:"
ls -lh data/parquet/*.parquet 2>/dev/null || echo "  No parquet files"
ls -lh data/current/*.jsonl 2>/dev/null || echo "  No live data files"
echo ""
echo "🚀 You can now start the Docker containers with:"
echo "   docker-compose up -d --build"
