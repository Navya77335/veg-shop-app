import streamlit as st
import json, os, io
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet

# ----------------- Config -----------------
st.set_page_config(page_title="Vegetable Shop", layout="wide")
OWNER_USER = "Sidhu"
OWNER_PASS = "Man"

# ----------------- File Paths -----------------
INVENTORY_FILE = "inventory.json"
CUSTOMERS_FILE = "customers.json"

# ----------------- Utility Functions -----------------
def load_json(file):
    if os.path.exists(file):
        with open(file, "r") as f:
            return json.load(f)
    return []

def save_json(file, data):
    with open(file, "w") as f:
        json.dump(data, f, indent=4)

def parse_qty(qty):
    qty = qty.strip()
    parts = qty.split()
    if len(parts) == 2:
        return float(parts[0]), parts[1]
    return 0, ""

def format_qty(num, unit):
    if unit == "g" and num >= 1000:
        return f"{num/1000:.2f} kg"
    return f"{num:.2f} {unit}"

def row_total(num, unit, price):
    if unit == "kg":
        return num * price
    elif unit == "g":
        return (num/1000) * price
    else:
        return num * price

def generate_pdf_receipt_bytes(phone, items, total):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    elements = [Paragraph(f"Receipt for {phone}", styles["Title"]), Spacer(1, 12)]

    table_data = [["Item", "Qty", "Price"]]
    for c in items:
        table_data.append([c["name"], c["qty"], f"₹{c['price']}"])
    table_data.append(["", "Total", f"₹{total:.2f}"])

    table = Table(table_data)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    elements.append(table)

    doc.build(elements)
    buffer.seek(0)
    return buffer

# ----------------- Main App -----------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if "inventory" not in st.session_state:
    st.session_state.inventory = load_json(INVENTORY_FILE)

if "customers" not in st.session_state:
    st.session_state.customers = load_json(CUSTOMERS_FILE)

if "cart" not in st.session_state:
    st.session_state.cart = []

if not st.session_state.logged_in:
    user = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        if user == OWNER_USER and password == OWNER_PASS:
            st.session_state.logged_in = True
            st.success("Login successful")
        else:
            st.error("Invalid credentials")
else:
    st.header("Vegetable Shop")
    tabs = st.tabs(["Inventory", "Cart", "Customers"])

    # Inventory Tab
    with tabs[0]:
        st.subheader("Current Inventory")
        for i, item in enumerate(st.session_state.inventory):
            st.write(f"{item['name']} - {item['qty']} @ ₹{item['price']} per unit")
            if st.button(f"Delete {item['name']}", key=f"del{i}"):
                st.session_state.inventory.pop(i)
                save_json(INVENTORY_FILE, st.session_state.inventory)
                st.experimental_rerun()

        name = st.text_input("New Item Name")
        qty = st.text_input("Quantity (e.g., 2 kg, 500 g, 5 pcs)")
        price = st.number_input("Price", min_value=0.0, step=0.5)
        if st.button("Add Item"):
            st.session_state.inventory.append({"name": name, "qty": qty, "price": price})
            save_json(INVENTORY_FILE, st.session_state.inventory)
            st.success("Item added")

    # Cart Tab
    with tabs[1]:
        st.subheader("Cart")
        for i, c in enumerate(st.session_state.cart):
            st.write(f"{c['name']} - {c['qty']} @ ₹{c['price']} per unit")
            if st.button(f"Remove {c['name']}", key=f"rm{i}"):
                st.session_state.cart.pop(i)

        item_names = [item["name"] for item in st.session_state.inventory]
        item_name = st.selectbox("Select Item", [""] + item_names)
        qty = st.text_input("Quantity (e.g., 2 kg, 500 g, 5 pcs)", key="cart_qty")
        if item_name and qty:
            item = next((i for i in st.session_state.inventory if i["name"] == item_name), None)
            if item:
                if st.button("Add to Cart"):
                    st.session_state.cart.append({"name": item_name, "qty": qty, "price": item["price"]})

        phone = st.text_input("Customer Phone (10 digits)")
        if st.button("Checkout"):
            if not st.session_state.cart:
                st.error("Cart is empty")
            elif not (phone.isdigit() and len(phone) == 10):
                st.error("Phone must be 10 digits")
            else:
                for c in st.session_state.cart:
                    item = next(i for i in st.session_state.inventory if i["name"] == c["name"])
                    stock_num, stock_unit = parse_qty(item["qty"])
                    buy_num, buy_unit = parse_qty(c["qty"])

                    if stock_unit == "g":
                        if buy_unit == "kg":
                            buy_num *= 1000
                        elif buy_unit == "g":
                            pass
                        else:
                            continue
                        new_qty = max(stock_num - buy_num, 0)
                        item["qty"] = format_qty(new_qty, "g")
                    elif stock_unit == "pcs":
                        if buy_unit != "pcs":
                            continue
                        new_qty = max(stock_num - buy_num, 0)
                        item["qty"] = f"{int(new_qty)} pcs"
                    elif stock_unit == "liters":
                        if buy_unit != "liters":
                            continue
                        new_qty = max(stock_num - buy_num, 0)
                        item["qty"] = f"{new_qty} liters"

                grand_total = sum([row_total(*parse_qty(c["qty"]), c["price"]) for c in st.session_state.cart])
                order = {
                    "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "phone": phone,
                    "items": st.session_state.cart.copy(),
                    "total": grand_total
                }
                st.session_state.customers.append(order)

                save_json(INVENTORY_FILE, st.session_state.inventory)
                save_json(CUSTOMERS_FILE, st.session_state.customers)

                pdf_bytes = generate_pdf_receipt_bytes(phone, st.session_state.cart, grand_total)
                st.download_button(
                    "⬇️ Download PDF Receipt",
                    data=pdf_bytes,
                    file_name=f"receipt_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                    mime="application/pdf"
                )

                st.session_state.cart = []
                st.success(f"Checkout complete. Total ₹{grand_total:.2f}")

    # Customers Tab
    with tabs[2]:
        st.subheader("Customer Orders")
        for c in st.session_state.customers:
            st.write(c)
