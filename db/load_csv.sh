#!/bin/bash
# ============================================================
#  DWH Assistant — CSV Seed Data Loader
#  Runs inside PostgreSQL container on first initialization
#  (placed in /docker-entrypoint-initdb.d/)
# ============================================================

set -e

SEED_DIR="/seed_data"

# Tables ordered by FK dependencies (parents first)
ORDERED_TABLES=(
    "countries"
    "categories"
    "shipping_carriers"
    "merchants"
    "users"
    "products"
    "orders"
    "order_items"
)

echo "============================================"
echo "  CSV Seed Data Loader"
echo "============================================"

if [ ! -d "$SEED_DIR" ]; then
    echo "WARNING: Seed directory $SEED_DIR not found. Skipping CSV loading."
    exit 0
fi

csv_count=$(find "$SEED_DIR" -maxdepth 1 -name "*.csv" 2>/dev/null | wc -l)
if [ "$csv_count" -eq 0 ]; then
    echo "No CSV files found in $SEED_DIR. Skipping."
    exit 0
fi

echo "Found $csv_count CSV file(s) in $SEED_DIR"
echo ""

loaded=0
skipped=0

for table in "${ORDERED_TABLES[@]}"; do
    csv_file="$SEED_DIR/${table}.csv"

    if [ -f "$csv_file" ]; then
        echo "Loading: ${table}.csv -> table '${table}'"

        psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
            \COPY ${table} FROM '${csv_file}' WITH (FORMAT csv, HEADER true);
EOSQL

        row_count=$(psql -t -A --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
            -c "SELECT count(*) FROM ${table};")
        echo "  -> $row_count rows loaded into '${table}'"
        echo ""
        loaded=$((loaded + 1))
    else
        echo "Skipping: ${table}.csv not found"
        skipped=$((skipped + 1))
    fi
done

# Check for extra CSVs that don't match any known table
for csv_file in "$SEED_DIR"/*.csv; do
    [ -f "$csv_file" ] || continue
    basename=$(basename "$csv_file" .csv)
    match=0
    for table in "${ORDERED_TABLES[@]}"; do
        if [ "$basename" = "$table" ]; then
            match=1
            break
        fi
    done
    if [ "$match" -eq 0 ]; then
        echo "WARNING: Unknown CSV file '${basename}.csv' — no matching table in schema"
    fi
done

echo ""
echo "============================================"
echo "  Done: $loaded loaded, $skipped skipped"
echo "============================================"
