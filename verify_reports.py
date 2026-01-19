from database import DatabaseManager
from datetime import datetime

def verify_backend():
    print("🚀 Starting Backend Verification...")
    db = DatabaseManager()
    
    today = datetime.now().strftime('%Y-%m-%d')
    print(f"📅 Date: {today}")
    
    # 1. Test Expenses
    print("\n1. Testing Expenses...")
    try:
        db.add_expense(today, "Test Expense", 500, "Shop Maintenance")
        expenses = db.get_expenses(today)
        assert not expenses.empty, "Expenses table is empty"
        assert expenses.iloc[-1]['amount'] == 500.0, "Expense amount mismatch"
        print("✅ Expense added and retrieved successfully.")
    except Exception as e:
        print(f"❌ Expense Test Failed: {e}")

    # 2. Test Ledger / Cash Flow
    print("\n2. Testing Cash Flow...")
    try:
        # Add a dummy credit (Cash In)
        db.add_ledger_entry("Test Customer", "Cash Payment", 0, 1000, today)
        
        cash_in, cash_out, net = db.get_daily_cash_flow(today)
        print(f"   Cash In: {cash_in}, Cash Out: {cash_out}, Net: {net}")
        
        # We expect at least 1000 in and 500 out (from step 1) + any previous data
        assert cash_in >= 1000, "Cash In should include the new 1000"
        assert cash_out >= 500, "Cash Out should include the new 500"
        
        print("✅ Cash Flow logic verified.")
    except Exception as e:
        print(f"❌ Cash Flow Test Failed: {e}")

    # 3. Test Recovery List
    print("\n3. Testing Customer Recovery List...")
    try:
        recovery = db.get_customer_recovery_list()
        if not recovery.empty:
            print(f"   Found {len(recovery)} customers.")
            top_customer = recovery.iloc[0]
            print(f"   Top Debt: {top_customer['name']} with {top_customer['net_outstanding']}")
            
            # Check sorting
            if len(recovery) > 1:
                assert recovery.iloc[0]['net_outstanding'] >= recovery.iloc[1]['net_outstanding'], "List not sorted by outstanding balance"
            print("✅ Recovery List verified.")
        else:
            print("⚠️ No customers found to test recovery list.")
    except Exception as e:
        print(f"❌ Recovery List Test Failed: {e}")

    # 4. Inventory Valuation
    print("\n4. Testing Inventory Valuation...")
    try:
        val = db.get_inventory_valuation()
        print(f"   Total Stock Value: {val}")
        assert isinstance(val, float), "Valuation should be a float"
        print("✅ Inventory Valuation verified.")
    except Exception as e:
        print(f"❌ Inventory Valuation Test Failed: {e}")

    print("\n🎉 Verification Complete!")

if __name__ == "__main__":
    verify_backend()
