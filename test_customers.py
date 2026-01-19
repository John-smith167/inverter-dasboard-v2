import pandas as pd
from database import DatabaseManager
import time

def test_currency_logic():
    print("🧪 Testing Customer Database Logic...")
    db = DatabaseManager()
    
    # 1. Add Customer
    print("\n1. Adding Test Customer...")
    # Using a unique name to avoid conflicts if re-running
    test_name = f"Test_Client_{int(time.time())}"
    c_id = db.add_customer(test_name, "Test City", "03001234567", 5000.0)
    print(f"   ✅ Added Customer: {test_name} with ID: {c_id}")
    
    # 2. Verify Customer Exists
    print("\n2. Verifying Customer Retrieval...")
    customers = db.get_all_customers()
    assert test_name in customers['name'].values, "Customer not found in DB!"
    print("   ✅ Customer found in DB.")
    
    # 3. Test Balance (Initial)
    print("\n3. Testing Initial Balance...")
    balances = db.get_customer_balances()
    cust_bal = balances[balances['name'] == test_name].iloc[0]
    print(f"   Initial Outstanding: {cust_bal['net_outstanding']}")
    assert cust_bal['net_outstanding'] == 5000.0, f"Expected 5000.0, got {cust_bal['net_outstanding']}"
    print("   ✅ Initial balance correct.")
    
    # 4. Add Ledger Transaction (Debit - Sale)
    print("\n4. Adding Ledger Debit (Sale of 2000)...")
    db.add_ledger_entry(test_name, "Test Sale", 2000.0, 0.0)
    
    # 5. Add Ledger Transaction (Credit - Payment)
    print("\n5. Adding Ledger Credit (Payment of 3000)...")
    db.add_ledger_entry(test_name, "Test Payment", 0.0, 3000.0)
    
    # 6. Verify Final Balance
    # Expected: 5000 (Open) + 2000 (Debit) - 3000 (Credit) = 4000
    print("\n6. Verifying Final Balance...")
    balances_final = db.get_customer_balances()
    final_bal = balances_final[balances_final['name'] == test_name].iloc[0]['net_outstanding']
    print(f"   Final Outstanding: {final_bal}")
    
    assert final_bal == 4000.0, f"Expected 4000.0, got {final_bal}"
    print("   ✅ Final balance calculation CORRECT!")

if __name__ == "__main__":
    test_currency_logic()
