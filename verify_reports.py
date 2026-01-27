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

    # 3. Test Recovery List & Classification
    print("\n3. Testing Customer Recovery List (Classification)...")
    try:
        # Create Dummy Customer for Counting Test
        dummy_name = "Test Counters"
        db.add_customer(dummy_name, "Lab", "000", 0)
        
        # Add Transactions
        db.add_ledger_entry(dummy_name, "Sold Inverter 5KW", 1000, 0, today)  # Inverter
        db.add_ledger_entry(dummy_name, "Repair Charger", 500, 0, today)      # Charger
        db.add_ledger_entry(dummy_name, "Solar Kit Complete", 5000, 0, today) # Kit
        db.add_ledger_entry(dummy_name, "Misc Wiring", 200, 0, today)         # Other
        db.add_ledger_entry(dummy_name, "Inverter Repair", 300, 0, today)     # Inverter (Count 2)
        
        recovery = db.get_customer_recovery_list()
        
        if not recovery.empty:
            # Find our dummy
            dummy = recovery[recovery['name'] == dummy_name]
            if not dummy.empty:
                row = dummy.iloc[0]
                print(f"   Counts -> Inv: {row['inverter_count']}, Chg: {row['charger_count']}, Kit: {row['kit_count']}, Oth: {row['other_count']}")
                
                assert row['inverter_count'] == 2, f"Expected 2 Inverters, got {row['inverter_count']}"
                assert row['charger_count'] == 1, f"Expected 1 Charger, got {row['charger_count']}"
                assert row['kit_count'] == 1, f"Expected 1 Kit, got {row['kit_count']}"
                assert row['other_count'] == 1, f"Expected 1 Other, got {row['other_count']}"
                print("✅ Category Counting verified.")
            else:
                 print("⚠️ Dummy customer not found in recovery list.")
        else:
            print("⚠️ Recovery list empty.")
    except Exception as e:
        print(f"❌ Recovery List Test Failed: {e}")

    # 4. Test Employee Delete & Ledger
    print("\n4. Testing Employee Management & Ledger Delete...")
    try:
        # Create Employee
        db.add_employee("Temp Emp", "Manager", "123", 0, "CNIC")
        emps = db.get_all_employees()
        assert "Temp Emp" in emps['name'].values, "Employee not added"
        
        # Add Ledger Entry
        db.add_employee_ledger_entry("Temp Emp", today, "Work Log", "Test Work", 1000, 0)
        
        # Verify Ledger Exists
        ledger = db.get_employee_ledger("Temp Emp")
        assert not ledger.empty, "Ledger entry not added"
        
        # Delete Ledger specifically
        db.delete_employee_ledger("Temp Emp")
        
        # Verify Ledger Gone
        ledger_after = db.get_employee_ledger("Temp Emp")
        assert ledger_after.empty, "Ledger history not deleted"
        print("✅ Ledger Deletion verified.")
        
        # Delete Employee
        t_id_row = emps[emps['name'] == "Temp Emp"]
        if not t_id_row.empty:
            t_id = t_id_row.iloc[0]['id']
            db.delete_employee(t_id)
            
            emps_final = db.get_all_employees()
            assert "Temp Emp" not in emps_final['name'].values, "Employee not deleted"
            print("✅ Employee Delete verified.")
        else:
            print("⚠️ Could not find temp employee ID to delete.")
            
    except Exception as e:
        print(f"❌ Employee/Ledger Test Failed: {e}")

    # 5. Inventory Valuation
    print("\n5. Testing Inventory Valuation...")
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
