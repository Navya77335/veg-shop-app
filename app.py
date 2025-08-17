import tkinter as tk
from tkinter import messagebox, simpledialog

import streamlit as st
import json, os
from datetime import datetime
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

# ----------------- File paths -----------------
INVENTORY_FILE = "inventory.json"
CUSTOMERS_FILE = "customers.json"

# ----------------- Helpers -----------------
def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r") as f:
                return json.load(f)
        except:
            return default
    return default

def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

inventory = load_json(INVENTORY_FILE, {})
customers = load_json(CUSTOMERS_FILE, {})

# ----------------- Billing PDF -----------------
def generate_bill_pdf(customer, cart, total, discount, final_total):
    filename = f"Bill_{customer}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    doc = SimpleDocTemplate(filename, pagesize=A4)
    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph("<b>Veg Shop Bill</b>", styles["Title"]))
    elements.append(Spacer(1, 12))
    elements.append(Paragraph(f"Customer: {customer}", styles["Normal"]))
    elements.append(Paragraph(f"Date: {datetime.now().strftime('%d-%m-%Y %H:%M:%S')}", styles["Normal"]))
    elements.append(Spacer(1, 12))

    data = [["Item", "Qty", "Price", "Subtotal"]]
    for item, details in cart.items():
        data.append([item, str(details["qty"]), f"₹{details['price']}", f"₹{details['subtotal']}"])
    data.append(["", "", "Total", f"₹{total}"])
    data.append(["", "", "Discount", f"-₹{discount}"])
    data.append(["", "", "Final Total", f"₹{final_total}"])

    table = Table(data, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("GRID", (0,0), (-1,-1), 1, "black"),
        ("BACKGROUND", (0,0), (-1,0), "#d3d3d3"),
    ]))
    elements.append(table)
    doc.build(elements)
    return filename

# ----------------- UI -----------------
st.set_page_config(page_title="Veg Shop", page_icon="🥦", layout="wide")
st.title("🥦 Veg Shop Management")

menu = st.sidebar.radio("Navigation", ["Customer Mode", "Owner Mode"])

if menu == "Customer Mode":
    st.subheader("🛒 Customer Billing")
    name = st.text_input("Enter your name")
    if name:
        if name not in customers:
            customers[name] = []
        cart = {}
        for item, details in inventory.items():
            col1, col2 = st.columns([2,1])
            with col1:
                qty = st.number_input(f"{item} (₹{details['price']} per {details['unit']})", 0, 100, 0)
            if qty > 0:
                cart[item] = {
                    "qty": qty,
                    "price": details["price"],
                    "subtotal": qty * details["price"]
                }

        if cart:
            total = sum(c["subtotal"] for c in cart.values())
            discount = round(total * 0.05, 2) if total > 500 else 0
            final_total = total - discount

            st.write("### Cart Summary")
            st.json(cart)
            st.write(f"**Total:** ₹{total}")
            st.write(f"**Discount:** ₹{discount}")
            st.write(f"**Final Total:** ₹{final_total}")

            if st.button("Checkout"):
                customers[name].append({
                    "cart": cart,
                    "total": total,
                    "discount": discount,
                    "final_total": final_total,
                    "time": datetime.now().isoformat()
                })
                save_json(CUSTOMERS_FILE, customers)
                bill = generate_bill_pdf(name, cart, total, discount, final_total)
                with open(bill, "rb") as f:
                    st.download_button("Download Bill", f, file_name=bill)

elif menu == "Owner Mode":
    st.subheader("⚙️ Owner Panel")
    OWNER_USER = "admin"
    OWNER_PASS = "1234"
    user = st.text_input("Username")
    pwd = st.text_input("Password", type="password")
    if st.button("Login"):
        if user == OWNER_USER and pwd == OWNER_PASS:
            st.success("Logged in as Owner ✅")
            choice = st.radio("Options", ["View Inventory", "Add Item", "View Customers"])
            if choice == "View Inventory":
                st.json(inventory)
            elif choice == "Add Item":
                item = st.text_input("Item name")
                price = st.number_input("Price", 0.0)
                unit = st.selectbox("Unit", ["kg", "pcs"])
                if st.button("Save Item"):
                    if item:
                        inventory[item] = {"price": price, "unit": unit}
                        save_json(INVENTORY_FILE, inventory)
                        st.success(f"Item {item} added/updated.")
            elif choice == "View Customers":
                st.json(customers)
        else:
            st.error("Invalid credentials")
