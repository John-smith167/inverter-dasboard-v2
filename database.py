import sqlite3
import pandas as pd
from datetime import datetime

class DatabaseManager:
    def __init__(self, db_name="inverter_business.db"):
        self.db_name = db_name
        self.create_tables()

    def get_connection(self):
        return sqlite3.connect(self.db_name)

    def create_tables(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Employees Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS employees (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    role TEXT NOT NULL,
                    phone TEXT,
                    salary REAL,
                    cnic TEXT
                )
            """)

            # Repairs/Jobs Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS repairs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    client_name TEXT NOT NULL,
                    inverter_model TEXT,
                    issue TEXT,
                    status TEXT DEFAULT 'Pending',
                    phone_number TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    service_cost REAL DEFAULT 0.0,
                    parts_cost REAL DEFAULT 0.0,
                    total_cost REAL DEFAULT 0.0,
                    used_parts TEXT,
                    assigned_to TEXT,
                    start_date DATE,
                    due_date DATE,
                    completion_date DATE,
                    is_late BOOLEAN DEFAULT 0
                )
            """)

            # Migration for existing repairs table
            # Check and add new columns if they don't exist
            # V2.0 Columns
            new_cols = {
                "service_cost": "REAL DEFAULT 0.0",
                "parts_cost": "REAL DEFAULT 0.0",
                "total_cost": "REAL DEFAULT 0.0",
                "used_parts": "TEXT",
                "assigned_to": "TEXT",
                "start_date": "DATE",
                "due_date": "DATE",
                "completion_date": "DATE",
                "is_late": "BOOLEAN DEFAULT 0"
            }
            
            # Get existing columns
            cursor.execute("PRAGMA table_info(repairs)")
            existing_cols = [info[1] for info in cursor.fetchall()]
            
            for col_name, col_type in new_cols.items():
                if col_name not in existing_cols:
                    try:
                        cursor.execute(f"ALTER TABLE repairs ADD COLUMN {col_name} {col_type}")
                    except sqlite3.OperationalError:
                        pass

            # Inventory Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS inventory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    item_name TEXT NOT NULL,
                    category TEXT,
                    import_date DATE,
                    quantity INTEGER DEFAULT 0,
                    cost_price REAL,
                    selling_price REAL
                )
            """)
            
            # Sales Table (for Analytics)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sales (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    item_id INTEGER,
                    item_name TEXT,
                    quantity_sold INTEGER,
                    sale_price REAL,
                    sale_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (item_id) REFERENCES inventory (id)
                )
            """)
            # Migration for Employees (Phone/CNIC)
            cursor.execute("PRAGMA table_info(employees)")
            emp_cols = [info[1] for info in cursor.fetchall()]
            if 'cnic' not in emp_cols:
                try:
                    cursor.execute("ALTER TABLE employees ADD COLUMN cnic TEXT")
                except: pass
            
            # Ledger Table (Financials)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ledger (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    party_name TEXT NOT NULL,
                    date DATE,
                    description TEXT,
                    debit REAL DEFAULT 0.0,
                    credit REAL DEFAULT 0.0
                )
            """)

            conn.commit()

    # --- Employee Methods ---
    def add_employee(self, name, role, phone, salary, cnic):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO employees (name, role, phone, salary, cnic) VALUES (?, ?, ?, ?, ?)",
                           (name, role, phone, salary, cnic))
            conn.commit()

    def get_all_employees(self):
        with self.get_connection() as conn:
            return pd.read_sql("SELECT * FROM employees", conn)
            
    def get_employee_names(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM employees")
            return [row[0] for row in cursor.fetchall()]

    def get_employee_workload(self):
        with self.get_connection() as conn:
            query = """
                SELECT assigned_to, COUNT(*) as active_jobs 
                FROM repairs 
                WHERE status != 'Delivered' AND assigned_to IS NOT NULL
                GROUP BY assigned_to
            """
            return pd.read_sql(query, conn)
    
    def get_employee_performance(self):
        with self.get_connection() as conn:
            query = """
                SELECT 
                    assigned_to, 
                    COUNT(*) as total_completed,
                    SUM(is_late) as total_late
                FROM repairs 
                WHERE status = 'Delivered' AND assigned_to IS NOT NULL
                GROUP BY assigned_to
            """
            df = pd.read_sql(query, conn)
            if not df.empty:
                df['on_time_rate'] = ((df['total_completed'] - df['total_late']) / df['total_completed']) * 100
                df['on_time_rate'] = df['on_time_rate'].round(1)
            return df

    def delete_employee(self, emp_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM employees WHERE id = ?", (emp_id,))
            conn.commit()

    # --- Repair Methods ---
    def add_repair(self, client_name, model, issue, status="Pending", phone="", assigned_to=None, due_date=None):
        start_date = datetime.now().date()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO repairs (client_name, inverter_model, issue, status, phone_number, service_cost, parts_cost, total_cost, used_parts, assigned_to, start_date, due_date, is_late)
                VALUES (?, ?, ?, ?, ?, 0.0, 0.0, 0.0, "", ?, ?, ?, 0)
            """, (client_name, model, issue, status, phone, assigned_to, start_date, due_date))
            conn.commit()

    def get_all_repairs(self):
        with self.get_connection() as conn:
            return pd.read_sql("SELECT * FROM repairs ORDER BY created_at DESC", conn)
    
    def get_job_history(self):
         with self.get_connection() as conn:
            return pd.read_sql("SELECT * FROM repairs WHERE status = 'Delivered' ORDER BY completion_date DESC", conn)
            
    def get_active_repairs(self):
        with self.get_connection() as conn:
            return pd.read_sql("SELECT * FROM repairs WHERE status != 'Delivered' ORDER BY due_date ASC", conn)

    def close_job(self, repair_id, service_cost, parts_cost, total_cost, used_parts_str, parts_list):
        """
        Closes the job: Updates costs, sets status to Delivered, checks lateness, sets completion date.
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Check for late delivery
            is_late = 0
            completion_date = datetime.now().date()
            
            cursor.execute("SELECT due_date FROM repairs WHERE id = ?", (repair_id,))
            res = cursor.fetchone()
            if res and res[0]:
                due_date_str = res[0]
                try:
                    # Handle both YYYY-MM-DD string and potential other formats if sqlite stored oddly
                    # Usually sqlite date is text.
                    due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date()
                    if completion_date > due_date:
                        is_late = 1
                except ValueError:
                    pass

            # 1. Update Repair Record
            cursor.execute("""
                UPDATE repairs 
                SET service_cost = ?, parts_cost = ?, total_cost = ?, used_parts = ?, 
                    status = 'Delivered', is_late = ?, completion_date = ?
                WHERE id = ?
            """, (service_cost, parts_cost, total_cost, used_parts_str, is_late, completion_date, repair_id))
            
            # 1.1 Add to Ledger (Debit the client)
            cursor.execute("SELECT client_name, inverter_model FROM repairs WHERE id = ?", (repair_id,))
            job_details = cursor.fetchone()
            if job_details:
                c_name, c_model = job_details
                desc = f"Repair Job #{repair_id} - {c_model}"
                cursor.execute("INSERT INTO ledger (party_name, date, description, debit, credit) VALUES (?, ?, ?, ?, ?)",
                               (c_name, completion_date, desc, total_cost, 0.0))

            # 2. Deduct Stock
            for part in parts_list:
                item_id = part['id']
                qty = part['qty']
                
                cursor.execute("SELECT quantity FROM inventory WHERE id = ?", (item_id,))
                res = cursor.fetchone()
                if res:
                    new_qty = max(0, res[0] - qty)
                    cursor.execute("UPDATE inventory SET quantity = ? WHERE id = ?", (new_qty, item_id))
            
            conn.commit()
            
    def update_repair_job(self, repair_id, service_cost, parts_cost, total_cost, used_parts_str, parts_list, new_status="Repaired"):
        """
        Legacy/General Update method - reusing close_job logic if status is Delivered could be better, 
        but this method handles intermediate updates too.
        For V2 Technician Zone, we primarily use 'Close Job'. 
        Keeping this for compatibility or partial updates if needed.
        """
        if new_status == "Delivered":
            return self.close_job(repair_id, service_cost, parts_cost, total_cost, used_parts_str, parts_list)
            
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE repairs 
                SET service_cost = ?, parts_cost = ?, total_cost = ?, used_parts = ?, status = ?
                WHERE id = ?
            """, (service_cost, parts_cost, total_cost, used_parts_str, new_status, repair_id))
            
            # Also deduct stock if parts used in intermediate step (assuming immediate deduction)
            for part in parts_list:
                item_id = part['id']
                qty = part['qty']
                cursor.execute("UPDATE inventory SET quantity = quantity - ? WHERE id = ?", (qty, item_id))
            
            conn.commit()

    # --- Inventory Methods ---
    def add_inventory_item(self, name, category, import_date, qty, cost, selling_price):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO inventory (item_name, category, import_date, quantity, cost_price, selling_price)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (name, category, import_date, qty, cost, selling_price))
            conn.commit()

    def get_inventory(self):
        with self.get_connection() as conn:
            return pd.read_sql("SELECT * FROM inventory", conn)

    def sell_item(self, item_id, qty_to_sell=1):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT quantity, item_name, selling_price FROM inventory WHERE id = ?", (item_id,))
            result = cursor.fetchone()
            if not result:
                return False, "Item not found"
            
            current_qty, item_name, selling_price = result
            
            if current_qty < qty_to_sell:
                return False, "Insufficient stock"
            
            cursor.execute("UPDATE inventory SET quantity = quantity - ? WHERE id = ?", (qty_to_sell, item_id))
            
            cursor.execute("""
                INSERT INTO sales (item_id, item_name, quantity_sold, sale_price)
                VALUES (?, ?, ?, ?)
            """, (item_id, item_name, qty_to_sell, selling_price)) 
            
            conn.commit()
            return True, "Item sold successfully"

    # --- Analytics Methods ---
    def get_revenue_analytics(self):
        """
        Calculates Total Revenue and Monthly Revenue based on Delivered jobs.
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            current_month = datetime.now().strftime('%Y-%m')
            
            # Total Revenue (All Delivered Jobs)
            cursor.execute("SELECT SUM(total_cost) FROM repairs WHERE status = 'Delivered'")
            total_rev = cursor.fetchone()[0] or 0.0
            
            # Monthly Revenue
            cursor.execute("SELECT SUM(total_cost) FROM repairs WHERE status = 'Delivered' AND strftime('%Y-%m', completion_date) = ?", (current_month,))
            monthly_rev = cursor.fetchone()[0] or 0.0
            
            return total_rev, monthly_rev

    def get_parts_vs_labor(self):
        """
        Returns the split between Parts Cost and Service Cost for all Delivered jobs.
        """
        with self.get_connection() as conn:
            query = "SELECT SUM(parts_cost) as parts, SUM(service_cost) as service FROM repairs WHERE status = 'Delivered'"
            df = pd.read_sql(query, conn)
            if not df.empty and df.iloc[0]['parts'] is not None:
                return df
            return pd.DataFrame({'parts': [0], 'service': [0]})

    def get_monthly_revenue(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            current_month = datetime.now().strftime('%Y-%m')
            
            query_sales = "SELECT SUM(quantity_sold * sale_price) FROM sales WHERE strftime('%Y-%m', sale_date) = ?"
            cursor.execute(query_sales, (current_month,))
            sales = cursor.fetchone()[0] or 0.0

            # Only count Delivered jobs for revenue in V2
            query_repairs = "SELECT SUM(total_cost) FROM repairs WHERE strftime('%Y-%m', completion_date) = ? AND status = 'Delivered'"
            cursor.execute(query_repairs, (current_month,))
            repairs = cursor.fetchone()[0] or 0.0
            
            return sales + repairs

    # --- Ledger Methods ---
    def add_ledger_entry(self, party_name, description, debit, credit, date_val=None):
        if not date_val:
            date_val = datetime.now().date()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO ledger (party_name, description, debit, credit, date) VALUES (?, ?, ?, ?, ?)",
                           (party_name, description, debit, credit, date_val))
            conn.commit()

    def get_ledger_entries(self, party_name):
        with self.get_connection() as conn:
            # Order by date descending (latest first) or ascending? Accounts usually ascending + balance.
            # Let's do ascending for running balance calculation
            return pd.read_sql("SELECT * FROM ledger WHERE party_name = ? ORDER BY date ASC, id ASC", conn, params=(party_name,))

    def get_all_ledger_parties(self):
        with self.get_connection() as conn:
            # Combine Ledger parties and Repair Clients
            cursor = conn.cursor()
            local_parties = set()
            
            cursor.execute("SELECT DISTINCT party_name FROM ledger")
            for r in cursor.fetchall():
                local_parties.add(r[0])
                
            cursor.execute("SELECT DISTINCT client_name FROM repairs")
            for r in cursor.fetchall():
                local_parties.add(r[0])
                
            return sorted(list(local_parties))
