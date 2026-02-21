"""
Test script for the complete baseline workflow
"""
import requests
import json

BASE_URL = "http://localhost:8000/api/v1"

# Get auth token
def get_token():
    response = requests.post(f"{BASE_URL}/auth/login-simple", json={
        "username": "admin",
        "password": "password123"
    })
    if response.status_code == 200:
        return response.json().get("access_token")
    print(f"Login failed: {response.text}")
    return None

def main():
    token = get_token()
    if not token:
        print("Failed to get auth token")
        return
    
    headers = {"Authorization": f"Bearer {token}"}
    
    print("\n" + "="*60)
    print("BUDGET PLANNING WORKFLOW TEST")
    print("="*60)
    
    # 1. Get workflow status
    print("\n1. Checking workflow status for FY 2026...")
    response = requests.get(f"{BASE_URL}/baseline/workflow-status/2026", headers=headers)
    if response.status_code == 200:
        status = response.json()
        print(f"   Ingest: {status['steps']['1_ingest']['status']}")
        print(f"   Calculate: {status['steps']['2_calculate']['status']}")
        print(f"   Plan: {status['steps']['3_plan']['status']}")
        print(f"   Export: {status['steps']['4_export']['status']}")
    else:
        print(f"   Error: {response.status_code} - {response.text}")
    
    # 2. Get connections
    print("\n2. Getting DWH connections...")
    response = requests.get(f"{BASE_URL}/connections", headers=headers)
    if response.status_code == 200:
        connections = response.json()
        print(f"   Found {len(connections)} connections")
        for conn in connections:
            print(f"   - {conn['name']} (ID: {conn['id']}, DB: {conn['database_name']})")
        
        if connections:
            conn_id = connections[0]['id']
            
            # 3. Test ingestion
            print(f"\n3. Running ingestion from connection {conn_id}...")
            response = requests.post(f"{BASE_URL}/baseline/ingest", 
                headers=headers,
                json={
                    "connection_id": conn_id,
                    "start_year": 2023,
                    "end_year": 2025
                }
            )
            if response.status_code == 200:
                result = response.json()
                print(f"   Status: {result['status']}")
                print(f"   Records imported: {result['records_imported']}")
                print(f"   Unique accounts: {result['unique_accounts']}")
            else:
                print(f"   Error: {response.status_code} - {response.text}")
            
            # 4. Get baseline data summary
            print("\n4. Getting baseline data summary...")
            response = requests.get(f"{BASE_URL}/baseline/data/summary", headers=headers)
            if response.status_code == 200:
                summary = response.json()
                print(f"   Data by year:")
                for year_data in summary.get('by_year', []):
                    print(f"   - {year_data['year']}: {year_data['accounts']} accounts, {year_data['records']} records")
            else:
                print(f"   Error: {response.status_code} - {response.text}")
            
            # 5. Calculate baselines
            print("\n5. Calculating baselines for FY 2026...")
            response = requests.post(f"{BASE_URL}/baseline/calculate",
                headers=headers,
                json={
                    "fiscal_year": 2026,
                    "method": "simple_average",
                    "source_years": [2023, 2024, 2025]
                }
            )
            if response.status_code == 200:
                result = response.json()
                print(f"   Status: {result['status']}")
                print(f"   Baselines created: {result['baselines_created']}")
            else:
                print(f"   Error: {response.status_code} - {response.text}")
            
            # 6. Get baseline summary
            print("\n6. Getting baseline summary...")
            response = requests.get(f"{BASE_URL}/baseline/baselines/summary", 
                headers=headers,
                params={"fiscal_year": 2026}
            )
            if response.status_code == 200:
                summary = response.json()
                print(f"   Total accounts: {summary['total_accounts']}")
                print(f"   Total amount: {summary['total_amount']:,.2f}")
            else:
                print(f"   Error: {response.status_code} - {response.text}")
            
            # 7. Create planned budgets with 5% adjustment
            print("\n7. Creating planned budgets with 5% driver adjustment...")
            response = requests.post(f"{BASE_URL}/baseline/planned/bulk",
                headers=headers,
                json={
                    "fiscal_year": 2026,
                    "driver_adjustment_pct": 0.05,
                    "scenario": "BASE"
                }
            )
            if response.status_code == 200:
                result = response.json()
                print(f"   Status: {result['status']}")
                print(f"   Budgets created: {result['budgets_created']}")
            else:
                print(f"   Error: {response.status_code} - {response.text}")
            
            # 8. Get planned summary
            print("\n8. Getting planned budget summary...")
            response = requests.get(f"{BASE_URL}/baseline/planned/summary",
                headers=headers,
                params={"fiscal_year": 2026}
            )
            if response.status_code == 200:
                summary = response.json()
                print(f"   By status: {summary['by_status']}")
            else:
                print(f"   Error: {response.status_code} - {response.text}")
            
            # 9. Final workflow status
            print("\n9. Final workflow status...")
            response = requests.get(f"{BASE_URL}/baseline/workflow-status/2026", headers=headers)
            if response.status_code == 200:
                status = response.json()
                print(f"   Ingest: {status['steps']['1_ingest']['status']} ({status['steps']['1_ingest']['records']} records)")
                print(f"   Calculate: {status['steps']['2_calculate']['status']} ({status['steps']['2_calculate']['baselines']} baselines)")
                print(f"   Plan: {status['steps']['3_plan']['status']} ({status['steps']['3_plan']['by_status']})")
                print(f"   Export: {status['steps']['4_export']['status']}")
            else:
                print(f"   Error: {response.status_code} - {response.text}")
    
    print("\n" + "="*60)
    print("TEST COMPLETE")
    print("="*60)

if __name__ == "__main__":
    main()
