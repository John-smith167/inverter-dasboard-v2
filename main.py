import streamlit as st
import pandas as pd
import json
import plotly.express as px
from datetime import datetime, date, timedelta
from database import DatabaseManager
from fpdf import FPDF
import base64
import time
import urllib.parse
import qrcode
from io import BytesIO
import os

# Initialize Database
# Check for secrets (support both new connections.gsheets and legacy gsheets)
if "connections" in st.secrets and "gsheets" in st.secrets["connections"]:
    pass # Found in connections
elif "gsheets" in st.secrets:
    pass # Found in top level
else:
    st.error("🚨 Critical Error: Google Sheets Secrets not found in `.streamlit/secrets.toml`. Please configure the connection.")
    st.stop()
    
db = DatabaseManager()

# --- PDF INVOICE GENERATOR ---
def create_invoice_pdf(client_name, device, parts_list, labor_cost, total_cost, is_final=False, labor_data_json="[]", job_id=None):
    pdf = FPDF()
    pdf.add_page()
    
    # --- HEADER (Professional Style) ---
    pdf.set_font("Arial", 'B', 20)
    pdf.set_y(10)
    pdf.cell(0, 8, txt="SK INVERTX TRADERS", ln=True, align='C')
    
    pdf.set_font("Arial", size=10)
    pdf.cell(0, 5, txt="Near SSD Lawn, National Bank, Devri Road, Ghotki", ln=True, align='C')
    pdf.cell(0, 5, txt="Prop: Suresh Kumar | Mobile: 0310-1757750, 0315-1757752", ln=True, align='C')
    
    if os.path.exists("logo.png"):
        pdf.image("logo.png", 10, 8, 30)
    
    pdf.ln(5)
    pdf.set_font("Arial", 'B', 16)
    title = "FINAL REPAIR INVOICE" if is_final else "REPAIR ESTIMATE"
    pdf.cell(0, 8, txt=title, ln=True, align='C')
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(5)
    
    # --- JOB INFO BOX ---
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(20, 6, "Job ID:", 0, 0)
    pdf.set_font("Arial", size=10)
    pdf.cell(40, 6, str(job_id) if job_id else "N/A", 0, 0)
    
    pdf.set_x(140)
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(20, 6, "Date:", 0, 0)
    pdf.set_font("Arial", size=10)
    pdf.cell(30, 6, datetime.now().strftime('%Y-%m-%d'), 0, 1)
    
    # Client Rows
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(20, 6, "Customer:", 0, 0)
    pdf.set_font("Arial", size=10)
    pdf.cell(100, 6, str(client_name), 0, 1)
    
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(20, 6, "Device:", 0, 0)
    pdf.set_font("Arial", size=10)
    pdf.cell(100, 6, str(device), 0, 1)
    
    pdf.ln(5)
    
    # --- TABLE ---
    # Col Widths: # (10), Description (80), Qty (15), Rate (30), Amount (35), Tech (20) -> 190
    pdf.set_fill_color(240, 240, 240)
    pdf.set_font("Arial", 'B', 9)
    
    pdf.cell(10, 8, "#", 1, 0, 'C', 1)
    pdf.cell(80, 8, "Item / Service Description", 1, 0, 'C', 1)
    pdf.cell(15, 8, "Qty", 1, 0, 'C', 1)
    pdf.cell(30, 8, "Rate (Rs.)", 1, 0, 'C', 1)
    pdf.cell(35, 8, "Technician", 1, 0, 'C', 1)
    pdf.cell(20, 8, "Amount", 1, 1, 'C', 1)
    
    pdf.set_font("Arial", size=9)
    
    idx = 1
    
    # 1. Parts Rows
    # Expecting parts_list to be [{name, qty, rate, amount}]
    # Handle legacy case where it might be simple list (fallback)
    
    for part in parts_list:
        # Check structure
        name = part.get('name', 'Part')
        qty = part.get('qty', 1)
        rate = part.get('rate', 0.0)
        # If rate is 0/missing but price (total) exists, infer rate or just show total
        total_p = part.get('amount', part.get('price', 0.0))
        if rate == 0 and qty > 0: rate = total_p / qty
        
        pdf.cell(10, 8, str(idx), 1, 0, 'C')
        pdf.cell(80, 8, str(name)[:45], 1, 0, 'L')
        pdf.cell(15, 8, str(qty), 1, 0, 'C')
        pdf.cell(30, 8, f"{rate:,.0f}", 1, 0, 'R')
        pdf.cell(35, 8, "-", 1, 0, 'C') # No tech for parts usually, or "Store"
        pdf.cell(20, 8, f"{total_p:,.0f}", 1, 1, 'R')
        idx += 1

    # 2. Labor Rows
    labor_detailed = []
    try:
        labor_detailed = json.loads(labor_data_json)
    except:
        pass
        
    if labor_detailed:
         for item in labor_detailed:
             desc = "Service: " + item.get('description', 'Repair')
             cost = float(item.get('cost', 0.0))
             tech = item.get('technician', 'NA')
             
             pdf.cell(10, 8, str(idx), 1, 0, 'C')
             pdf.cell(80, 8, str(desc)[:45], 1, 0, 'L')
             pdf.cell(15, 8, "1", 1, 0, 'C')
             pdf.cell(30, 8, f"{cost:,.0f}", 1, 0, 'R')
             pdf.cell(35, 8, str(tech)[:18], 1, 0, 'C')
             pdf.cell(20, 8, f"{cost:,.0f}", 1, 1, 'R')
             idx += 1
    else:
        # Fallback legacy labor
        if labor_cost > 0:
            pdf.cell(10, 8, str(idx), 1, 0, 'C')
            pdf.cell(80, 8, "Service Labor Charges", 1, 0, 'L')
            pdf.cell(15, 8, "1", 1, 0, 'C')
            pdf.cell(30, 8, f"{labor_cost:,.0f}", 1, 0, 'R')
            pdf.cell(35, 8, "NA", 1, 0, 'C')
            pdf.cell(20, 8, f"{labor_cost:,.0f}", 1, 1, 'R')
            
    pdf.ln(5)
    
    # --- TOTALS ---
    pdf.set_left_margin(120)
    pdf.set_x(120)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(35, 10, "Total Bill:", 0, 0, 'R')
    pdf.cell(35, 10, f"Rs. {total_cost:,.2f}", 1, 1, 'R')
    
    # Reset Margin
    pdf.set_left_margin(10)
    pdf.ln(10)
    
    # Amount In Words
    pdf.set_font("Arial", 'B', 10)
    try:
        # Assuming num_to_words is global or imported
        words = num_to_words(int(total_cost))
        word_str = f"{words} Rupees Only"
    except:
        word_str = "________________________________"
        
    pdf.cell(35, 6, "Amount (In Words):", 0, 0)
    pdf.set_font("Arial", 'I', 10)
    pdf.cell(0, 6, word_str, 0, 1)
    
    pdf.ln(15)
    
    # --- FOOTER / SIGNS ---
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(90, 6, "Technician / Manager", 0, 0, 'L')
    pdf.cell(0, 6, "Customer Signature", 0, 1, 'R')
    pdf.ln(5)
    pdf.cell(90, 6, "_________________", 0, 0, 'L')
    pdf.cell(0, 6, "_________________", 0, 1, 'R')
    
    return pdf.output(dest='S').encode('latin-1')

def create_ledger_pdf(party_name, ledger_df, final_balance):
    # Fetch Customer Details from DB
    customers = db.get_all_customers()
    c_row = None
    if not customers.empty:
        matches = customers[customers['name'] == party_name]
        if not matches.empty:
            c_row = matches.iloc[0]
            
    # Helper for placeholders
    def get_val_or_line(val, line_len=20):
        # Convert to string and strip
        s_val = str(val).strip() if pd.notna(val) else ""
        if s_val.endswith(".0"): s_val = s_val[:-2] # Remove decimal from IDs/Phones
        if s_val.lower() == "nan" or s_val == "":
            return "_" * line_len
        return s_val

    # Safely extract
    c_address = get_val_or_line(c_row.get('address'), 50) if c_row is not None else "_"*50
    c_nic = get_val_or_line(c_row.get('nic'), 20) if c_row is not None else "_"*20
    c_phone = get_val_or_line(c_row.get('phone'), 20) if c_row is not None else "_"*20
    
    pdf = FPDF()
    pdf.add_page()
    
    # --- HEADER SECTION ---
    # Logo
    if os.path.exists("logo.png"): 
        pdf.image("logo.png", 88.5, 8, 33)
    
    pdf.set_y(35) # Ensure title is not covered
    pdf.set_font("Arial", 'B', 20)
    pdf.cell(0, 8, txt="SK INVERTX TRADERS", ln=True, align='C')
    
    pdf.set_font("Arial", size=10)
    pdf.cell(0, 5, txt="Near SSD Lawn, National Bank, Devri Road, Ghotki", ln=True, align='C')
    pdf.cell(0, 5, txt="Prop: Suresh Kumar", ln=True, align='C')
    pdf.cell(0, 5, txt="Mobile: 0310-1757750, 0315-1757752", ln=True, align='C')
    
    pdf.ln(5)
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 8, txt="Sales Invoice / Ledger Statement", ln=True, align='C')
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(5)
    
    # --- CUSTOMER DETAILS SECTION ---
    # Left Side: Customer Info
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(25, 6, "Customer:", 0, 0)
    pdf.set_font("Arial", size=10)
    pdf.cell(100, 6, str(party_name), 'B', 0) # Name with underline
    
    # Right Side: Date
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(15, 6, "Date:", 0, 0)
    pdf.set_font("Arial", size=10)
    pdf.cell(0, 6, datetime.now().strftime('%d-%m-%Y'), 'B', 1)
    
    # Line 2: Address
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(25, 6, "Address:", 0, 0)
    pdf.set_font("Arial", size=10)
    pdf.cell(0, 6, str(c_address), 0, 1)
    
    # Line 3: NIC & Mobile
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(25, 6, "NIC #:", 0, 0)
    pdf.set_font("Arial", size=10)
    pdf.cell(60, 6, str(c_nic), 0, 0)
    
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(20, 6, "Mobile #:", 0, 0)
    pdf.set_font("Arial", size=10)
    pdf.cell(0, 6, str(c_phone), 'B', 1)
    
    pdf.ln(5)
    
    # --- TABLE HEADER ---
    pdf.set_fill_color(240, 240, 240)
    pdf.set_font("Arial", 'B', 9)
    # Adjusted Columns for Discount & Rate
    # S#(8), Date(18), Item(45), Qty(10), Rate(18), Bill(23), Disc(15), Cash(23), Bal(28) => 188mm (Fine for A4)
    
    pdf.cell(8, 8, "S#", 1, 0, 'C', 1)
    pdf.cell(18, 8, "Date", 1, 0, 'C', 1)
    pdf.cell(45, 8, "Item / Description", 1, 0, 'C', 1)
    pdf.cell(10, 8, "Qty", 1, 0, 'C', 1)
    pdf.cell(18, 8, "Rate", 1, 0, 'C', 1)
    pdf.cell(23, 8, "Total Bill", 1, 0, 'C', 1)
    pdf.cell(15, 8, "Discount", 1, 0, 'C', 1)
    pdf.cell(23, 8, "Cash Rec.", 1, 0, 'C', 1)
    pdf.cell(28, 8, "Rem. Balance", 1, 1, 'C', 1)
    
    # --- TABLE ROWS ---
    pdf.set_font("Arial", size=8)
    idx_counter = 1
    for _, row in ledger_df.iterrows():
        # Handle date object
        d_str = str(row['date'])
        
        pdf.cell(8, 6, str(idx_counter), 1, 0, 'C')
        pdf.cell(18, 6, d_str, 1, 0, 'C')
        
        # Truncate Desc
        desc_text = str(row['description'])
        if len(desc_text) > 25: desc_text = desc_text[:23] + ".."
        pdf.cell(45, 6, desc_text, 1, 0, 'L')
        
        # Quantity
        qty_val = row.get('quantity', 0)
        qty_str = str(int(qty_val)) if pd.notna(qty_val) and qty_val != 0 else "-"
        pdf.cell(10, 6, qty_str, 1, 0, 'C')

        # Rate
        rate_val = row.get('rate', 0.0)
        rate_str = f"{rate_val:,.0f}" if pd.notna(rate_val) and rate_val != 0 else "-"
        pdf.cell(18, 6, rate_str, 1, 0, 'R')
        
        # Numbers
        debit_val = row['debit']
        discount_val = row.get('discount', 0.0)
        credit_val = row['credit']
        bal_val = row['Balance'] 
        
        pdf.cell(23, 6, f"{debit_val:,.0f}" if debit_val!=0 else "-", 1, 0, 'R')
        pdf.cell(15, 6, f"{discount_val:,.0f}" if discount_val!=0 else "-", 1, 0, 'R')
        pdf.cell(23, 6, f"{credit_val:,.0f}" if credit_val!=0 else "-", 1, 0, 'R')
        pdf.cell(28, 6, f"{bal_val:,.0f}", 1, 1, 'R')
        
        idx_counter += 1
        
    pdf.ln(2)
    
    # --- TOTALS BOX ---
    # Bottom Right
    pdf.set_x(100) # Move to right half
    pdf.set_font("Arial", 'B', 10)
    
    # Calculate totals
    total_debit = ledger_df['debit'].sum()
    total_credit = ledger_df['credit'].sum()
    
    pdf.cell(50, 6, "Total Bill Amount:", 0, 0, 'R')
    pdf.cell(40, 6, f"{total_debit:,.0f}", 0, 1, 'R')
    
    pdf.set_x(100)
    pdf.cell(50, 6, "Total Received:", 0, 0, 'R')
    pdf.cell(40, 6, f"{total_credit:,.0f}", 0, 1, 'R')
    
    pdf.line(110, pdf.get_y()+1, 200, pdf.get_y()+1)
    pdf.ln(2)
    
    pdf.set_x(100)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(50, 8, "Net Balance:", 0, 0, 'R')
    pdf.cell(40, 8, f"{final_balance:,.0f}", 1, 1, 'R', fill=True) 
    
    pdf.ln(15)
    
    # Signatures (Relative positioning to avoid Page 2 drift)
    # Check Y position, if too low, add page
    if pdf.get_y() > 250:
        pdf.add_page()
        
    pdf.set_font("Arial", 'B', 9)
    pdf.cell(90, 10, "Prepared By: _________________", 0, 0, 'L')
    pdf.cell(0, 10, "Receiver Signature: _________________", 0, 1, 'R')
    
    return pdf.output(dest='S').encode('latin-1')

def create_employee_payroll_pdf(employee_name, ledger_df, final_balance):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    
    # Header
    pdf.set_font("Arial", 'B', 16)
    if os.path.exists("logo.png"):
        pdf.image("logo.png", 88.5, 8, 33)
        pdf.set_y(35)

    pdf.cell(0, 8, txt="SK INVERTX TRADERS", ln=True, align='C')
    
    pdf.set_font("Arial", size=10)
    pdf.cell(0, 5, txt="Near SSD Lawn, National Bank, Devri Road, Ghotki", ln=True, align='C')
    pdf.cell(0, 5, txt="Prop: Suresh Kumar | Mobile: 0310-1757750, 0315-1757752", ln=True, align='C')
    
    pdf.ln(5)
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 8, txt="EMPLOYEE PAYROLL STATEMENT", ln=True, align='C')
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    
    # Fetch Employee Details
    employees = db.get_all_employees()
    e_row = None
    if not employees.empty:
        matches = employees[employees['name'] == employee_name]
        if not matches.empty:
            e_row = matches.iloc[0]

    # Helper
    def get_val_or_line(val, line_len=20):
        s_val = str(val).strip() if pd.notna(val) else ""
        if s_val.lower() == "nan" or s_val == "":
            return "_" * line_len
        return s_val

    e_phone = get_val_or_line(e_row.get('phone'), 20) if e_row is not None else "_"*20
    e_cnic = get_val_or_line(e_row.get('cnic'), 25) if e_row is not None else "_"*25
    
    # Employee Info Section
    pdf.ln(5)
    pdf.set_font("Arial", 'B', 10)
    
    # Line 1: Name & Date
    pdf.cell(20, 6, "Employee:", 0, 0)
    pdf.set_font("Arial", size=10)
    pdf.cell(105, 6, str(employee_name), 'B', 0)
    
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(15, 6, "Date:", 0, 0)
    pdf.set_font("Arial", size=10)
    pdf.cell(0, 6, datetime.now().strftime('%d-%m-%Y'), 'B', 1)
    
    # Line 2: Phone & CNIC
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(20, 6, "Phone #:", 0, 0)
    pdf.set_font("Arial", size=10)
    pdf.cell(105, 6, str(e_phone), 'B', 0)
    
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(15, 6, "CNIC:", 0, 0)
    pdf.set_font("Arial", size=10)
    pdf.cell(0, 6, str(e_cnic), 'B', 1)
    
    pdf.ln(5)
    
    # Table Header
    pdf.set_fill_color(220, 220, 220)
    pdf.set_font("Arial", 'B', 9)
    pdf.cell(25, 10, "Date", 1, 0, 'C', 1)
    pdf.cell(30, 10, "Type", 1, 0, 'C', 1)
    pdf.cell(65, 10, "Description", 1, 0, 'C', 1)
    pdf.cell(25, 10, "Earned", 1, 0, 'C', 1)
    pdf.cell(25, 10, "Paid", 1, 0, 'C', 1)
    pdf.cell(25, 10, "Balance", 1, 1, 'C', 1)
    
    # Rows
    pdf.set_font("Arial", size=8)
    running_balance = 0.0
    for _, row in ledger_df.iterrows():
        d_str = str(row['date'])
        running_balance += (row['earned'] - row['paid'])
        
        pdf.cell(25, 10, d_str, 1)
        pdf.cell(30, 10, str(row['type'])[:15], 1)
        pdf.cell(65, 10, str(row['description'])[:35], 1)
        pdf.cell(25, 10, f"{row['earned']:,.0f}", 1, 0, 'R')
        pdf.cell(25, 10, f"{row['paid']:,.0f}", 1, 0, 'R')
        pdf.cell(25, 10, f"{running_balance:,.0f}", 1, 1, 'R')
        
    pdf.ln(5)
    pdf.set_font("Arial", 'B', 12)
    
    # Balance Display
    if final_balance > 0:
        balance_label = "Payable Salary:"
    elif final_balance < 0:
        balance_label = "Outstanding Advance:"
    else:
        balance_label = "Net Balance:"
    
    pdf.cell(140, 10, balance_label, 0, 0, 'R')
    pdf.cell(55, 10, f"Rs. {abs(final_balance):,.2f}", 1, 1, 'C')
    
    pdf.ln(10)
    
    # Remarks Section
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(20, 6, "Remarks:", 0, 1)
    pdf.line(10, pdf.get_y()+6, 200, pdf.get_y()+6) # Underline for remarks
    pdf.ln(8)
    
    # Signatures
    pdf.ln(10)
    pdf.cell(90, 6, "Employee Signature", 0, 0, 'L')
    pdf.cell(0, 6, "Approved By", 0, 1, 'R')
    pdf.ln(8)
    pdf.cell(90, 6, "_________________", 0, 0, 'L')
    pdf.cell(0, 6, "_________________", 0, 1, 'R')
    
    return pdf.output(dest='S').encode('latin-1')


def num_to_words(n):
    try:
        n = int(n)
        if n < 0: return "Minus " + num_to_words(-n)
        if n == 0: return ""
        
        units = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine"]
        teens = ["", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen", "Seventeen", "Eighteen", "Nineteen"]
        tens = ["", "Ten", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]
        
        if n < 10: return units[n]
        if n < 20: return teens[n-10] if n > 10 else tens[1]
        if n < 100: return tens[n // 10] + (" " + units[n % 10] if n % 10 != 0 else "")
        if n < 1000: return units[n // 100] + " Hundred" + (" " + num_to_words(n % 100) if n % 100 != 0 else "")
        if n < 100000: return num_to_words(n // 1000) + " Thousand" + (" " + num_to_words(n % 1000) if n % 1000 != 0 else "")
        if n < 10000000: return num_to_words(n // 100000) + " Lakh" + (" " + num_to_words(n % 100000) if n % 100000 != 0 else "")
        return num_to_words(n // 10000000) + " Crore" + (" " + num_to_words(n % 10000000) if n % 10000000 != 0 else "")
    except:
        return ""

def create_sales_invoice_pdf(invoice_no, customer, date_val, items_df, subtotal, freight, misc, grand_total, previous_balance, outstanding_balance, cash_received=0.0):
    pdf = FPDF()
    pdf.add_page()
    
    # Determine if this is a Payment Receipt (Cash only, no billable items)
    is_receipt = (grand_total == 0 and cash_received > 0)
    
    # --- HEADER ---
    pdf.set_font("Arial", 'B', 20)
    pdf.set_y(10)
    pdf.cell(0, 8, txt="SK INVERTX TRADERS", ln=True, align='C')
    
    pdf.set_font("Arial", size=10)
    pdf.cell(0, 5, txt="Near SSD Lawn, National Bank, Devri Road, Ghotki", ln=True, align='C')
    pdf.cell(0, 5, txt="Prop: Suresh Kumar | Mobile: 0310-1757750, 0315-1757752", ln=True, align='C')
    
    if os.path.exists("logo.png"):
        pdf.image("logo.png", 10, 8, 30)

    pdf.ln(5)
    pdf.set_font("Arial", 'B', 16)
    
    title_text = "Payment Receipt" if is_receipt else "Sales Invoice"
    pdf.cell(0, 8, txt=title_text, ln=True, align='C')
    
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(5)

    # --- INVOICE & CUSTOMER DETAILS ---
    
    # Invoice No & Date
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(20, 6, "Ref #:" if is_receipt else "Invoice #:", 0, 0)
    pdf.set_font("Arial", size=10)
    pdf.cell(40, 6, str(invoice_no), 0, 0)
    
    pdf.set_x(140)
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(20, 6, "Date :", 0, 0)
    pdf.set_font("Arial", size=10)
    pdf.cell(30, 6, str(date_val), 0, 1)
    
    pdf.line(10, pdf.get_y()+1, 200, pdf.get_y()+1)
    pdf.ln(3)

    # Customer Details
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(20, 6, "Customer:", 0, 0)
    pdf.set_font("Arial", size=10)
    pdf.cell(100, 6, str(customer), 0, 1)
    
    pdf.ln(5)

    # --- TABLE HEADER ---
    if not is_receipt:
        pdf.set_fill_color(240, 240, 240)
        pdf.set_font("Arial", 'B', 10)
        
        pdf.cell(10, 8, "S#", 1, 0, 'C', 1)
        pdf.cell(80, 8, "Item Description", 1, 0, 'C', 1)
        pdf.cell(15, 8, "Qty", 1, 0, 'C', 1)
        pdf.cell(25, 8, "Rate", 1, 0, 'C', 1)
        pdf.cell(20, 8, "Discount", 1, 0, 'C', 1)
        pdf.cell(40, 8, "Net Amount", 1, 1, 'C', 1)

        # --- TABLE ROWS ---
        pdf.set_font("Arial", size=9)
        idx = 1
        for _, row in items_df.iterrows():
            item_name = str(row['Item Name'])[:45]
            qty = float(row['Qty'])
            ret = float(row.get('Return Qty', 0))
            net_qty = qty - ret
            rate = float(row['Rate'])
            discount = float(row.get('Discount', 0))
            total = float(row['Total'])
            
            pdf.cell(10, 8, str(idx), 1, 0, 'C')
            pdf.cell(80, 8, item_name, 1, 0, 'L')
            pdf.cell(15, 8, f"{net_qty:g}", 1, 0, 'C')
            pdf.cell(25, 8, f"{rate:g}", 1, 0, 'R')
            pdf.cell(20, 8, f"{discount:g}", 1, 0, 'R')
            pdf.cell(40, 8, f"{total:,.2f}", 1, 1, 'R')
            idx += 1
            
        pdf.ln(2)
    else:
        # Receipt View - Just show the main description
        pdf.set_fill_color(245, 245, 245)
        pdf.set_font("Arial", size=12)
        pdf.multi_cell(0, 10, f"Received payment from {customer}.", border=1, align='C', fill=True)
        pdf.ln(5)

    # --- SUMMARY SECTION ---
    y_before_totals = pdf.get_y()
    
    # Right Side Totals
    pdf.set_left_margin(110)
    pdf.set_x(110)
    pdf.set_font("Arial", 'B', 10)
    
    if not is_receipt:
        pdf.cell(45, 7, "Total:", 0, 0, 'R')
        pdf.cell(35, 7, f"{subtotal:,.2f}", 1, 1, 'R')
        
        if freight > 0 or misc > 0:
            extras = freight + misc
            pdf.cell(45, 7, "Freight/Labor:", 0, 0, 'R')
            pdf.cell(35, 7, f"{extras:,.2f}", 1, 1, 'R')

        pdf.cell(45, 7, "Bill Total:", 0, 0, 'R')
        pdf.cell(35, 7, f"{grand_total:,.2f}", 1, 1, 'R')

    if cash_received > 0:
        pdf.set_fill_color(230, 255, 230)
        pdf.cell(45, 7, "Cash Received:", 0, 0, 'R', is_receipt)
        pdf.cell(35, 7, f"{cash_received:,.2f}", 1, 1, 'R', is_receipt)
    
    if not is_receipt:
        current_bill_bal = grand_total - cash_received
        pdf.cell(45, 7, "Bill Balance:", 0, 0, 'R')
        pdf.cell(35, 7, f"{current_bill_bal:,.2f}", 1, 1, 'R')
    
    pdf.cell(45, 7, "Previous Balance:", 0, 0, 'R')
    pdf.cell(35, 7, f"{previous_balance:,.2f}", 1, 1, 'R')
    
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(45, 8, "Outstanding Balance:", 0, 0, 'R')
    pdf.cell(35, 8, f"{outstanding_balance:,.2f}", 1, 1, 'R')
    
    y_after_totals = pdf.get_y()
    
    # --- FOOTER CONTENT (Left Side) ---
    pdf.set_left_margin(10)
    pdf.set_y(y_before_totals)
    
    if not is_receipt:
        pdf.set_font("Arial", 'B', 10)
        pdf.cell(20, 6, "Remarks:", 0, 1)
        pdf.set_font("Arial", size=9)
        pdf.multi_cell(90, 5, "Warranty claims as per company policy. No return/change without invoice.", border=1)
    else:
        pdf.set_font("Arial", 'I', 9)
        pdf.cell(90, 6, "Thank you for your payment.", 0, 1)
    
    pdf.set_y(max(y_after_totals, pdf.get_y()) + 5)
    
    # Amount In Words helps validation
    amount_to_word = cash_received if is_receipt else grand_total
    
    pdf.set_font("Arial", 'B', 10)
    try:
        words = num_to_words(int(amount_to_word))
        word_str = f"{words} Rupees Only"
    except:
        word_str = "________________________________"
        
    pdf.cell(35, 6, "Amount (In Words):", 0, 0)
    pdf.set_font("Arial", 'I', 10)
    pdf.cell(0, 6, word_str, 0, 1)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    
    pdf.ln(15)
    
    # Signatures
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(90, 6, "Prepared By", 0, 0, 'L')
    pdf.cell(0, 6, "Receiver Signature", 0, 1, 'R')
    pdf.ln(5)
    pdf.cell(90, 6, "_________________", 0, 0, 'L')
    pdf.cell(0, 6, "_________________", 0, 1, 'R')

    return pdf.output(dest='S').encode('latin-1')

def create_stock_valuation_pdf(stock_df):
    pdf = FPDF(orientation='L', unit='mm', format='A4')
    pdf.add_page()
    pdf.set_font("Arial", size=12)

    # Header
    pdf.set_font("Arial", 'B', 20)
    # Logo placement for Landscape (Width ~297mm)
    if os.path.exists("logo.png"):
        pdf.image("logo.png", 10, 8, 33)
        
    pdf.set_y(10)
    pdf.cell(0, 8, txt="SK INVERTX TRADERS", ln=True, align='C')
    
    pdf.set_font("Arial", size=10)
    pdf.cell(0, 5, txt="Near SSD Lawn, National Bank, Devri Road, Ghotki", ln=True, align='C')
    pdf.cell(0, 5, txt="Prop: Suresh Kumar | Mobile: 0310-1757750, 0315-1757752", ln=True, align='C')
    
    pdf.ln(5)
    
    pdf.set_font("Arial", size=12)
    # Title
    pdf.cell(0, 8, txt="Detailed Stock Valuation Report", ln=True, align='C')
    pdf.line(10, pdf.get_y(), 287, pdf.get_y()) # Line across page (A4 Land = 297mm, margin 10)
    
    pdf.ln(5)
    pdf.set_font("Arial", size=10)
    pdf.cell(0, 6, txt=f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", ln=True, align='C')
    pdf.ln(5)

    # Table Config
    pdf.set_fill_color(220, 220, 220)
    pdf.set_font("Arial", 'B', 10)
    
    pdf.cell(10, 10, "#", 1, 0, 'C', 1)
    pdf.cell(60, 10, "Item Name", 1, 0, 'C', 1)
    pdf.cell(35, 10, "Category", 1, 0, 'C', 1)
    pdf.cell(20, 10, "Qty", 1, 0, 'C', 1)
    pdf.cell(30, 10, "Cost Price", 1, 0, 'C', 1)
    pdf.cell(30, 10, "Sell Price", 1, 0, 'C', 1)
    pdf.cell(35, 10, "Total Cost", 1, 0, 'C', 1)
    pdf.cell(35, 10, "Total Sales", 1, 1, 'C', 1)
    
    # Rows
    pdf.set_font("Arial", size=9)
    idx = 1
    for _, row in stock_df.iterrows():
        item = str(row['item_name'])[:35]
        cat = str(row['category'])[:20]
        
        pdf.cell(10, 8, str(idx), 1, 0, 'C')
        pdf.cell(60, 8, item, 1, 0, 'L')
        pdf.cell(35, 8, cat, 1, 0, 'L')
        pdf.cell(20, 8, str(row['quantity']), 1, 0, 'C')
        pdf.cell(30, 8, f"{row['cost_price']:,.2f}", 1, 0, 'R')
        pdf.cell(30, 8, f"{row['selling_price']:,.2f}", 1, 0, 'R')
        pdf.cell(35, 8, f"{row['Total Cost']:,.2f}", 1, 0, 'R')
        pdf.cell(35, 8, f"{row['Total Selling']:,.2f}", 1, 1, 'R')
        idx += 1
        
    pdf.ln(5)
    
    # Summary Box
    g_total_cost = stock_df['Total Cost'].sum()
    g_total_sell = stock_df['Total Selling'].sum()
    
    pdf.set_font("Arial", 'B', 11)
    pdf.cell(185, 10, "Grand Totals:", 0, 0, 'R')
    pdf.set_fill_color(255, 230, 230)
    pdf.cell(35, 10, f"{g_total_cost:,.2f}", 1, 0, 'R', 1)
    pdf.set_fill_color(230, 255, 230)
    pdf.cell(35, 10, f"{g_total_sell:,.2f}", 1, 1, 'R', 1)
    
    return pdf.output(dest='S').encode('latin-1')

def create_recovery_list_pdf(recovery_df, grand_total):
    pdf = FPDF(orientation='L', unit='mm', format='A4')
    pdf.add_page()
    pdf.set_font("Arial", size=12)

    # Header
    pdf.set_font("Arial", 'B', 16)
    if os.path.exists("logo.png"):
        pdf.image("logo.png", 10, 8, 33)
        
    pdf.set_y(15)
    pdf.cell(0, 10, txt="SK INVERTX TRADERS", ln=True, align='C')
    pdf.set_font("Arial", size=12)
    pdf.cell(0, 8, txt="Customer Recovery List", ln=True, align='C')
    pdf.set_font("Arial", size=10)
    pdf.cell(0, 6, txt=f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", ln=True, align='C')
    pdf.ln(10)
    
    # Identify Dynamic Columns
    cat_cols = [c for c in recovery_df.columns if c.endswith('_count') and c != 'other_count']
    if 'other_count' in recovery_df.columns:
        cat_cols.append('other_count')
        
    # Table Config
    pdf.set_fill_color(220, 220, 220)
    pdf.set_font("Arial", 'B', 9)
    
    # Static Widths
    # Total Page Width ~280mm (A4 Landscape minus margins)
    # Name(50) + City(25) + Phone(28) + Sales(22) + Paid(22) + Open(20) + Net(25) = 192mm
    # Remaining: ~88mm for Categories
    
    # Headers
    pdf.cell(50, 10, "Customer Name", 1, 0, 'C', 1)
    pdf.cell(25, 10, "City", 1, 0, 'C', 1)
    pdf.cell(28, 10, "Phone", 1, 0, 'C', 1)
    
    # Dynamic Headers
    cat_width = 12
    # Adjust width if too many cols
    if len(cat_cols) > 0:
        total_cat_width = 88
        cat_width = max(8, total_cat_width / len(cat_cols))
        
    for c in cat_cols:
        label = c.replace('_count', '')[:3].title() # Truncate to 3 chars
        pdf.cell(cat_width, 10, label, 1, 0, 'C', 1)
        
    pdf.cell(22, 10, "Sales", 1, 0, 'C', 1)
    pdf.cell(22, 10, "Paid", 1, 0, 'C', 1)
    pdf.cell(20, 10, "Op. Bal", 1, 0, 'C', 1)
    pdf.cell(25, 10, "Net Due", 1, 1, 'C', 1)
    
    # Rows
    pdf.set_font("Arial", size=8)
    for _, row in recovery_df.iterrows():
        # Sanitize Name
        raw_name = str(row['name'])
        clean_name = raw_name.replace("❌", " (Del)")
        # Ensure compatible with FPDF (Latin-1)
        try:
            name = clean_name.encode('latin-1', 'replace').decode('latin-1')[:28]
            city = str(row['city']).encode('latin-1', 'replace').decode('latin-1')[:15]
        except:
             name = clean_name[:28]
             city = str(row['city'])[:15]
        
        phone = str(row['phone'])
        
        pdf.cell(50, 8, name, 1)
        pdf.cell(25, 8, city, 1)
        pdf.cell(28, 8, phone, 1)
        
        # Dynamic Counts
        for c in cat_cols:
            val = row.get(c, 0)
            pdf.cell(cat_width, 8, str(int(val)), 1, 0, 'C')
            
        pdf.cell(22, 8, f"{row['total_sales']:,.0f}", 1, 0, 'R')
        pdf.cell(22, 8, f"{row['total_paid']:,.0f}", 1, 0, 'R')
        pdf.cell(20, 8, f"{row['opening_balance']:,.0f}", 1, 0, 'R')
        pdf.cell(25, 8, f"{row['net_outstanding']:,.0f}", 1, 1, 'R')

    pdf.ln(5)
    
    # Summary
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(200, 10, "Overall Total Outstanding:", 0, 0, 'R')
    pdf.set_fill_color(200, 220, 255)
    pdf.cell(42, 10, f"Rs. {grand_total:,.2f}", 1, 1, 'R', 1)
    
    # Safe Encode for Output
    try:
        return pdf.output(dest='S').encode('latin-1', 'replace')
    except Exception as e:
        return pdf.output(dest='S').encode('latin-1', 'ignore')

def render_stock_valuation_table(db_instance):
    st.header("📦 Detailed Stock Valuation")
    stock_inv = db_instance.get_inventory()
    if not stock_inv.empty:
        # Prepare Data
        stock_inv['Total Cost'] = stock_inv['quantity'] * stock_inv['cost_price']
        stock_inv['Total Selling'] = stock_inv['quantity'] * stock_inv['selling_price']
        
        # Display
        st.dataframe(
            stock_inv[['id', 'item_name', 'category', 'quantity', 'cost_price', 'selling_price', 'Total Cost', 'Total Selling']],
            use_container_width=True,
            column_config={
                "cost_price": st.column_config.NumberColumn("Cost Price", format="Rs. %.2f"),
                "selling_price": st.column_config.NumberColumn("Selling Price", format="Rs. %.2f"),
                "Total Cost": st.column_config.NumberColumn("Total Cost Value", format="Rs. %.2f"),
                "Total Selling": st.column_config.NumberColumn("Total Sales Value", format="Rs. %.2f"),
            }
        )
        
        # Totals
        g_total_cost = stock_inv['Total Cost'].sum()
        g_total_sell = stock_inv['Total Selling'].sum()
        
        st.markdown(f"""<div style="display:flex; gap:20px; justify-content:flex-end; margin-top:10px;"><div style="text-align:right; padding:10px; background:#1a1c24; border-radius:10px; border:1px solid #f7768e;"><span style="color:#a9b1d6; font-size:0.9rem;">Total Stock Cost</span><br><span style="color:#f7768e; font-size:1.5rem; font-weight:bold;">Rs. {g_total_cost:,.2f}</span></div><div style="text-align:right; padding:10px; background:#1a1c24; border-radius:10px; border:1px solid #9ece6a;"><span style="color:#a9b1d6; font-size:0.9rem;">Total Sales Potential</span><br><span style="color:#9ece6a; font-size:1.5rem; font-weight:bold;">Rs. {g_total_sell:,.2f}</span></div></div>""", unsafe_allow_html=True)
        
        # Download Button
        # Download Button
        pdf_bytes = create_stock_valuation_pdf(stock_inv)
        st.download_button(
            "📥 Download Stock Report (PDF)",
            data=pdf_bytes,
            file_name=f"Stock_Report_{datetime.now().strftime('%Y-%m-%d')}.pdf",
            mime="application/pdf",
            type="primary"
        )
        
    else:
        st.info("No stock data available.")
    
    st.divider()


# Page Config
st.set_page_config(page_title="SK INVERTX TRADERS", layout="wide", page_icon="⚡", initial_sidebar_state="expanded")

# --- INTERACTIVE DIALOGS ---
@st.dialog("Repair Job Manager")
def repair_dialog(job_id, client_name, issue, model, current_parts, current_labor, phone_number, total_bill_val=0.0, parts_data_json="[]", labor_data_json="[]", assigned_tech="Unassigned"):
    st.caption(f"Job #{job_id} • {model}")
    
    # Parse Saved Data
    saved_parts = []
    try:
        saved_parts = json.loads(parts_data_json)
    except:
        saved_parts = []
        
    # Helpers to extract saved values
    saved_stock_ids = [p['id'] for p in saved_parts if p.get('type') == 'stock']
    saved_custom = [p for p in saved_parts if p.get('type') == 'custom']
    
    # Initialize session state for quantities if not present (only on first load of this dialog instance?)
    # Streamlit dialog re-runs from scratch, so we need to rely on st.session_state persistence or default values.
    # We will use st.session_state injection if keys don't exist.
    
    for p in saved_parts:
        if p.get('type') == 'stock':
            k_qty = f"qty_{job_id}_{p['id']}"
            if k_qty not in st.session_state:
                st.session_state[k_qty] = p['qty']
    
    # 1. Top: Client Info
    with st.container(border=True):
        st.markdown("### 👤 Client Details")
        cd1, cd2 = st.columns(2)
        with cd1:
            st.markdown(f"**Name:** {client_name}")
            st.markdown(f"**Contact:** {phone_number}")
        with cd2:
            st.markdown(f"**Device:** {model}")
            st.caption(f"**Issue:** {issue}")

    # 2. Middle: Technician Zone (Parts & Labor)
    st.markdown("#### 🔧 Technician Zone")
    
    # Parts Selection
    inventory = db.get_inventory()
    parts_cost = 0.0
    selected_parts_db = []     # For Stock Deduction (Only ID'd items)
    all_billable_parts = []    # For Invoice (Legacy - Strings)
    parts_list_for_pdf = []    # For Invoice (Detailed)
    
    # Prepare Data for Saving
    current_parts_data = []
    
    if not inventory.empty:
        # Create mapping for multiselect
        inv_map = { r['id']: f"{r['item_name']} - Rs. {r['selling_price']} (Stock: {r['quantity']})" for i, r in inventory.iterrows() }
        
        # Pre-select based on saved IDs
        # We need to intersect with available IDs to avoid errors
        default_sel = [sid for sid in saved_stock_ids if sid in inv_map]
        
        sel_keys = st.multiselect("Add Stock Parts", options=list(inv_map.keys()), default=default_sel, format_func=lambda x: inv_map[x], key=f"diag_parts_{job_id}")
        
        if sel_keys:
            st.caption("Parts Bill:")
            for k in sel_keys:
                item = inventory[inventory['id'] == k].iloc[0]
                
                # Quantity Input for each selected part
                c_p_name, c_p_qty = st.columns([3, 1])
                c_p_name.markdown(f"- {item['item_name']} (@ Rs. {item['selling_price']})")
                p_qty = c_p_qty.number_input("Qty", min_value=1, value=1, step=1, key=f"qty_{job_id}_{k}", label_visibility="collapsed")
                
                line_total = item['selling_price'] * p_qty
                parts_cost += line_total
                
                # Add to lists
                selected_parts_db.append({'id': k, 'qty': p_qty})
                # Add selling_price to saved data to persist 'current' price if needed in future, though not strictly schema required
                current_parts_data.append({'id': k, 'qty': p_qty, 'type': 'stock', 'name': item['item_name'], 'price': item['selling_price']})
                parts_list_for_pdf.append({'name': item['item_name'], 'qty': p_qty, 'rate': item['selling_price'], 'amount': line_total})
                
                # Show qty in name if > 1
                disp_name = f"{item['item_name']} (x{p_qty})" if p_qty > 1 else item['item_name']
                all_billable_parts.append({'name': disp_name, 'price': line_total})
    
    
    # Custom / Out-of-Stock Item (Always Visible)
    st.markdown("---")
    st.markdown("**➕ Add Custom / Market Item**")
    
    # Restore Custom Item State if available (Single Item Logic)
    def_c_name = ""
    def_c_price = 0.0
    def_c_qty = 1
    
    if saved_custom:
        # Load the first custom item found
        sc = saved_custom[0]
        def_c_name = sc.get('name', '')
        def_c_price = sc.get('unit_price', 0.0)
        def_c_qty = sc.get('qty', 1)
        
    # We use key+job_id to persist in session, but we also want defaults.
    
    col_custom1, col_custom2, col_custom3 = st.columns([2, 1, 1])
    with col_custom1:
        c_name = st.text_input("Item Name", value=def_c_name, key=f"cust_name_{job_id}", placeholder="e.g., Battery, Capacitor")
    with col_custom2:
        c_price = st.number_input("Price (Rs.)", min_value=0.0, value=float(def_c_price), step=100.0, key=f"cust_price_{job_id}")
    with col_custom3:
        c_qty = st.number_input("Qty", min_value=1, value=int(def_c_qty), step=1, key=f"cust_qty_{job_id}")
    
    if c_name and c_price > 0:
        c_total = c_price * c_qty
        parts_cost += c_total
        disp_c_name = f"{c_name} (Custom) (x{c_qty})" if c_qty > 1 else f"{c_name} (Custom)"
        all_billable_parts.append({'name': disp_c_name, 'price': c_total})
        parts_list_for_pdf.append({'name': c_name, 'qty': c_qty, 'rate': c_price, 'amount': c_total})
        
        current_parts_data.append({'id': None, 'qty': c_qty, 'type': 'custom', 'name': c_name, 'unit_price': c_price})
        
        st.success(f"✅ Added: {disp_c_name} - Rs. {c_total:,.2f}")


    # Labor & Services
    st.markdown("---")
    st.markdown("**🔧 Labor & Services**")
    
    # Init Labor Data
    labor_list = []
    try:
        labor_list = json.loads(labor_data_json)
    except:
        pass
        
    if not labor_list and current_labor and float(current_labor) > 0:
        # Migration for legacy single labor value
        labor_list = [{"description": "Repair Service", "qty": 1, "rate": float(current_labor), "cost": float(current_labor), "technician": assigned_tech}]
        
    labor_df = pd.DataFrame(labor_list)
    
    # Ensure correct columns for new schema
    required_cols = ["description", "qty", "rate"] # 'cost' and 'technician' are derived/hidden
    
    # Normalize existing data
    if not labor_df.empty:
        if "rate" not in labor_df.columns and "cost" in labor_df.columns:
             # Legacy migration: assume rate = cost if qty missing or 1
             labor_df["rate"] = labor_df["cost"]
        if "qty" not in labor_df.columns:
             labor_df["qty"] = 1
             
    for col in required_cols:
        if col not in labor_df.columns:
             if col == "qty": labor_df[col] = 1
             elif col == "rate": labor_df[col] = 0.0
             else: labor_df[col] = ""
             
    # Filter for display
    display_df = labor_df[["description", "qty", "rate"]]
            
    # Editor
    updated_labor_display = st.data_editor(
        display_df,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "description": st.column_config.TextColumn("Description / Device", required=True, width="large"),
            "qty": st.column_config.NumberColumn("Quantity", min_value=1, step=1, width="small"),
            "rate": st.column_config.NumberColumn("Rate (Rs.)", min_value=0, step=100, width="small"),
        },
        key=f"labor_grid_{job_id}"
    )
    
    # Calculate Total Labor & Reconstruct Full JSON
    labor = 0.0
    final_labor_records = []
    
    if not updated_labor_display.empty:
        for index, row in updated_labor_display.iterrows():
            q = int(row.get('qty', 1))
            r = float(row.get('rate', 0.0))
            line_total = q * r
            labor += line_total
            
            # Create record with all hidden fields needed for backend
            final_labor_records.append({
                "description": row.get('description'),
                "qty": q,
                "rate": r,
                "cost": line_total, # Backend expects 'cost' as total for ledger crediting
                "technician": assigned_tech # Auto-assign current job's tech
            })
        
    final_labor_json = json.dumps(final_labor_records)

    # Live Total
    total = parts_cost + labor
    st.markdown(f"### 💰 Estimated Total: Rs. {total:,.2f}")
    
    st.divider()
    
    # serialized data
    final_parts_json = json.dumps(current_parts_data)
    final_parts_str = str([p['name'] for p in all_billable_parts]) # For display only
    
    # 3. Bottom: Actions
    col_save, col_print, col_close = st.columns(3)
    
    with col_save:
        if st.button("💾 Save Progress", use_container_width=True):
            db.update_repair_job(job_id, labor, parts_cost, total, final_parts_str, selected_parts_db, new_status="In Progress", parts_data_json=final_parts_json, labor_data_json=final_labor_json)
            st.toast("Progress Saved!")
            st.rerun()

    with col_print:
        if st.button("🖨️ Print Invoice", use_container_width=True):
             # 1. AUTO-SAVE State
             db.update_repair_job(job_id, labor, parts_cost, total, final_parts_str, selected_parts_db, new_status="In Progress", parts_data_json=final_parts_json, labor_data_json=final_labor_json)
             
             # 2. Generate PDF
             pdf_bytes = create_invoice_pdf(client_name, model, parts_list_for_pdf, labor, total, is_final=False, labor_data_json=final_labor_json, job_id=job_id) # Draft if not closed
             st.session_state['download_invoice'] = {
                'data': pdf_bytes,
                'name': f"Invoice_{client_name}.pdf"
            }
             st.rerun()

    with col_close:
        if st.button("✅ Complete Job", type="primary", use_container_width=True):
            # Close Job - Deduct Stock ONLY for inventory items
            db.close_job(job_id, labor, parts_cost, total, final_parts_str, selected_parts_db, parts_data_json=final_parts_json, labor_data_json=final_labor_json)
            st.success("Job Completed & Moved to History!")
            st.rerun()

    # 4. WhatsApp Alert (New)
    st.divider()
    # WA Link Logic (Cloud Safe)
    # pywhatkit removed due to cloud server crashes (KeyError: DISPLAY)
    # Using st.link_button instead
    
    # Phone Cleaning
    clean_phone = str(phone_number).strip()
    if clean_phone.startswith("0"):
        clean_phone = "92" + clean_phone[1:]
    
    # Message
    msg_text = f"Assalam-o-Alaikum {client_name}! Your Inverter ({model}) is ready. Total Bill: Rs. {total_bill_val}. Please collect before 8 PM. - SK INVERTX TRADERS"
    encoded_msg = urllib.parse.quote(msg_text)
    
    # URL
    whatsapp_url = f"https://wa.me/{clean_phone}?text={encoded_msg}"
    
    st.link_button("🟢 Open in WhatsApp", whatsapp_url, use_container_width=True)

@st.dialog("Stock Control")
def inventory_dialog(item_id, item_name, current_price, current_cost, current_qty):
    st.header(f"📦 {item_name}")
    st.caption(f"Stock: {current_qty} | Sell: {current_price} | Cost: {current_cost}")
    
    with st.form("stock_update"):
        c1, c2 = st.columns(2)
        new_price = c1.number_input("Selling Price", value=float(current_price))
        new_cost = c2.number_input("Cost Price", value=float(current_cost) if pd.notnull(current_cost) else 0.0)
        
        c3, c4 = st.columns(2)
        add_qty = c3.number_input("Add Qty", min_value=0, value=0, step=1)
        del_qty = c4.number_input("Remove Qty", min_value=0, value=0, step=1)
        
        if st.form_submit_button("Update Inventory"):
            final_qty = max(0, current_qty + add_qty - del_qty)
            db.update_inventory_item(item_id, final_qty, new_cost, new_price)
            st.success(f"Updated {item_name}!")
            st.rerun()

    st.divider()
    if st.button("❌ Delete Item", type="primary", use_container_width=True):
         db.delete_inventory_item(item_id)
         st.success("Item Deleted!")
         st.rerun()



@st.dialog("Register New Client")
def add_client_dialog():
    st.header("👤 Add New Client")
    st.caption("Create a profile for a new customer. You can set an opening balance from their old 'Khata'.")
    
    with st.form("new_client_form"):
        name = st.text_input("Business / Client Name (Required)")
        col_c1, col_c2 = st.columns(2)
        city = col_c1.text_input("City", "Ghotki")
        phone = col_c2.text_input("Phone Number")
        
        col_c3, col_c4 = st.columns(2)
        address = col_c3.text_input("Address")
        nic = col_c4.text_input("NIC #")
        
        st.divider()
        st.markdown("**💰 Opening Balance (Old Khata)**")
        st.caption("If they already owe money (Debit), enter it here as a POSITIVE number. If you owe them (Advance), enter as NEGATIVE.")
        opening_bal = st.number_input("Opening Balance (Rs.)", value=0.0, step=1000.0)
        
        if st.form_submit_button("Create Client Profile", type="primary", use_container_width=True):
            if name:
                new_id = db.add_customer(name, city, phone, opening_bal, address, nic)
                st.success(f"✅ Client '{name}' Created! ID: {new_id}")
                time.sleep(1)
                st.rerun()
            else:
                st.error("Client Name is required.")

@st.dialog("Performance Card")
def employee_dialog(emp_id, emp_name, emp_role, emp_phone, emp_cnic):
    # Header Profile
    c_p1, c_p2 = st.columns([1, 4])
    with c_p1:
        st.markdown("<div style='font-size:3rem;'>👤</div>", unsafe_allow_html=True)
    with c_p2:
        st.header(f"{emp_name}")
        st.markdown(f"**Role:** {emp_role}")
    
    st.divider()
    
    # Personal Info
    st.caption("📋 Personal Information")
    i1, i2 = st.columns(2)
    i1.markdown(f"**📞 Phone:** {emp_phone if emp_phone else 'N/A'}")
    i2.markdown(f"**🆔 CNIC:** {emp_cnic if emp_cnic else 'N/A'}")
    
    st.divider()
    
    # Stats
    st.caption("📊 Performance Stats")
    
    perf = db.get_employee_performance()
    if not perf.empty and emp_name in perf['assigned_to'].values:
        row = perf[perf['assigned_to'] == emp_name].iloc[0]
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Jobs Done", row['total_completed'])
        c2.metric("Late Deliveries", row['total_late'], delta_color="inverse")
        c3.metric("On-Time %", f"{row['on_time_rate']}%")
        
        st.progress(row['on_time_rate'] / 100)
    else:
        st.info("No completed jobs yet.")

    st.divider()
    st.divider()
    
    # Delete Button Logic with Session State
    del_key = f"confirm_del_emp_{emp_id}"
    del_ledger_key = f"del_ledger_check_{emp_id}"
    
    if st.button("🗑️ Delete Employee", key=f"del_emp_btn_{emp_id}"):
        st.session_state[del_key] = True
        # Reset checkbox state on new open
        if del_ledger_key in st.session_state: del st.session_state[del_ledger_key]
        
    if st.session_state.get(del_key, False):
        # 1. Check Balance
        bal = db.calculate_employee_balance(emp_name)
        
        st.error("Are you sure you want to delete this employee?")
        
        if bal != 0:
            st.warning(f"⚠️ **Warning:** This employee has a remaining balance of Rs. {bal:,.2f}!")
        
        # 2. Checkbox for Ledger
        delete_ledger = st.checkbox("Also delete entire Ledger History for this employee?", key=del_ledger_key)
        
        col_conf1, col_conf2 = st.columns(2)
        
        if col_conf1.button("Yes, Delete", key=f"yes_del_emp_{emp_id}", type="primary"):
            # Execute deletion
            if delete_ledger:
                db.delete_employee_ledger(emp_name)
                st.toast(f"Ledger history for {emp_name} deleted.")
                
            db.delete_employee(emp_id)
            st.success("Employee Deleted!")
            # Clear state
            st.session_state[del_key] = False
            st.rerun()
            
        if col_conf2.button("Cancel", key=f"no_del_emp_{emp_id}"):
            st.session_state[del_key] = False
            st.rerun()

@st.dialog("Employee Payroll Manager")
def employee_payroll_dialog(emp_id, emp_name):
    st.caption(f"💰 Payroll & Ledger for {emp_name}")
    
    # Create 2 Tabs (Ledger History removed - now has dedicated full page)
    tab1, tab2 = st.tabs(["🛠️ Log Daily Work", "💸 Record Payment"])
    
    # TAB 1: Log Daily Work
    with tab1:
        st.markdown("### Log Work Completed")
        


        with st.form("log_work_form"):
            w_date = st.date_input("Date", value=datetime.now().date())
            
            col1, col2 = st.columns(2)
            units = col1.number_input("Units Fixed", min_value=0, value=0, step=1)
            rate = col2.number_input("Rate per Unit (Rs.)", min_value=0.0, value=100.0, step=10.0)
            
            # Additional Description
            desc_input = st.text_input("Description (Optional)", placeholder="e.g. Model XYZ, Overtime...")

            # Auto-calculate
            total_earning = units * rate
            st.markdown(f"### 💰 Total Earning: **Rs. {total_earning:,.2f}**")
            
            if st.form_submit_button("Add to Ledger", type="primary", use_container_width=True):
                if units > 0 or total_earning > 0: # Allow simple manual earning entry if units=0?
                    description = f"Fixed {units} Units @ Rs.{rate}"
                    if desc_input:
                        description += f" - {desc_input}"
                        
                    db.add_employee_ledger_entry(emp_name, w_date, "Work Log", description, total_earning, 0.0)
                    st.success(f"✅ Work log added! Earned: Rs. {total_earning:,.2f}")
                    st.rerun()
                else:
                    st.error("Units or Amount must be greater than 0")
    
    # TAB 2: Record Payment
    with tab2:
        st.markdown("### Record Payment to Employee")
        
        with st.form("payment_form"):
            p_date = st.date_input("Payment Date", value=datetime.now().date())
            amount = st.number_input("Amount Given (Rs.)", min_value=0.0, value=0.0, step=100.0)
            p_type = st.radio("Payment Type", ["Salary Payment", "Advance/Loan"], horizontal=True)
            
            if st.form_submit_button("Record Payment", type="primary", use_container_width=True):
                if amount > 0:
                    description = f"{p_type} - Rs. {amount:,.2f}"
                    db.add_employee_ledger_entry(emp_name, p_date, p_type, description, 0.0, amount)
                    st.success(f"✅ Payment recorded! Paid: Rs. {amount:,.2f}")
                    st.rerun()
                else:
                    st.error("Amount must be greater than 0")
    



# --- GLOBAL CSS (V4 MODERN THEME) ---
def local_css():
    st.markdown("""
    <style>
        /* Global Background - Deep Dark Blue/Purple Theme */
        .stApp {
            background-color: #0e1117; /* Streamlit Default Dark or Custom Deep */
            background-image: linear-gradient(#13141f, #0e1117);
            color: #ffffff;
        }
        
        /* 1. CSS Fixes: Remove White Space */
        .main .block-container {
            padding-top: 1rem;
            padding-right: 1rem;
            padding-left: 1rem;
            padding-bottom: 2rem;
        }

        /* 2. Sidebar Styling */
        section[data-testid="stSidebar"] {
            background-color: #0b0c15;
            background-image: linear-gradient(180deg, #1f2335 0%, #0b0c15 100%);
            border-right: 1px solid #2e3440;
        }
        
        /* 3. Card Container Styling */
        .modern-card {
            background-color: #1a1c24; /* Lighter than bg */
            border-radius: 15px;
            padding: 20px;
            margin-bottom: 15px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.3);
            border: 1px solid #2c2f3f;
            transition: all 0.3s ease;
        }
        .modern-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 8px 25px rgba(0,0,0,0.4);
            border-color: #7aa2f7;
        }
        
        /* Typography */
        h1, h2, h3, h4, h5 { font-family: 'Inter', sans-serif; font-weight: 600; }
        .big-text { font-size: 1.2rem; font-weight: bold; color: #fff; margin-bottom: 0.5rem; }
        .sub-text { font-size: 0.9rem; color: #a9b1d6; margin-bottom: 0.2rem; }
        .price-text { font-size: 1.1rem; font-weight: bold; color: #9ece6a; }
        .stock-low { color: #f7768e; font-weight: bold; }
        
        /* Custom Radio Button as Cards/Pills in Sidebar */
        [data-testid="stSidebar"] [data-testid="stRadio"] > div[role="radiogroup"] {
            gap: 12px;
        }
        
        [data-testid="stSidebar"] [data-testid="stRadio"] label {
            background-color: #1a1c24 !important;
            border: 1px solid #2e3440;
            border-radius: 12px;
            padding: 12px 16px;
            width: 100%;
            transition: all 0.3s ease;
            box-shadow: 0 2px 5px rgba(0,0,0,0.2);
            margin-bottom: 0px !important; /* Managed by gap */
        }
        
        [data-testid="stSidebar"] [data-testid="stRadio"] label:hover {
            border-color: #7aa2f7;
            background-color: #24283b !important;
            transform: translateX(5px);
        }
        
        /* Selected State */
        [data-testid="stSidebar"] [data-testid="stRadio"] label[data-checked="true"] {
             background: linear-gradient(90deg, #7aa2f7, #bb9af7) !important;
             color: white !important;
             border: none;
             box-shadow: 0 4px 15px rgba(122, 162, 247, 0.4);
        }
        
        /* Hide the default radio circle */
        [data-testid="stSidebar"] [data-testid="stRadio"] label > div:first-child {
            display: none;
        }
        [data-testid="stSidebar"] [data-testid="stRadio"] label p {
            font-size: 1.1rem;
            font-weight: 600;
        }
        
    </style>
    """, unsafe_allow_html=True)

local_css()

# --- APP NAVIGATION Logic ---
if 'page' not in st.session_state:
    st.session_state.page = "📊 Dashboard"

def update_nav():
    st.session_state.page = st.session_state.nav_radio

# --- SIDEBAR NAV ---
with st.sidebar:
    if os.path.exists("logo_sidebar.png"):
        st.image("logo_sidebar.png", width=150)
    elif os.path.exists("logo.png"):
        st.image("logo.png", width=120)
    else:
        st.image("https://cdn-icons-png.flaticon.com/512/3665/3665922.png", width=50) # Fallback
        
    st.markdown("### SK INVERTX TRADERS")
    st.caption("v4.6 FIXED")
    st.markdown("---")
    
    # Navigation Pills
    options = ["⚡ Quick Invoice", "🔧 Repair Center", "👥 Partners & Ledger", "📦 Product Inventory", "👷 Staff & Payroll", "📊 Business Reports"]
    
    # Determine index safely
    try:
        curr_idx = options.index(st.session_state.page)
    except ValueError:
        curr_idx = 0
        
    st.radio(
        "Navigate", 
        options,
        index=curr_idx,
        key="nav_radio",
        on_change=update_nav,
        label_visibility="collapsed"
    )

# Shortcut for readability
menu = st.session_state.page



def update_sales_grid():
    """
    Callback to sync data_editor changes to session_state.sales_grid_data immediately.
    Solves persistence issues on first edit.
    """
    state = st.session_state["sales_editor"]
    df = st.session_state.sales_grid_data.copy()
    
    # 1. Handle Edited Rows (Indices refer to original DF)
    # Important: Process edits BEFORE adds/deletes if indices rely on original
    for idx, changes in state.get("edited_rows", {}).items():
        # Ensure idx is valid
        if idx in df.index:
            for col, val in changes.items():
                df.at[idx, col] = val

    # 2. Handle Deleted Rows
    deleted_rows = state.get("deleted_rows", [])
    if deleted_rows:
        df = df.drop(index=deleted_rows)
        # Reset index to avoid holes, but careful if edits relied on old index?
        # Streamlit guarantees deleted_rows indices correspond to the state entering the editor.
        # Edits also correspond to that state. So we can drop safely after applying edits.
    
    # 3. Handle Added Rows
    added_rows = state.get("added_rows", [])
    for new_row in added_rows:
        # Fill defaults if missing
        defaults = {"Item Name": "", "Qty": 1, "Rate": 0.0, "Discount": 0.0, "Return Qty": 0, "Total": 0.0}
        defaults.update(new_row)
        df = pd.concat([df, pd.DataFrame([defaults])], ignore_index=True)

    # 4. Global Recalculation
    # Clean Types
    df = df.reset_index(drop=True)
    df['Qty'] = pd.to_numeric(df['Qty'], errors='coerce').fillna(0)
    df['Rate'] = pd.to_numeric(df['Rate'], errors='coerce').fillna(0.0)
    df['Discount'] = pd.to_numeric(df.get('Discount', 0), errors='coerce').fillna(0.0)
    df['Return Qty'] = pd.to_numeric(df['Return Qty'], errors='coerce').fillna(0)
    
    # Apply Formula
    df['Total'] = ((df['Qty'] - df['Return Qty']) * df['Rate']) - df['Discount']
    
    # Save back
    st.session_state.sales_grid_data = df

# --- TAB: QUICK INVOICE ---
if menu == "⚡ Quick Invoice":
    st.title("⚡ Quick Sales Invoice")
    
    # Create Tabs
    tab_new, tab_hist = st.tabs(["➕ New Invoice", "📜 Invoice History"])

    # --- TAB 1: NEW INVOICE ---
    with tab_new:
        # Session State for Grid
        if 'sales_grid_data' not in st.session_state:
            # Initialize with 3 empty rows for convenience
            st.session_state.sales_grid_data = pd.DataFrame(
                [{"Item Name": "", "Qty": 1, "Rate": 0.0, "Discount": 0.0, "Return Qty": 0, "Total": 0.0}] * 3
            )

        # 1. HEADER SECTION
        with st.container(border=True):
            c1, c2, c3 = st.columns([2, 1, 1])
            
            # Get Customer List
            customers_df = db.get_all_customers()
            cust_names = customers_df['name'].tolist() if not customers_df.empty else []
            
            with c1:
                customer_name = st.selectbox("Select Customer", ["Counter Sale"] + cust_names, index=0)
                
            with c2:
                inv_date = st.date_input("Invoicing Date", value=datetime.now().date())
                
            with c3:
                # Auto-generated Invoice #
                next_inv = db.get_next_invoice_number()
                st.text_input("Invoice #", value=next_inv, disabled=True)

        # 1.5 PRODUCT SELECTION (New)
        st.markdown("### 📦 Add Product")
        
        # Fetch Inventory for Dropdown
        inventory_df = db.get_inventory()
        inv_options = {}
        if not inventory_df.empty:
            # Create a label mapping: "Item Name - Rs. Price (Stock: X)" -> ID/Row
             for _, row in inventory_df.iterrows():
                 lbl = f"{row['item_name']} | Stock: {row['quantity']} | Rs. {row['selling_price']}"
                 inv_options[lbl] = row
        
        col_prod1, col_prod2 = st.columns([3, 1])
        with col_prod1:
             selected_prod_label = st.selectbox("Select Stock Item", options=["Select Item..."] + list(inv_options.keys()), index=0, key="quick_inv_product_select")
        
        with col_prod2:
             if st.button("⬇ Add to Cart", type="secondary", use_container_width=True):
                 if selected_prod_label and selected_prod_label != "Select Item...":
                     item_data = inv_options[selected_prod_label]
                     
                     # Create new row data
                     new_row = {
                         "Item Name": item_data['item_name'],
                         "Qty": 1,
                         "Rate": float(item_data['selling_price']),
                         "Discount": 0.0,
                         "Return Qty": 0,
                         "Total": float(item_data['selling_price'])
                     }
                     
                     # Append to session state
                     st.session_state.sales_grid_data = pd.concat([
                         st.session_state.sales_grid_data, 
                         pd.DataFrame([new_row])
                     ], ignore_index=True)
                     
                     st.toast(f"Added {item_data['item_name']}")
                     time.sleep(0.5)
                     st.rerun()
                 else:
                     st.toast("Please select an item first.")

        # 2. GRID ENTRY SYSTEM
        st.subheader("🛒 Items Cart")
        
        # Editable Dataframe
        # We use column_config to enforce types
        edited_df = st.data_editor(
            st.session_state.sales_grid_data,
            num_rows="dynamic",
            use_container_width=True,
            column_config={
                "Item Name": st.column_config.TextColumn("Item Name (Type freely)", width="large", required=True),
                "Qty": st.column_config.NumberColumn("Qty", min_value=0, step=1, required=True),
                "Rate": st.column_config.NumberColumn("Rate (Rs.)", min_value=0.0, step=10.0, required=True),
                "Discount": st.column_config.NumberColumn("Discount", min_value=0.0, step=10.0),
                "Return Qty": st.column_config.NumberColumn("Return Qty", min_value=0, step=1),
                "Total": st.column_config.NumberColumn("Total", disabled=True) # Calculated column
            },
            key="sales_editor",
            on_change=update_sales_grid
        )
        
        # 3. REAL-TIME CALCULATIONS
        df_display = st.session_state.sales_grid_data.copy()
        
        # Sums
        subtotal = df_display['Total'].sum()

        # Footer Inputs
        st.divider()
        fc1, fc2, fc3 = st.columns([2, 1, 1])
        
        with fc2:
            st.markdown(f"**Subtotal:** Rs. {subtotal:,.2f}")
            freight = st.number_input("Freight / Kiraya", min_value=0.0, step=50.0)
            misc = st.number_input("Labor / Misc", min_value=0.0, step=50.0)
            
        with fc3:
            grand_total = subtotal + freight + misc
            st.markdown(f"""<div style="background-color:#1a1c24; padding:15px; border-radius:10px; border:2px solid #7aa2f7; text-align:center;"><div style="font-size:0.9rem; color:#a9b1d6;">💰 Net Payable</div><div style="font-size:2rem; font-weight:bold; color:#7aa2f7;">Rs. {grand_total:,.0f}</div></div>""", unsafe_allow_html=True)
            
            cash_received = st.number_input("Cash Received", min_value=0.0, step=100.0)
            
            st.write("")
            if st.button("✅ Save & Print", type="primary", use_container_width=True):
                if customer_name and grand_total >= 0:
                    # Filter out empty rows
                    valid_items = df_display[df_display['Item Name'].str.strip() != ""]
                    
                    # Logic Change: Allow if Cash Received > 0 even if no items
                    if valid_items.empty and cash_received == 0:
                        st.error("Please add at least one item or enter Cash Received.")
                    else:
                        # If Cash Only, create dummy item for record
                        if valid_items.empty and cash_received > 0:
                            valid_items = pd.DataFrame([{
                                "Item Name": "Payment Received", 
                                "Qty": 1, 
                                "Rate": 0.0, 
                                "Discount": 0.0, 
                                "Return Qty": 0, 
                                "Total": 0.0
                            }])
                        
                        # Save to DB
                        success = db.record_invoice(next_inv, customer_name, valid_items, freight, misc, grand_total)
                        
                        if success:
                            # Record Cash Payment if any
                            if cash_received > 0:
                                db.add_ledger_entry(customer_name, f"Cash Payment for Inv #{next_inv}", 0.0, cash_received, inv_date)
                            
                            st.success(f"Invoice {next_inv} Saved Successfully!")
                            
                            # Fetch Balances for Invoice
                            inv_led = db.get_ledger_entries(customer_name)
                            cur_bal_n = 0.0
                            if not inv_led.empty:
                                cur_bal_n = inv_led['debit'].sum() - inv_led['credit'].sum()
                            
                            # Previous Balance logic:
                            # Current Balance = Previous + GrandTotal - CashReceived
                            # => Previous = Current - GrandTotal + CashReceived
                            # (Wait, if we already added ledger entries for GrandTotal AND CashReceived, then Current represents the final state)
                            # So Previous Balance is Current - (Total - Cash) ? No.
                            # Previous Balance is strictly what it was BEFORE this transaction (invoice + cash).
                            # So Previous = Current - GrandTotal + CashReceived
                            prev_bal_n = cur_bal_n - grand_total + cash_received
                            
                            # Generate PDF
                            pdf_bytes = create_sales_invoice_pdf(
                                next_inv, customer_name, inv_date.strftime('%Y-%m-%d'), 
                                valid_items, subtotal, freight, misc, grand_total, prev_bal_n, cur_bal_n, cash_received
                            )
                            
                            # Show Download
                            st.download_button(
                                "📥 Download Invoice PDF", 
                                data=pdf_bytes, 
                                file_name=f"Invoice_{next_inv}.pdf", 
                                mime="application/pdf", 
                                type="primary",
                                use_container_width=True
                            )
                            
                            # Clear Grid
                            del st.session_state.sales_grid_data
                            time.sleep(2)
                            st.rerun()
                else:
                    st.error("Invalid Customer or Total.")

    # --- TAB 2: INVOICE HISTORY ---
    with tab_hist:
        st.subheader("📜 Search Invoice History")
        
        col_s1, col_s2 = st.columns([3, 1])
        with col_s1:
             search_inv_input = st.text_input("Enter Invoice #", placeholder="e.g. INV-2026-001")
             
        if search_inv_input:
             # Fetch Items
             items_df = db.get_invoice_items(search_inv_input)
             
             if not items_df.empty:
                 st.success(f"✅ Found {len(items_df)} items for {search_inv_input}")
                 
                 # Extract Meta Data from first row
                 first_row = items_df.iloc[0]
                 cust_name_h = first_row['customer_name']
                 date_h = first_row['sale_date']
                 
                 # Display Meta
                 st.markdown(f"**Customer:** {cust_name_h} | **Date:** {date_h}")
                 
                 # Prepare Display DF
                 # Columns in Sales: id, invoice_id, customer_name, item_name, quantity_sold, sale_price, return_quantity, total_amount, sale_date
                 disp_ph = items_df[['item_name', 'quantity_sold', 'sale_price', 'return_quantity', 'total_amount']].copy()
                 disp_ph.columns = ['Item Name', 'Qty', 'Rate', 'Return Qty', 'Total']
                 
                 st.dataframe(disp_ph, use_container_width=True)
                 
                 # Calculations
                 subtotal_h = disp_ph['Total'].sum()
                 
                 # Try to get Grand Total from Ledger to infer Freight/Misc
                 ledger_total = db.get_invoice_total_from_ledger(search_inv_input)
                 
                 # Fetch Cash Received if any
                 cash_received_h = db.get_cash_received_for_invoice(search_inv_input)
                 
                 # ADD TO TABLE: specific request to show cash received in table
                 if cash_received_h > 0:
                     # Create a row for Cash Received
                     cr_row = pd.DataFrame([{
                         'Item Name': "💰 **Cash Received**",
                         'Qty': 0,
                         'Rate': 0,
                         'Return Qty': 0,
                         'Total': cash_received_h 
                     }])
                     disp_ph = pd.concat([disp_ph, cr_row], ignore_index=True)

                 
                 # Inferred Extras
                 diff = 0.0
                 if ledger_total > subtotal_h:
                     diff = ledger_total - subtotal_h
                     
                 # Display Totals
                 st.divider()
                 h_c1, h_c2 = st.columns([3, 1])
                 with h_c2:
                     st.markdown(f"**Subtotal:** Rs. {subtotal_h:,.2f}")
                     if diff > 0:
                         st.markdown(f"**Freight/Misc:** Rs. {diff:,.2f}")
                     
                     st.markdown(f"### Total: Rs. {ledger_total:,.0f}")
                     
                     if cash_received_h > 0:
                         # NEW PROMINENT DISPLAY
                         st.markdown(f"""
                         <div style="background-color:#1a1c24; padding:10px; border-radius:10px; border:2px solid #9ece6a; text-align:center; margin-top:10px;">
                            <div style="font-size:0.9rem; color:#a9b1d6;">✅ Cash Received</div>
                            <div style="font-size:1.5rem; font-weight:bold; color:#9ece6a;">Rs. {cash_received_h:,.0f}</div>
                         </div>
                         """, unsafe_allow_html=True)
                     
                     # Re-Print Button
                     st.write("") # Spacer
                     if st.button("🖨️ Re-Print Invoice", key=f"reprint_{search_inv_input}", use_container_width=True):
                         # Generate PDF
                         # We need balances for PDF
                         led_entries = db.get_ledger_entries(cust_name_h)
                         cur_bal_p = 0.0
                         if not led_entries.empty:
                            cur_bal_p = led_entries['debit'].sum() - led_entries['credit'].sum()
                         
                         # Prev Balance Approximation for Reprint
                         # Prev = Current - (Billed - Cash)
                         # If Billed is 0 (Receipt), Prev = Current + Cash
                         # We must respect the historical context ideally, but for reprint we often show current snapshot 
                         # OR we try to back-calculate. 
                         # Let's use the standard formula: Prev = Current - GrandTotal + Cash
                         prev_bal_p = cur_bal_p - ledger_total + cash_received_h
                         
                         pdf_bytes = create_sales_invoice_pdf(
                             search_inv_input, cust_name_h, date_h, 
                             items_df, subtotal_h, diff, 0.0, ledger_total, prev_bal_p, cur_bal_p, cash_received_h
                         )
                         
                         st.download_button(
                            "📥 Download PDF",
                            data=pdf_bytes,
                            file_name=f"Invoice_{search_inv_input}.pdf",
                            mime="application/pdf",
                            type="primary",
                            use_container_width=True
                         )
                     # Ends the first block above


             else:
                 st.info("No invoice found with that number. Please check the ID (e.g., INV-2026-001).")
# --- TAB: ACCOUNTS LEDGER ---


# --- TAB: CREATE JOB (WIZARD) ---
# --- TAB: REPAIR CENTER ---
elif menu == "🔧 Repair Center":
    st.title("🔧 Repair Center")
    
    tab1, tab2, tab3 = st.tabs(["➕ New Job", "🛠️ Active Jobs", "📜 History"])
    
    # TAB 1: NEW JOB (Legacy Create Job Wizard)
    with tab1:
        st.subheader("➕ New Job Wizard")
        
        # Initialize Wizard State
        if 'wiz_step' not in st.session_state:
            st.session_state.wiz_step = 1
            st.session_state.wiz_data = {}

        # Progress Bar
        steps = ["Client", "Device", "Photo", "Review"]
        curr = st.session_state.wiz_step
        st.progress(curr / 4)
        st.caption(f"Step {curr} of 4: {steps[curr-1]}")
        
        # Container for Wizard
        with st.container(border=True):
            
            # STEP 1: CLIENT
            if curr == 1:
                st.subheader("1. Client Details")
                c1, c2 = st.columns(2)
                name = c1.text_input("Full Name", value=st.session_state.wiz_data.get('name',''))
                phone = c2.text_input("Phone Number", value=st.session_state.wiz_data.get('phone',''))
                
                if st.button("Next ➡", type="primary"):
                    if name:
                        st.session_state.wiz_data['name'] = name
                        st.session_state.wiz_data['phone'] = phone
                        st.session_state.wiz_step = 2
                        st.rerun()
                    else:
                        st.error("Client Name is required.")

            # STEP 2: DEVICE
            elif curr == 2:
                st.subheader("2. Device Information")
                c1, c2 = st.columns(2)
                model = c1.text_input("Device Model", value=st.session_state.wiz_data.get('model',''))
                due = c2.date_input("Due Date", min_value=datetime.now().date())
                issue = st.text_area("Issue Description", value=st.session_state.wiz_data.get('issue',''))
                
                emps = db.get_employee_names()
                assign = st.selectbox("Assign Technician", emps if emps else ["Unassigned"])
                
                c_back, c_next = st.columns([1, 1])
                if c_back.button("⬅ Back"):
                    st.session_state.wiz_step = 1
                    st.rerun()
                if c_next.button("Next ➡", type="primary"):
                    if model and issue:
                        st.session_state.wiz_data['model'] = model
                        st.session_state.wiz_data['due'] = due
                        st.session_state.wiz_data['issue'] = issue
                        st.session_state.wiz_data['assign'] = assign
                        st.session_state.wiz_step = 3
                        st.rerun()
                    else:
                        st.error("Model and Issue are required.")

            # STEP 3: PHOTO (Placeholder)
            elif curr == 3:
                st.subheader("3. Intake Photos")
                st.info("Upload functionality connected to secure storage.")
                uploaded = st.file_uploader("Upload Device Photo (Optional)", type=['png', 'jpg'])
                
                c_back, c_next = st.columns([1, 1])
                if c_back.button("⬅ Back"):
                    st.session_state.wiz_step = 2
                    st.rerun()
                if c_next.button("Next ➡", type="primary"):
                    st.session_state.wiz_step = 4
                    st.rerun()

            # STEP 4: REVIEW
            elif curr == 4:
                st.subheader("4. Review & Launch")
                data = st.session_state.wiz_data
                
                st.markdown(f"""
                **Client:** {data.get('name')} ({data.get('phone')})  
                **Device:** {data.get('model')}  
                **Issue:** {data.get('issue')}  
                **Technician:** {data.get('assign')}  
                **Due:** {data.get('due')}
                """)
                
                c_back, c_submit = st.columns([1, 1])
                if c_back.button("⬅ Back"):
                    st.session_state.wiz_step = 3
                    st.rerun()
                
                if c_submit.button("Open Job", type="primary"):
                    db.add_repair(
                        data['name'], 
                        data['model'], 
                        data['issue'], 
                        "Pending", 
                        data['phone'], 
                        data['assign'], 
                        data['due']
                    )
                    # QR CODE GENERATION
                    qr_data = f"JOB-{db.get_active_repairs().iloc[-1]['id']}" 
                    last_id = db.get_active_repairs()['id'].max()
                    
                    qr = qrcode.QRCode(version=1, box_size=10, border=5)
                    qr.add_data(f"JOB-{last_id}")
                    qr.make(fit=True)
                    img = qr.make_image(fill_color="black", back_color="white")
                    
                    # Convert to bytes for streamlit
                    buf = BytesIO()
                    img.save(buf)
                    byte_im = buf.getvalue()
                    
                    st.image(byte_im, caption="🖨️ Print Label", width=200)
                    
                    st.success("Job Created Successfully!")
                    # Reset
                    st.session_state.wiz_step = 1
                    st.session_state.wiz_data = {}
                    
                    if st.button("Start New Job"):
                        st.rerun()

    # TAB 2: ACTIVE REPAIRS
    with tab2:
        st.subheader("🛠️ Active Jobs & Billing")
        
        # Check for download trigger from dialog
        if 'download_invoice' in st.session_state:
            dl = st.session_state['download_invoice']
            st.success("Invoice Ready!")
            st.download_button("📥 Download PDF", data=dl['data'], file_name=dl['name'], mime="application/pdf", key="dl_btn_active")
            if st.button("Clear Notification", key="clear_notif_active"): 
                del st.session_state['download_invoice']
                st.rerun()

        # Scan to Open (Search)
        search_qr = st.text_input("📷 Scan QR / Enter Job ID (e.g., JOB-123)", key="qr_search")
        
        jobs = db.get_active_repairs()
        
        if not jobs.empty:
            # Filter Logic
            if search_qr:
                # Extract number if format is JOB-123
                clean_search = search_qr.upper().replace("JOB-", "").strip()
                # Search in ID or Client Name
                jobs = jobs[jobs['id'].astype(str) == clean_search]
                if jobs.empty:
                    st.warning("No job found with that ID.")

            cols = st.columns(3)
            today = datetime.now().date()
            
            for idx, row in jobs.iterrows():
                with cols[idx % 3]:
                    # Status Logic
                    days_left = 99
                    status_color = "#7aa2f7" # Blue
                    is_late_flag = False
                    
                    if row['due_date']:
                        try:
                            d = datetime.strptime(row['due_date'], '%Y-%m-%d').date()
                            days_left = (d - today).days
                            
                            if days_left < 0:
                                status_color = "#eb4d4b" # Red (Overdue)
                                is_late_flag = True
                                badge_text = f"🚨 OVERDUE ({abs(days_left)} Days)"
                            elif days_left <= 1: # Today or Tomorrow
                                status_color = "#f0932b" # Orange (Urgent)
                                badge_text = f"⚠️ Due Soon ({days_left} Days)"
                            else:
                                status_color = "#6ab04c" # Green (Safe)
                                badge_text = f"⏱ {days_left} Days Left"
                        except: 
                            badge_text = "No Date"
                    else:
                        badge_text = "No Date"
                    
                    # Render Card
                    st.markdown(f"""<div class="modern-card" style="border-top: 5px solid {status_color};"><div style="display:flex; justify-content:space-between;"><span style="font-weight:bold; color:#a9b1d6;">#{row['id']}</span><span style="background:{status_color}33; color:{status_color}; padding:2px 8px; border-radius:4px; font-size:0.8rem;">{row['status']}</span></div><div class="big-text" style="margin-top:10px;">{row['client_name']}</div><div class="sub-text">📱 {row['inverter_model']}</div><div class="sub-text">🔧 {row['assigned_to']}</div><div class="sub-text" style="margin-top:10px; font-weight:bold; color:{status_color};">{badge_text}</div></div>""", unsafe_allow_html=True)
                    
                    # ACTION: Open Dialog
                    if st.button(f"Manage {row['client_name']}", key=f"btn_{row['id']}", use_container_width=True):
                        p_data = row['parts_data'] if 'parts_data' in row and pd.notna(row['parts_data']) else "[]"
                        l_data = row.get('labor_data', "[]")
                        if pd.isna(l_data): l_data = "[]"
                        repair_dialog(row['id'], row['client_name'], row['issue'], row['inverter_model'], row['used_parts'], row['service_cost'], row['phone_number'], row['total_cost'], p_data, l_data, row['assigned_to'])

        else:
            st.info("No active jobs. Good job team! 🌴")

    # TAB 3: JOB HISTORY
    with tab3:
        st.subheader("📜 Completed Repairs")
        
        # Check for download trigger from any invoice generation
        if 'download_invoice' in st.session_state:
            dl = st.session_state['download_invoice']
            st.success("Invoice Ready!")
            st.download_button("📥 Download PDF", data=dl['data'], file_name=dl['name'], mime="application/pdf", key="dl_btn_history")
            if st.button("Clear Notification", key="clear_notif_history"): 
                del st.session_state['download_invoice']
                st.rerun()

        # Simple Search Filter
        query = st.text_input("Search History", placeholder="Client, Device, Date...")
        history = db.get_job_history()
        
        if not history.empty:
            if query:
               history = history[history.astype(str).apply(lambda x: x.str.contains(query, case=False)).any(axis=1)]
            
            # Consistent Card Grid for History
            h_cols = st.columns(3)
            for idx, row in history.iterrows():
                with h_cols[idx % 3]:
                    st.markdown(f"""<div class="modern-card" style="border-left: 4px solid #9ece6a;"><div class="big-text">{row['client_name']}</div><div class="sub-text">{row['inverter_model']}</div><div class="sub-text">Completed: {row['completion_date']}</div><div class="price-text" style="text-align:right; margin-top:10px;">Rs. {row['total_cost']:,.2f}</div></div>""", unsafe_allow_html=True)
                    
                    # Invoice Button
                    if st.button("📄 Get Invoice", key=f"hist_inv_{row['id']}", use_container_width=True):
                        # Reconstruct Data
                        # We don't have individual parts prices, so we bundle.
                        parts_bundle = [{'name': "Spare Parts & Consumables", 'price': row['parts_cost']}]
                        pdf = create_invoice_pdf(row['client_name'], row['inverter_model'], parts_bundle, row['service_cost'], row['total_cost'], is_final=True)
                        st.session_state['download_invoice'] = {
                            'data': pdf,
                            'name': f"Invoice_{row['client_name']}_Final.pdf"
                        }
                        st.rerun()
        else:
            st.info("No history found.")

# --- TAB: INVENTORY ---
elif menu == "📦 Product Inventory":
    st.title("📦 Product Inventory")
    
    # Create Tabs
    tab1, tab2 = st.tabs(["📦 Stock Management", "💰 Stock Valuation"])

    # TAB 1: STOCK MANAGEMENT
    with tab1:
        # 1. Add Stock Area (Calculator Mode)
        with st.expander("➕ Add New Stock Item", expanded=True):
            c1, c2, c3 = st.columns(3)
            i_name = c1.text_input("Item Name", key="new_i_name")
            cat = c2.text_input("Category", placeholder="e.g. Battery", key="new_i_cat")
            qty = c3.number_input("Quantity", min_value=1, step=1, key="new_i_qty")
            
            c4, c5 = st.columns(2)
            p_cost = c4.number_input("Cost Price (Rs.)", 0.0, step=10.0, key="new_i_cost")
            p_sell = c5.number_input("Selling Price (Rs.)", 0.0, step=10.0, key="new_i_sell")
            
            # Calculator Display
            tot_cost = qty * p_cost
            tot_sell = qty * p_sell
            
            st.markdown(f"""
    <div style="padding:10px; background:#1a1c24; border-radius:8px; margin-bottom:10px;">
    <span style="color:#a9b1d6; margin-right:15px;">📊 Calculator:</span>
    <strong style="color:#f7768e">Total Cost: Rs. {tot_cost:,.0f}</strong> &nbsp;|&nbsp; 
    <strong style="color:#9ece6a">Total Selling: Rs. {tot_sell:,.0f}</strong>
    </div>
    """, unsafe_allow_html=True)

            if st.button("Add Item", type="primary"):
                if i_name:
                    db.add_inventory_item(i_name, cat if cat else "General", datetime.now(), qty, p_cost, p_sell)
                    st.success("Item Added Successfully!")
                    time.sleep(0.5)
                    st.rerun()
                else:
                    st.error("Item Name is required.")

        # 2. Search & Filter
        st.divider()
        search_inv = st.text_input("Search (Name, Category, or ID)", placeholder="Type to search...")
        
        inv = db.get_inventory()
        if not inv.empty:
            if search_inv:
                # Flexible Search
                mask = inv.apply(lambda x: search_inv.lower() in str(x['item_name']).lower() or 
                                        search_inv.lower() in str(x['category']).lower() or 
                                        search_inv.lower() in str(x['id']).lower(), axis=1)
                inv = inv[mask]
            
            # Grid Layout
            i_cols = st.columns(3)
            for idx, row in inv.iterrows():
                with i_cols[idx % 3]:
                    # Visual Logic
                    low_stock = row['quantity'] < 5
                    stock_color = "#f7768e" if low_stock else "#9ece6a"
                    
                    # Calculating Totals for Display
                    t_cost = row['quantity'] * row['cost_price']
                    t_sell = row['quantity'] * row['selling_price']
                    
                    st.markdown(f"""<div class="modern-card"><div style="display:flex; justify-content:space-between;"><span class="sub-text">#{row['id']}</span><span class="sub-text">{row['category']}</span></div><div class="big-text">{row['item_name']}</div><div style="display:flex; justify-content:space-between; margin-top:10px; font-size:0.9rem;"><span>Cost: Rs. {row['cost_price']}</span><span>Sell: Rs. {row['selling_price']}</span></div><div style="display:flex; justify-content:space-between; margin-top:5px; font-size:0.9rem;"><span>T.Cost: Rs. {t_cost:,.0f}</span><span>T.Sell: Rs. {t_sell:,.0f}</span></div><div style="margin-top:10px; padding-top:10px; border-top:1px solid #2c2f3f; text-align:right;"><span style="color:{stock_color}; font-weight:bold; font-size:1.1rem;">{row['quantity']} Units</span></div></div>""", unsafe_allow_html=True)
                    
                    # ACTION: Open Dialog
                    if st.button(f"✏ Manage", key=f"inv_btn_{row['id']}", use_container_width=True):
                        inventory_dialog(row['id'], row['item_name'], row['selling_price'], row['cost_price'], row['quantity'])
        else:
            st.info("Inventory Empty.")

    # TAB 2: STOCK VALUATION
    with tab2:
        render_stock_valuation_table(db)



# --- TAB: BUSINESS REPORTS ---
elif menu == "📊 Business Reports":
    st.title("📊 Business Reports & Analytics")

    # --- SECTION A: DAILY CASH BOOK (Moved to Top) ---
    st.header("💵 Daily Cash Book")
    
    # Date Selector
    report_date = st.date_input("Select Date", value=datetime.now().date())
    
    # Fetch Data
    cash_in, cash_out, net_cash = db.get_daily_cash_flow(report_date)

    # Display Metrics
    r_col1, r_col2, r_col3 = st.columns(3)
    with r_col1:
         st.markdown(f"""<div class="modern-card" style="text-align:center; border-left: 5px solid #9ece6a;"><div class="sub-text">🟢 Cash Received</div><div style="font-size:2rem; font-weight:bold; color:#9ece6a;">Rs. {cash_in:,.0f}</div></div>""", unsafe_allow_html=True)
         
    with r_col2:
         st.markdown(f"""<div class="modern-card" style="text-align:center; border-left: 5px solid #f7768e;"><div class="sub-text">🔴 Shop Expenses</div><div style="font-size:2rem; font-weight:bold; color:#f7768e;">Rs. {cash_out:,.0f}</div></div>""", unsafe_allow_html=True)
         
    with r_col3:
         net_color = "#7aa2f7" if net_cash >= 0 else "#f7768e"
         st.markdown(f"""<div class="modern-card" style="text-align:center; border-left: 5px solid {net_color};"><div class="sub-text">💰 Net Cash in Drawer</div><div style="font-size:2rem; font-weight:bold; color:{net_color};">Rs. {net_cash:,.0f}</div></div>""", unsafe_allow_html=True)

    # Add Expense Dialog/Expander
    with st.expander("➕ Record Shop Expense"):
         with st.form("add_exp_form"):
              e_desc = st.text_input("Expense Description (e.g., Tea, Lunch, Bill)")
              e_amt = st.number_input("Amount (Rs.)", min_value=0.0, step=50.0)
              e_cat = st.selectbox("Category", ["Shop Maintenance", "Food/Tea", "Utility Bill", "Salary", "Other"])
              
              if st.form_submit_button("Record Expense"):
                   if e_desc and e_amt > 0:
                        db.add_expense(report_date, e_desc, e_amt, e_cat)
                        st.success("Expense Recorded!")
                        st.rerun()
                   else:
                        st.error("Please enter description and amount.")

    # Show Expenses Table
    expenses_df = db.get_expenses(report_date)
    if not expenses_df.empty:
         st.markdown("### Expense Details")
         st.dataframe(expenses_df[['description', 'amount', 'category']], use_container_width=True)
         
         # Total Amount (Auto Calculator)
         total_exp_day = expenses_df['amount'].sum()
         st.markdown(f"""<div style="text-align:right; font-size:1.2rem; font-weight:bold; margin-top:5px; padding:10px; background:#1a1c24; border-radius:8px;">Total Expenses: <span style="color:#f7768e">Rs. {total_exp_day:,.2f}</span></div>""", unsafe_allow_html=True)
    
    st.divider()

    # --- SECTION B: REPAIR CENTER OVERVIEW (New Design) ---
    st.header("🔧 Repair Center Overview")
    
    # Filter Selection
    filter_option = st.radio("Select Period", ["Today", "This Week", "This Month"], horizontal=True)
    
    # Calculate Metrics based on Filter
    all_repairs = db.get_all_repairs()
    
    # Determine Date Range
    now = datetime.now()
    today = now.date()
    start_filter_date = today
    
    if filter_option == "This Week":
        start_filter_date = today - timedelta(days=today.weekday()) # Start of week (Monday)
    elif filter_option == "This Month":
        start_filter_date = date(today.year, today.month, 1) # Start of month
    
    # Metrics Variables
    repairs_received = 0
    repairs_delivered = 0
    active_now = 0
    
    if not all_repairs.empty:
        # Active Now (Status != Delivered) - Independent of time filter usually, but let's show CURRENT active
        active_now = len(all_repairs[all_repairs['status'] != 'Delivered'])
        
        # Received (Compare start_date)
        # Ensure start_date is date object
        try:
             # Vectorized conversion if possible, or loop
             # Safe loop for small dataset
             for _, row in all_repairs.iterrows():
                 try:
                     s_date = datetime.strptime(str(row['start_date']), '%Y-%m-%d').date()
                     if s_date >= start_filter_date:
                         repairs_received += 1
                 except: pass
                 
                 if row['status'] == 'Delivered' and row['completion_date']:
                     try:
                         c_date = datetime.strptime(str(row['completion_date']), '%Y-%m-%d').date()
                         if c_date >= start_filter_date:
                             repairs_delivered += 1
                     except: pass
        except Exception as e:
            pass

    inventory = db.get_inventory()
    low_stock_count = len(inventory[inventory['quantity'] < 5]) if not inventory.empty else 0

    # Display Cards
    rc1, rc2, rc3, rc4 = st.columns(4)
    with rc1:
        st.markdown(f"""<div class="modern-card" style="text-align:center;"><div class="sub-text">Repairs Received</div><div style="font-size:2rem; font-weight:bold; color:#7aa2f7;">{repairs_received}</div><div class="sub-text" style="font-size:0.8rem;">{filter_option}</div></div>""", unsafe_allow_html=True)
    with rc2:
        st.markdown(f"""<div class="modern-card" style="text-align:center;"><div class="sub-text">Repairs Delivered</div><div style="font-size:2rem; font-weight:bold; color:#9ece6a;">{repairs_delivered}</div><div class="sub-text" style="font-size:0.8rem;">{filter_option}</div></div>""", unsafe_allow_html=True)
    with rc3:
        st.markdown(f"""<div class="modern-card" style="text-align:center;"><div class="sub-text">Active Now</div><div style="font-size:2rem; font-weight:bold; color:#e0af68;">{active_now}</div><div class="sub-text" style="font-size:0.8rem;">Live Count</div></div>""", unsafe_allow_html=True)
    with rc4:
         color_stk = "#f7768e" if low_stock_count > 0 else "#9ece6a"
         st.markdown(f"""<div class="modern-card" style="text-align:center;"><div class="sub-text">Low Stock Alerts</div><div style="font-size:2rem; font-weight:bold; color:{color_stk};">{low_stock_count}</div><div class="sub-text" style="font-size:0.8rem;">Inventory</div></div>""", unsafe_allow_html=True)

    st.divider()

    # --- SECTION C: STOCK VALUATION (Prominent) ---
    stock_value = db.get_inventory_valuation()
    st.header(f"📦 Total Stock Value: :green[Rs. {stock_value:,.2f}]")
    
    with st.expander("📦 Detailed Stock Valuation Table", expanded=True):
        render_stock_valuation_table(db)
    
    st.divider()

    # --- SECTION D: CUSTOMER RECOVERY LIST ---
    st.header("📋 Customer Recovery List")
    
    recovery_df = db.get_customer_recovery_list()
    
    if not recovery_df.empty:
        # 1. Summaries (Dynamic Categories)
        
        # Identify Category Columns (end with _count)
        cat_cols = [c for c in recovery_df.columns if c.endswith('_count') and c != 'other_count']
        
        # Add 'other_count' at the end if it exists
        if 'other_count' in recovery_df.columns:
            cat_cols.append('other_count')
            
        st.subheader("📊 Sold Items Summary (All Customers)")
        
        # Create dynamic columns for cards
        if cat_cols:
            cols = st.columns(min(len(cat_cols), 6)) # Max 6 columns per row
            
            for idx, col_name in enumerate(cat_cols):
                # Calculate total
                total_val = recovery_df[col_name].sum()
                # Label: "inverter_count" -> "Inverters"
                label = col_name.replace('_count', 's').title()
                
                col_idx = idx % 6
                with cols[col_idx]:
                     st.metric(label=f"Total {label}", value=int(total_val))
        else:
            st.info("No categorical sales data available yet.")

        st.markdown("---")

        # 2. Detailed Table and Export
        grand_outstanding = recovery_df['net_outstanding'].sum()
        
        # Configure Static Columns
        column_cfg = {
            "name": st.column_config.TextColumn("Customer Name", width="medium"),
            "city": st.column_config.TextColumn("City", width="small"),
            "phone": st.column_config.TextColumn("Phone", width="small"),
            "total_sales": st.column_config.NumberColumn("Sales", format="Rs. %.0f"),
            "total_paid": st.column_config.NumberColumn("Paid", format="Rs. %.0f"),
            "opening_balance": st.column_config.NumberColumn("Op. Bal", format="Rs. %.0f"),
            "net_outstanding": st.column_config.NumberColumn("Net Outstanding", format="Rs. %.0f"),
            "other_count": st.column_config.NumberColumn("Other", format="%d"),
        }
        
        # Add Dynamic Configs for Categories
        for c in cat_cols:
             if c != 'other_count':
                 label = c.replace('_count', '').title()
                 column_cfg[c] = st.column_config.NumberColumn(label, format="%d", width="small")

        # Select Columns to Display
        # Ensure we only select columns that actually exist
        base_cols = ['name', 'city', 'phone']
        financial_cols = ['total_sales', 'total_paid', 'opening_balance', 'net_outstanding']
        
        display_cols = base_cols + cat_cols + financial_cols
        # Filter to ensure existence (just in case)
        display_cols = [c for c in display_cols if c in recovery_df.columns]

        st.dataframe(
            recovery_df[display_cols],
            use_container_width=True,
            column_config=column_cfg,
            hide_index=True,
            height=500
        )
        
        st.markdown(f"""<div style="text-align:right; font-size:1.5rem; font-weight:bold; margin-top:15px; padding:20px; border:2px solid #7aa2f7; border-radius:10px;">Overall Total Outstanding: <span style="color:#7aa2f7">Rs. {grand_outstanding:,.2f}</span></div>""", unsafe_allow_html=True)
        
        # Export Button
        # We need to ensure create_recovery_list_pdf can handle dynamic columns or we might need to update it too.
        # For now, let's keep it simple or check if it needs update. 
        # Checking db.create_recovery_list_pdf... assuming logic inside it is robust or we'll fix it next.
        
        # Export Button
        # Correctly calling the standalone function
        try:
            pdf_bytes = create_recovery_list_pdf(recovery_df, grand_outstanding)
            
            c_d1, c_d2 = st.columns([1, 1])
            with c_d1:
                st.download_button(
                     label="⬇️ Download Recovery List (PDF)",
                     data=pdf_bytes,
                     file_name=f"Customer_Recovery_{datetime.now().strftime('%Y-%m-%d')}.pdf",
                     mime="application/pdf",
                     type="primary"
                )
        except Exception as e:
            st.error(f"Error generating PDF: {e}")
            
        # --- DELETE OPTION ---
        st.markdown("---")
        with st.expander("🗑️ Manage / Delete Customer Data", expanded=False):
            st.warning("⚠️ Deleting a customer here will remove them from the **Directory**, **Ledger**, and **Sales History**. This action cannot be undone.")
            
            # List of names in the recovery list
            del_options = ["Select Customer..."] + list(recovery_df['name'].unique())
            
            del_target = st.selectbox("Select Customer to Delete", options=del_options)
            
            if del_target and del_target != "Select Customer...":
                # Clean name if it has " (Deleted)" or " ❌" marker
                real_name = del_target.replace(" ❌", "").replace(" (Deleted)", "")
                
                if st.button(f"🗑️ Permanently Delete '{real_name}'", type="primary"):
                    db.delete_customer_full_data(real_name)
                    st.success(f"Deleted data for {real_name}.")
                    time.sleep(1)
                    st.rerun()

    else:
        st.info("No customer data available.")

    st.divider()

    # --- SECTION E: STRATEGIC INSIGHTS ---
    st.subheader("💡 Strategic Insights")
    
    # NEW: FINANCIAL HEALTH (Expenses & Sales Trend)
    f_col1, f_col2 = st.columns(2)
    
    # 1. Expense Breakdown (Pie)
    with f_col1:
         st.markdown("#### 💸 Expense Breakdown (This Month)")
         exp_breakdown = db.get_monthly_expenses_breakdown()
         if not exp_breakdown.empty:
             fig_exp = px.pie(
                 exp_breakdown, 
                 values='amount', 
                 names='category', 
                 hole=0.5,
                 color_discrete_sequence=px.colors.qualitative.Pastel
             )
             fig_exp.update_layout(height=300, margin=dict(t=0, b=0, l=0, r=0))
             st.plotly_chart(fig_exp, use_container_width=True)
         else:
             st.caption("No expenses recorded this month.")
             
    # 2. Sales Trend (Line)
    with f_col2:
         st.markdown("#### 📈 Sales Trend (Last 30 Days)")
         sales_trend = db.get_sales_trend()
         if not sales_trend.empty:
              fig_trend = px.line(
                  sales_trend,
                  x='sale_date',
                  y='total_amount',
                  markers=True,
                  line_shape='spline',
              )
              fig_trend.update_traces(line_color='#7aa2f7', line_width=3)
              fig_trend.update_layout(height=300, margin=dict(t=0, b=0, l=0, r=0), xaxis_title="", yaxis_title="")
              st.plotly_chart(fig_trend, use_container_width=True)
         else:
              st.caption("No sales data found.")

    st.divider()
    
    history_df = db.get_job_history()
    
    if not history_df.empty:
        col_bi1, col_bi2 = st.columns(2)
        
        # 3. Inventory Intelligence
        with col_bi1:
            st.markdown("#### 🔥 Top Selling Parts")
            all_parts = []
            for raw_parts in history_df['used_parts']:
                if raw_parts and len(raw_parts) > 2:
                    try:
                        clean = raw_parts.replace("[","").replace("]","").replace("'","").replace('"',"")
                        if clean:
                            parts = [p.strip() for p in clean.split(',')]
                            all_parts.extend(parts)
                    except: pass
            
            if all_parts:
                part_counts = pd.Series(all_parts).value_counts().reset_index()
                part_counts.columns = ['Part Name', 'Qty Sold']
                top_parts = part_counts.head(10)
                
                fig_inv = px.bar(
                    top_parts, 
                    x='Qty Sold', 
                    y='Part Name', 
                    orientation='h',
                    title="",
                    color='Qty Sold',
                    color_continuous_scale='Magma'
                )
                fig_inv.update_layout(height=300, margin=dict(t=0, b=0), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig_inv, use_container_width=True)
            else:
                st.info("No parts data found in history.")

        # 4. Repair Profitability Matrix
        with col_bi2:
            st.markdown("#### 💎 Profitability Matrix")
            matrix = history_df.groupby('inverter_model').agg(
                Volume=('id', 'count'),
                Avg_Profit=('service_cost', 'mean'),
                Total_Revenue=('total_cost', 'sum')
            ).reset_index()
            
            if not matrix.empty:
                mean_vol = matrix['Volume'].mean()
                mean_prof = matrix['Avg_Profit'].mean()
                
                fig_mat = px.scatter(
                    matrix,
                    x='Volume',
                    y='Avg_Profit',
                    size='Total_Revenue',
                    color='inverter_model',
                    hover_name='inverter_model',
                    title="",
                    labels={'Volume': 'Number of Repairs', 'Avg_Profit': 'Avg Service Fee'}
                )
                fig_mat.add_hline(y=mean_prof, line_dash="dash", line_color="white", annotation_text="Avg Profit")
                fig_mat.add_vline(x=mean_vol, line_dash="dash", line_color="white", annotation_text="Avg Vol")
                fig_mat.update_layout(showlegend=False, height=300, margin=dict(t=0, b=0), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig_mat, use_container_width=True)


# --- TAB: CLIENT DIRECTORY ---
# --- TAB: PARTNERS & LEDGER ---
elif menu == "👥 Partners & Ledger":
    st.title("👥 Partners & Ledger")
    
    # State management for view
    if 'ledger_view_party' not in st.session_state:
        st.session_state.ledger_view_party = None

    # Logic to handle "Back to Directory"
    if st.session_state.ledger_view_party:
        # SHOW LEDGER VIEW
        current_party = st.session_state.ledger_view_party
        
        col_back, col_title = st.columns([1, 5])
        if col_back.button("⬅ Back to Directory"):
            st.session_state.ledger_view_party = None
            st.rerun()
        
        col_title.subheader(f"History: {current_party}")
        
        # Add Entry Form
        with st.expander("➕ Add Transaction", expanded=False):
             # Callback to handle transaction addition safely
             def add_transaction_callback():
                  d_val = st.session_state.get(f"d_{current_party}")
                  desc_val = st.session_state.get(f"desc_{current_party}", "")
                  
                  # Inputs
                  # Inputs
                  
                  # TOGGLE FOR STOCK ITEM
                  is_stock = st.checkbox("📦 Select from Inventory?", key=f"is_stock_{current_party}")
                  
                  # Load Inventory if needed
                  stock_item_id = None
                  stock_item_name = None
                  
                  if is_stock:
                      inv_df = db.get_inventory()
                      stock_opts = {}
                      if not inv_df.empty:
                          for _, r in inv_df.iterrows():
                              lbl = f"{r['item_name']} (Stock: {r['quantity']}) - Rs. {r['selling_price']}"
                              stock_opts[lbl] = r
                      
                      sel_stock = st.selectbox("Select Item", options=["Choose..."] + list(stock_opts.keys()), key=f"sel_stock_{current_party}")
                      
                      if sel_stock and sel_stock != "Choose...":
                          s_data = stock_opts[sel_stock]
                          stock_item_id = s_data['id']
                          stock_item_name = s_data['item_name']
                          
                          # Auto-Populate Rate if it's 0 (First selection)
                          # We use session state injection for Rate
                          if st.session_state.get(f"r_{current_party}", 0) == 0:
                               st.session_state[f"r_{current_party}"] = float(s_data['selling_price'])
                               st.rerun()

                  q_curr = st.session_state.get(f"q_{current_party}", 0)
                  r_curr = st.session_state.get(f"r_{current_party}", 0.0)
                  disc_curr = st.session_state.get(f"disc_{current_party}", 0.0)
                  bill_amt = st.session_state.get(f"bill_{current_party}", 0.0)
                  cash_amt = st.session_state.get(f"cash_{current_party}", 0.0)
                  
                  entries_added = 0
                  
                  # 1. Process BILL (Debit)
                  if bill_amt > 0:
                      bill_desc = desc_val if desc_val else "Bill"
                      
                      # Special Handling for Stock Sale
                      if is_stock and stock_item_id:
                          # Use new robust method
                          # Override description if empty
                          if not desc_val: bill_desc = f"Sale: {stock_item_name}"
                          
                          db.record_ledger_sale(current_party, d_val, stock_item_id, stock_item_name, q_curr, r_curr, disc_curr, bill_amt)
                      else:
                          # Standard Ledger Entry
                          db.add_ledger_entry(current_party, bill_desc, bill_amt, 0.0, d_val, quantity=q_curr, rate=r_curr, discount=disc_curr)
                          
                      entries_added += 1
                      
                  # 2. Process CASH RECEIVED (Credit)
                  if cash_amt > 0:
                      cash_desc = "Cash Received"
                      # If both added, maybe clarify description
                      if bill_amt > 0 and desc_val:
                           cash_desc = f"Payment for: {desc_val}"
                      elif desc_val:
                           cash_desc = desc_val
                           
                      db.add_ledger_entry(current_party, cash_desc, 0.0, cash_amt, d_val, quantity=0, rate=0.0, discount=0.0)
                      entries_added += 1
                  
                  if entries_added > 0:
                      st.session_state['tx_msg'] = ('success', "Transaction Recorded Successfully!")
                      # Reset Inputs
                      st.session_state[f"q_{current_party}"] = 0
                      st.session_state[f"r_{current_party}"] = 0.0
                      st.session_state[f"disc_{current_party}"] = 0.0
                      st.session_state[f"bill_{current_party}"] = 0.0
                      st.session_state[f"cash_{current_party}"] = 0.0
                      st.session_state[f"desc_{current_party}"] = ""
                      # Reset Stock Toggle if desired? Maybe keep it.
                      # st.session_state[f"is_stock_{current_party}"] = False 
                  else:
                      st.session_state['tx_msg'] = ('error', "Please enter a Bill Amount or Cash Received.")

             # Helper for auto-calculation
             def update_calc():
                 q = st.session_state.get(f"q_{current_party}", 0)
                 r = st.session_state.get(f"r_{current_party}", 0.0)
                 disc = st.session_state.get(f"disc_{current_party}", 0.0)
                 # Only update bill if q or r are positive
                 if q > 0 or r > 0:
                     st.session_state[f"bill_{current_party}"] = max(0.0, (q * r) - disc)

             # 1. Row 1: Qty & Rate & Discount
             c1, c2, c3 = st.columns(3)
             c1.number_input("Quantity (Optional)", min_value=0, step=1, key=f"q_{current_party}", on_change=update_calc)
             c2.number_input("Rate / Price per Item", min_value=0.0, step=10.0, key=f"r_{current_party}", on_change=update_calc)
             c3.number_input("Discount", min_value=0.0, step=10.0, key=f"disc_{current_party}", on_change=update_calc)
             
             # 2. Row 2: Bill & Cash
             c4, c5 = st.columns(2)
             c4.number_input("Values for Total Bill (Debit)", min_value=0.0, step=100.0, key=f"bill_{current_party}")
             c5.number_input("Cash Received (Credit)", min_value=0.0, step=100.0, key=f"cash_{current_party}")

             # 3. Row 3: Meta
             c6, c7 = st.columns([1, 2])
             c6.date_input("Date", key=f"d_{current_party}")
             c7.text_input("Description (e.g. Item Name)", key=f"desc_{current_party}")
             
             st.button("Save Transaction", type="primary", on_click=add_transaction_callback)

             # Display Message from callback
             if 'tx_msg' in st.session_state:
                 msg_type, msg_text = st.session_state.pop('tx_msg')
                 if msg_type == 'success':
                     st.success(msg_text)
                 else:
                     st.error(msg_text)

        # Table
        ledger_df = db.get_ledger_entries(current_party)
        
        if not ledger_df.empty:
            ledger_df['Balance'] = (ledger_df['debit'].cumsum() - ledger_df['credit'].cumsum())
            
            # Ensure ID is present for view
            if 'id' not in ledger_df.columns:
                 ledger_df['id'] = range(len(ledger_df)) # Fallback
            
            # Update View Columns
            display_df = ledger_df[['id', 'date', 'description', 'quantity', 'rate', 'discount', 'debit', 'credit', 'Balance']].copy()
            
            st.dataframe(display_df, use_container_width=True, height=400, 
                         column_config={
                             "id": st.column_config.TextColumn("ID", width="small"),
                             "quantity": st.column_config.NumberColumn("Qty", format="%d"),
                             "rate": st.column_config.NumberColumn("Price", format="Rs. %.0f"),
                             "discount": st.column_config.NumberColumn("Discount", format="Rs. %.0f"),
                             "debit": st.column_config.NumberColumn("Total Bill (Debit)", format="Rs. %.0f"),
                             "credit": st.column_config.NumberColumn("Cash Recieved (Credit)", format="Rs. %.0f"),
                             "Balance": st.column_config.NumberColumn("Outstanding Balance", format="Rs. %.0f"),
                         })
            
            # Delete Section
            with st.expander("🗑️ Manage / Delete Entries"):
                del_id = st.number_input("Enter Transaction ID to Delete", min_value=1, step=1, key=f"del_led_{current_party}")
                if st.button("Delete Transaction", type="primary"):
                     db.delete_ledger_entry(del_id)
                     st.success(f"Deleted Transaction ID {del_id}")
                     time.sleep(1)
                     st.rerun()
            
            final_bal = ledger_df.iloc[-1]['Balance']
            curr_color = "#f7768e" if final_bal > 0 else "#9ece6a" 
            
            st.markdown(f"""<div style="padding:20px; border-radius:10px; background-color:#1a1c24; border:1px solid {curr_color}; text-align:right;"><div class="sub-text">Total Pending Balance</div><div style="font-size:2.5rem; font-weight:bold; color:{curr_color}">Rs. {final_bal:,.2f}</div></div>""", unsafe_allow_html=True)
            
            st.write("")
            if st.button("🖨️ Download Statement (PDF)"):
                 pdf_data = create_ledger_pdf(current_party, ledger_df, final_bal)
                 st.download_button("📥 Click to Download PDF", data=pdf_data, file_name=f"Ledger_{current_party}.pdf", mime="application/pdf")

        else:
            st.info("No transactions found for this party.")
            
    else:
        # SHOW DIRECTORY VIEW
        
        # 1. Top Bar: Search, Add, General Ledger
        col_search, col_add, col_gen = st.columns([3, 1, 1])
        with col_search:
            search_client = st.text_input("🔍 Search Clients", placeholder="Name, City, or ID...")
        with col_add:
            if st.button("➕ Create Client", type="primary", use_container_width=True):
                add_client_dialog()
        with col_gen:
             if st.button("📜 General Ledger", use_container_width=True):
                 st.session_state['show_ledger_picker'] = not st.session_state.get('show_ledger_picker', False)

        if st.session_state.get('show_ledger_picker', False):
             all_parties = db.get_all_ledger_parties()
             sel_party = st.selectbox("Select Account to Open", all_parties, index=None, placeholder="Choose account...")
             if sel_party:
                 st.session_state.ledger_view_party = sel_party
                 st.session_state['show_ledger_picker'] = False
                 st.rerun()

        # 2. Fetch Data
        clients = db.get_customer_balances()
        
        if not clients.empty:
            # Filter
            if search_client:
                match = clients.astype(str).apply(lambda x: x.str.contains(search_client, case=False)).any(axis=1)
                clients = clients[match]
                
            # 3. Grid View
            c_cols = st.columns(3)
            for idx, row in clients.iterrows():
                with c_cols[idx % 3]:
                    # Balance Logic
                    bal = row['net_outstanding']
                    if bal > 0:
                        bal_text = f"🔴 Pending: Rs. {bal:,.0f}"
                        bal_color = "#f7768e" # Red
                    elif bal < 0:
                        bal_text = f"🟢 Advance: Rs. {abs(bal):,.0f}"
                        bal_color = "#9ece6a" # Green
                    else:
                        bal_text = "⚪ Cleared"
                        bal_color = "#a9b1d6" # Grey
                        
                    st.markdown(f"""<div class="modern-card"><div style="display:flex; justify-content:space-between;"><span class="sub-text">{row['customer_id']}</span><span class="sub-text">📍 {row['city']}</span></div><div class="big-text" style="margin-top:5px;">{row['name']}</div><div style="font-size:1.1rem; font-weight:bold; color:{bal_color}; margin-top:10px; margin-bottom:10px;">{bal_text}</div><div class="sub-text">📞 {row['phone']}</div></div>""", unsafe_allow_html=True)
                    
                    b1, b2 = st.columns(2)
                    if b1.button(f"📜 View Ledger", key=f"view_leg_{row['customer_id']}", use_container_width=True):
                        st.session_state.ledger_view_party = row['name']
                        st.rerun()

                    if b2.button(f"🗑️ Delete", key=f"del_client_{row['customer_id']}", use_container_width=True):
                         st.session_state[f"confirm_del_{row['customer_id']}"] = True
                         st.rerun()
                    
                    if st.session_state.get(f"confirm_del_{row['customer_id']}", False):
                        st.warning("Are you sure? This will delete the client profile.")
                        col_conf1, col_conf2 = st.columns(2)
                        if col_conf1.button("✅ Yes, Delete", key=f"yes_del_{row['customer_id']}", type="primary"):
                             db.delete_customer(row['customer_id'])
                             st.success(f"Client {row['name']} deleted!")
                             st.session_state[f"confirm_del_{row['customer_id']}"] = False
                             time.sleep(1)
                             st.rerun()
                        
                        if col_conf2.button("❌ Cancel", key=f"no_del_{row['customer_id']}"):
                             st.session_state[f"confirm_del_{row['customer_id']}"] = False
                             st.rerun()
        else:
            st.info("No clients found. Add your first client!")

# --- TAB: STAFF & PAYROLL ---
elif menu == "👷 Staff & Payroll":
    st.title("👷 Staff & Payroll")
    
    # State management for ledger view
    if 'ledger_view_employee' not in st.session_state:
        st.session_state.ledger_view_employee = None

    # Logic to handle "Back to Employee List"
    if st.session_state.ledger_view_employee:
        # SHOW FULL-PAGE EMPLOYEE LEDGER VIEW
        current_employee = st.session_state.ledger_view_employee
        
        col_back, col_title = st.columns([1, 5])
        if col_back.button("⬅ Back to Employee List"):
            st.session_state.ledger_view_employee = None
            st.rerun()
        
        col_title.subheader(f"History: {current_employee}")
        
        # Add Transaction Form
        with st.expander("➕ Add Transaction", expanded=False):
            dc1, dc2, dc3, dc4 = st.columns([1, 2, 2, 1.5])
            t_date = dc1.date_input("Date", key=f"emp_led_date_{current_employee}")
            t_desc = dc2.text_input("Description", "Work Log", key=f"emp_led_desc_{current_employee}")
            t_type = dc3.radio("Type", ["Earned (Work/Fixed)", "Paid (Payment)"], horizontal=True, key=f"emp_led_type_{current_employee}")
            t_amount = dc4.number_input("Amount", min_value=0.0, step=100.0, key=f"emp_led_amt_{current_employee}")
            
            if st.button("Add Entry", type="primary", key=f"emp_led_add_{current_employee}"):
                if t_amount > 0:
                    earned = t_amount if "Earned" in t_type else 0.0
                    paid = t_amount if "Paid" in t_type else 0.0
                    entry_type = "Work Log" if "Earned" in t_type else "Salary Payment"
                    
                    db.add_employee_ledger_entry(current_employee, t_date, entry_type, t_desc, earned, paid)
                    st.success("Entry Added!")
                    st.rerun()
                else:
                    st.error("Amount must be greater than 0")

        # Table
        ledger_df = db.get_employee_ledger(current_employee)
        
        if not ledger_df.empty:
            # Calculate Running Balance
            ledger_df_asc = ledger_df.sort_values(by=['date', 'id'], ascending=True)
            ledger_df_asc['Balance'] = (ledger_df_asc['earned'] - ledger_df_asc['paid']).cumsum()
            
            # Display in descending order
            display_df = ledger_df_asc.sort_values(by=['date', 'id'], ascending=False)[['id', 'date', 'type', 'description', 'earned', 'paid', 'Balance']].copy()
            
            st.dataframe(display_df, use_container_width=True, height=400, 
                         column_config={
                             "id": st.column_config.TextColumn("ID", width="small"),
                             "date": "Date",
                             "type": "Type",
                             "description": "Description",
                             "earned": st.column_config.NumberColumn("Earned", format="Rs. %.0f"),
                             "paid": st.column_config.NumberColumn("Paid", format="Rs. %.0f"),
                             "Balance": st.column_config.NumberColumn("Balance", format="Rs. %.0f"),
                         })
            
            # Delete Section
            with st.expander("🗑️ Manage / Delete Entries"):
                del_id = st.number_input("Enter Transaction ID to Delete", min_value=1, step=1, key=f"del_emp_led_{current_employee}")
                if st.button("Delete Transaction", type="primary", key=f"del_emp_led_btn_{current_employee}"):
                     db.delete_employee_ledger_entry(del_id)
                     st.success(f"Deleted Transaction ID {del_id}")
                     time.sleep(1)
                     st.rerun()
            
            # Balance Display
            final_bal = ledger_df_asc.iloc[-1]['Balance']
            
            if final_bal > 0:
                balance_color = "#9ece6a"  # Green
                balance_icon = "🟢"
                balance_label = "Payable Salary"
            elif final_bal < 0:
                balance_color = "#f7768e"  # Red
                balance_icon = "🔴"
                balance_label = "Outstanding Advance"
            else:
                balance_color = "#7aa2f7"  # Blue
                balance_icon = "⚪"
                balance_label = "Settled"
            
            st.markdown(f"""<div style="padding:20px; border-radius:10px; background-color:#1a1c24; border:2px solid {balance_color}; text-align:center; margin-top:20px;"><div style="font-size:0.9rem; color:#a9b1d6; margin-bottom:5px;">{balance_icon} {balance_label}</div><div style="font-size:2.5rem; font-weight:bold; color:{balance_color}">Rs. {abs(final_bal):,.2f}</div></div>""", unsafe_allow_html=True)
            
            # PDF Download
            st.write("")
            if st.button("🖨️ Download Statement (PDF)", use_container_width=True, key=f"emp_led_pdf_{current_employee}"):
                pdf_data = create_employee_payroll_pdf(current_employee, ledger_df, final_bal)
                st.download_button(
                    "📥 Click to Download PDF", 
                    data=pdf_data, 
                    file_name=f"Payroll_{current_employee}.pdf", 
                    mime="application/pdf",
                    use_container_width=True
                )

        else:
            st.info("No transactions recorded yet. Start by adding entries above.")
    
    else:
        # SHOW EMPLOYEE LIST VIEW
        # Add Employee (Collapsible)
        with st.expander("➕ Register New Employee"):
            with st.form("new_emp"):
                c1, c2 = st.columns(2)
                name = c1.text_input("Full Name")
                role = c2.selectbox("Role", ["Technician", "Manager"])
                
                c3, c4 = st.columns(2)
                phone = c3.text_input("Phone Number")
                cnic = c4.text_input("CNIC / Passport Number")
                
                if st.form_submit_button("Save Employee"):
                    if name:
                        db.add_employee(name, role, phone, 0, cnic)
                        st.success("Employee Added!")
                        st.rerun()
                    else:
                        st.error("Name is required.")

        emp = db.get_all_employees()
        if not emp.empty:
            # SEARCH STAFF
            search_emp = st.text_input("🔍 Search Staff", placeholder="Name or Role...")
            if search_emp:
                 emp = emp[emp.astype(str).apply(lambda x: x.str.contains(search_emp, case=False)).any(axis=1)]

            # Optimization: Fetch stats once
            workload_df = db.get_employee_workload()
            perf_df = db.get_employee_performance()
            
            e_cols = st.columns(3)
            for idx, row in emp.iterrows():
                with e_cols[idx % 3]:
                    # Workload Logic
                    active_jobs = 0
                    if not workload_df.empty and row['name'] in workload_df['assigned_to'].values:
                        active_jobs = workload_df[workload_df['assigned_to'] == row['name']].iloc[0]['active_jobs']
                    
                    # Completed Logic
                    completed_jobs = 0
                    if not perf_df.empty and row['name'] in perf_df['assigned_to'].values:
                        completed_jobs = perf_df[perf_df['assigned_to'] == row['name']].iloc[0]['total_completed']
                    
                    load_badge = ""
                    if active_jobs > 5:
                        load_badge = f"<span style='background:#f7768e; color:white; padding:2px 6px; border-radius:4px; font-size:0.7rem; font-weight:bold; margin-left:5px;'>🔥 High Load</span>"
                    
                    st.markdown(f"""<div class="modern-card" style="text-align:center;"><div style="font-size:3rem; margin-bottom:10px;">👤</div><div class="big-text">{row['name']} {load_badge}</div><div class="sub-text" style="color:#7aa2f7; text-transform:uppercase; letter-spacing:1px;">{row['role']}</div><div style="margin-top:10px; font-weight:bold;">⚡ Active Jobs: {active_jobs}</div><div style="margin-bottom:10px; font-weight:bold; color:#9ece6a;">✅ Completed: {completed_jobs}</div><hr style="border-color:#2c2f3f;"><div style="font-size:0.8rem; color:#a9b1d6;">ID: {row['id']} • Active</div></div>""", unsafe_allow_html=True)
                    
                    # ACTION BUTTONS
                    btn_col1, btn_col2, btn_col3 = st.columns(3)
                    with btn_col1:
                        if st.button(f"View Data", key=f"emp_btn_{row['id']}", use_container_width=True):
                            # Robust field access with fallback
                            p = row['phone'] if 'phone' in row else ''
                            c = row['cnic'] if 'cnic' in row else ''
                            employee_dialog(row['id'], row['name'], row['role'], p, c)
                    
                    with btn_col2:
                        if st.button(f"💰 Wallet", key=f"emp_wallet_{row['id']}", use_container_width=True):
                            st.session_state['active_payroll_emp'] = {'id': row['id'], 'name': row['name']}
                            st.rerun()
                    
                    with btn_col3:
                        if st.button(f"📜 Ledger", key=f"emp_ledger_{row['id']}", use_container_width=True):
                            st.session_state.ledger_view_employee = row['name']
                            # Clear payroll dialog state to prevent it from auto-opening
                            if 'active_payroll_emp' in st.session_state:
                                del st.session_state['active_payroll_emp']
                            st.rerun()

            # Handle Active Payroll Dialog (Outside the loop)
            if 'active_payroll_emp' in st.session_state and st.session_state['active_payroll_emp']:
                 emp_data = st.session_state['active_payroll_emp']
                 try:
                     employee_payroll_dialog(emp_data['id'], emp_data['name'])
                 except Exception:
                     # If dialog closes or error, clear state
                     del st.session_state['active_payroll_emp']
                     st.rerun()

