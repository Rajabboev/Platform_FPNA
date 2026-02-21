"""Test DWH Integration API endpoints"""
import requests
import json

BASE_URL = "http://localhost:8000/api/v1"

def test_balans_summary():
    """Test the balans_ato summary endpoint"""
    print("=" * 60)
    print("Testing DWH Balans Summary Endpoint")
    print("=" * 60)
    
    # Connection ID 2 is DWH_Main
    resp = requests.get(f"{BASE_URL}/dwh/connections/2/balans-summary", timeout=30)
    print(f"Status: {resp.status_code}")
    
    if resp.status_code == 200:
        data = resp.json()
        print(f"\nDWH Summary:")
        print(f"  Total Rows: {data.get('total_rows', 0):,}")
        print(f"  Unique Accounts: {data.get('unique_accounts', 0)}")
        print(f"  Unique Dates: {data.get('unique_dates', 0)}")
        print(f"  Unique Currencies: {data.get('unique_currencies', 0)}")
        print(f"  Unique Branches: {data.get('unique_branches', 0)}")
        print(f"  Date Range: {data.get('date_range', {}).get('min')} to {data.get('date_range', {}).get('max')}")
        print(f"\n  Account Classes:")
        for ac in data.get('account_classes', []):
            print(f"    Class {ac['class']}: {ac['count']} accounts")
    else:
        print(f"Error: {resp.text}")

def test_balans_preview():
    """Test the balans_ato preview endpoint"""
    print("\n" + "=" * 60)
    print("Testing DWH Balans Preview Endpoint")
    print("=" * 60)
    
    resp = requests.get(f"{BASE_URL}/dwh/connections/2/balans-preview", 
                       params={"limit": 10}, timeout=30)
    print(f"Status: {resp.status_code}")
    
    if resp.status_code == 200:
        data = resp.json()
        print(f"\nPreview ({data.get('count', 0)} records):")
        for row in data.get('data', [])[:5]:
            print(f"  {row['account_code']} | {row['snapshot_date']} | "
                  f"Currency:{row['currency_code']} | Balance:{row['balance_uzs']:,.0f}")
    else:
        print(f"Error: {resp.text}")

def test_ingestion():
    """Test snapshot ingestion"""
    print("\n" + "=" * 60)
    print("Testing Snapshot Ingestion (small batch)")
    print("=" * 60)
    
    # Test with a limited date range
    resp = requests.post(f"{BASE_URL}/dwh/ingest/snapshots", 
                        json={
                            "connection_id": 2,
                            "source_table": "balans_ato",
                            "source_schema": "dbo",
                            "start_date": "2025-01-01",
                            "end_date": "2025-01-31",
                            "aggregate_branches": True
                        }, timeout=120)
    print(f"Status: {resp.status_code}")
    
    if resp.status_code == 200:
        data = resp.json()
        print(f"\nIngestion Result:")
        print(f"  Batch ID: {data.get('batch_id')}")
        print(f"  Status: {data.get('status')}")
        print(f"  Total Records: {data.get('total_records', 0):,}")
        print(f"  Imported: {data.get('imported_records', 0):,}")
        print(f"  Failed: {data.get('failed_records', 0)}")
    else:
        print(f"Error: {resp.text}")

if __name__ == "__main__":
    test_balans_summary()
    test_balans_preview()
    test_ingestion()
    
    print("\n" + "=" * 60)
    print("All tests completed!")
    print("=" * 60)
