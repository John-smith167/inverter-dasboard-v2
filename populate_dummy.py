import sqlite3
import pandas as pd
from database import DatabaseManager

# Setup Test Data for Analytics
db = DatabaseManager('test_bi.db')
db.create_tables()

# Add dummy inventory
db.add_inventory_item("Capacitor 100uF", "Spare", "2023-01-01", 50, 10, 50)
inv = db.get_inventory()
cap_id = int(inv.iloc[0]['id'])

# Add dummy history (Delivered Jobs)
# 1. High Volume, Low Profit (Model A)
for _ in range(5):
    db.add_repair("Client", "Model A", "Issue", "Delivered")
    # Hack: Update costs manually since close_job does stock logic
    db.update_repair_job(
        repair_id=_, service_cost=500, parts_cost=50, total_cost=550, 
        used_parts_str="['Capacitor 100uF']", parts_list=[], new_status="Delivered"
    )

# 2. Low Volume, High Profit (Model B)
for _ in range(2):
    db.add_repair("Client", "Model B", "Issue", "Delivered")
    db.update_repair_job(
        repair_id=_, service_cost=2000, parts_cost=0, total_cost=2000, 
        used_parts_str="", parts_list=[], new_status="Delivered"
    )

print("Dummy data created. Please manually verify charts in Main App.")
print("Running query check...")

df = db.get_job_history()
print("History Rows:", len(df))
print(df[['inverter_model', 'service_cost', 'used_parts']])
