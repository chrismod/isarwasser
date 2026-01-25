#!/bin/bash
set -e

echo "🔧 Setting up Isarwasser data pipeline..."

# Check if we're in the right directory
if [ ! -f "pipeline/ingest_lfu_csv_to_parquet.py" ]; then
    echo "❌ Error: Must be run from the isarwasser root directory"
    exit 1
fi

# Install Node.js if not present
if ! command -v node &> /dev/null; then
    echo "📦 Installing Node.js..."
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
    apt-get install -y nodejs
fi

# Install Python dependencies
echo "📦 Checking Python dependencies..."
python3 -m pip install -q --break-system-packages -r pipeline/requirements.txt

# Install Node dependencies for pipeline
echo "📦 Installing Node.js dependencies..."
cd pipeline
npm install
cd ..

# Create data directories
echo "📁 Creating data directories..."
mkdir -p data/parquet
mkdir -p data/current
mkdir -p web/public/data/parquet
mkdir -p web/public/data/current

# Generate Parquet files using Node.js (more reliable than Python for this)
echo "🔄 Converting CSV data to Parquet format..."
node pipeline/ingest_lfu_csv_to_parquet_daily_only.mjs \
  --station-id 16005701 \
  --start-date 1975-01-01 \
  --sync-to-web-public web/public/data/parquet

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
ls -lh web/public/data/parquet/*.parquet 2>/dev/null || echo "  No parquet files"
ls -lh data/current/*.jsonl 2>/dev/null || echo "  No live data files"
echo ""
echo "🚀 You can now start the Docker containers with:"
echo "   docker-compose up -d"
