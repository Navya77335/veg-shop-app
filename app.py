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
OWNER_PASS = "Mani@2"
INVENTORY_FILE = "inventory.json"
CUSTOMERS_FILE = "customers.json"

# ----------------- Helpers -----------------
def safe_load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if data else default
        except Exception:
            return default
    return default

def save_json(path, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception:
        pass

def parse_qty(qty):
    if isinstance(qty, (int, float)):
        return float(qty), ""
    qty_str = str(qty).strip().lower().replace(" ", "")
    num, unit = "", ""
    for c in qty_str:
        if c.isdigit() or c == ".":
            num += c
        else:
            unit += c
    try:
        num = float(num)
    except:
        num = 0
    if unit == "kg":
        num *= 1000
        unit = "g"
    return num, unit

def format_qty(num, unit):
    if unit == "g" and num >= 1000:
        return f"{num/1000:.2f} kg"
    return f"{num:.0f} {unit}".strip()

def row_total(qty_num, unit, price):
    if unit == "g":
        return (qty_num / 1000.0) * price
    return qty_num * price

def generate_pdf_receipt_bytes(phone, items, grand_total):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    elements = []
    elements.append(Paragraph("<b>Vegetable Shop Receipt</b>", styles["Title"]))
    elements.append(Spacer(1, 12))
    elements.append(Paragraph(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles["Normal"]))
    elements.append(Paragraph(f"Customer Phone: {phone}", styles["Normal"]))
    elements.append(Spacer(1, 12))
    data = [["Item", "Quantity", "Unit Price", "Total"]]
    for item in items:
        qn, qu = parse_qty(item["qty"])
        total = row_total(qn, qu, item["price"])
        label = f"₹{item['price']}/kg" if qu == "g" else f"₹{item['price']}/pc"
        data.append([item["name"], item["qty"], label, f"₹{total:.2f}"])
    data.append(["", "", "Grand Total", f"₹{grand_total:.2f}"])
    table = Table(data, colWidths=[180, 120, 120, 100])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.lightblue),
        ("TEXTCOLOR", (0,0), (-1,0), colors.black),
        ("ALIGN", (0,0), (-1,-1), "CENTER"),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("GRID", (0,0), (-1,-1), 1, colors.black),
    ]))
    elements.append(table)
    doc.build(elements)
    buffer.seek(0)
    return buffer.read()

def remove_duplicates(items):
    seen = {}
    for item in items:
        seen[item["name"]] = item
    return list(seen.values())

def to_base_unit(num, unit):
    if unit == "kg":
        return num * 1000, "g"
    return num, unit

def subtract_stock(item_qty, sale_qty):
    sn, su = parse_qty(item_qty)
    qn, qu = parse_qty(sale_qty)
    sn, su = to_base_unit(sn, su)
    qn, qu = to_base_unit(qn, qu)
    if su == qu:
        remaining = max(sn - qn, 0)
        return format_qty(remaining, su)
    return item_qty

# ----------------- Defaults -----------------
default_inventory = [
    {"name": "Brinjal", "qty": "15 kg", "price": 20, "cost": 12},
    {"name": "Onion", "qty": "10 kg", "price": 30, "cost": 18},
    {"name": "Tomato", "qty": "17 kg", "price": 25, "cost": 15},
    {"name": "Lady Fingers", "qty": "18 kg", "price": 22, "cost": 14},
    {"name": "Beans", "qty": "15 kg", "price": 28, "cost": 20},
    {"name": "Cauliflower", "qty": "8 pcs", "price": 35, "cost": 25},
]

# ----------------- Session State -----------------
if "inventory" not in st.session_state:
    st.session_state.inventory = remove_duplicates(safe_load_json(INVENTORY_FILE, default_inventory))
if "customers" not in st.session_state:
    st.session_state.customers = safe_load_json(CUSTOMERS_FILE, [])
if "cart" not in st.session_state:
    st.session_state.cart = []
if "owner_logged_in" not in st.session_state:
    st.session_state.owner_logged_in = False

# ----------------- UI -----------------
st.title("🛒 Vegetable Shop (Web)")
st.caption("Customer view + Owner controls. Supports kg, g, pcs, liters.")

# Inventory display
st.subheader("Inventory")
avail_map = {it["name"]: parse_qty(it["qty"]) for it in st.session_state.inventory}
rows = []
for item in st.session_state.inventory:
    qn, qu = avail_map[item["name"]]
    rows.append({
        "Name": item["name"],
        "Available": format_qty(qn, qu),
        "Price": f"₹{item['price']}/kg" if qu == "g" else f"₹{item['price']}/pc"
    })
st.dataframe(rows, use_container_width=True, hide_index=True)

# Add to Cart
st.subheader("Add to Cart")
item_names = [i["name"] for i in st.session_state.inventory]
col1, col2, col3, col4 = st.columns([2, 1.5, 1.5, 1])
with col1:
    name = st.selectbox("Item", item_names)
with col2:
    qty_num = st.number_input("Quantity", min_value=0.1, step=0.1)
with col3:
    unit = st.selectbox("Unit", ["kg", "g", "pcs", "liters"])
with col4:
    if st.button("Add"):
        stock = next(i for i in st.session_state.inventory if i["name"] == name)
        sn, su = parse_qty(stock["qty"])
        sn, su = to_base_unit(sn, su)
        qn, qu = to_base_unit(qty_num, unit)
        if su != qu:
            st.error(f"Please use unit '{su}' for this item")
        elif qn > sn:
            st.error("Not enough stock")
        else:
            st.session_state.cart.append({"name": name, "qty": f"{qty_num} {unit}", "price": stock["price"]})
            st.success(f"Added {qty_num} {unit} of {name}")

# Cart
st.subheader("Cart")
if not st.session_state.cart:
    st.info("Cart is empty")
else:
    total = 0
    for idx, c in enumerate(st.session_state.cart):
        qn, qu = parse_qty(c["qty"])
        row = row_total(qn, qu, c["price"])
        total += row
        st.write(f"{idx+1}. {c['name']} - {c['qty']} (₹{row:.2f})")
    st.markdown(f"**Grand Total: ₹{total:.2f}**")

# Checkout
st.subheader("Checkout")
with st.form("checkout"):
    phone = st.text_input("Customer Phone")
    ok = st.form_submit_button("Generate Bill & Update Stock")
if ok:
    if not st.session_state.cart:
        st.error("Cart is empty")
    elif not (phone.isdigit() and len(phone)==10):
        st.error("Invalid phone")
    else:
        for c in st.session_state.cart:
            item = next(i for i in st.session_state.inventory if i["name"] == c["name"])
            item["qty"] = subtract_stock(item["qty"], c["qty"])
        grand = sum([row_total(*parse_qty(c["qty"]), c["price"]) for c in st.session_state.cart])
        order = {"time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "phone": phone,
                 "items": st.session_state.cart.copy(), "total": grand}
        st.session_state.customers.append(order)
        save_json(INVENTORY_FILE, st.session_state.inventory)
        save_json(CUSTOMERS_FILE, st.session_state.customers)
        pdf = generate_pdf_receipt_bytes(phone, st.session_state.cart, grand)
        st.download_button("⬇️ Download PDF Receipt", data=pdf,
                           file_name=f"receipt_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                           mime="application/pdf")
        st.session_state.cart = []
        st.success(f"Checkout complete. Total ₹{grand:.2f}")

# ----------------- Owner Login & Inventory Management -----------------
st.subheader("Owner Login")
if not st.session_state.owner_logged_in:
    user = st.text_input("Username")
    pw = st.text_input("Password", type="password")
    if st.button("Login"):
        if user == OWNER_USER and pw == OWNER_PASS:
            st.session_state.owner_logged_in = True
            st.success("Logged in successfully")
        else:
            st.error("Invalid credentials")
else:
    st.info(f"Welcome, {OWNER_USER}!")
    with st.expander("Manage Inventory"):
        # Add new item
        st.markdown("### Add Item")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            new_name = st.text_input("Name")
        with col2:
            new_qty = st.text_input("Quantity (e.g. 10 kg)")
        with col3:
            new_price = st.number_input("Price", min_value=0.0)
        with col4:
            new_cost = st.number_input("Cost", min_value=0.0)
        if st.button("Add Item"):
            st.session_state.inventory.append({"name": new_name, "qty": new_qty, "price": new_price, "cost": new_cost})
            save_json(INVENTORY_FILE, st.session_state.inventory)
            st.success("Item added successfully")
        
        # Update existing item
        st.markdown("### Update Item")
        upd_item = st.selectbox("Select item to update", [i["name"] for i in st.session_state.inventory])
        upd_qty = st.text_input("New Quantity (e.g. 5 kg)")
        upd_price = st.number_input("New Price", min_value=0.0, key="upd_price")
        upd_cost = st.number_input("New Cost", min_value=0.0, key="upd_cost")
        if st.button("Update Item"):
            for item in st.session_state.inventory:
                if item["name"] == upd_item:
                    if upd_qty:
                        item["qty"] = upd_qty
                    item["price"] = upd_price
                    item["cost"] = upd_cost
            save_json(INVENTORY_FILE, st.session_state.inventory)
            st.success("Item updated successfully")

        # Remove item
        st.markdown("### Remove Item")
        del_item = st.selectbox("Select item to remove", [i["name"] for i in st.session_state.inventory], key="del_item")
        if st.button("Remove Item"):
            st.session_state.inventory = [i for i in st.session_state.inventory if i["name"] != del_item]
            save_json(INVENTORY_FILE, st.session_state.inventory)
            st.success("Item removed successfully")

        # Logout
        if st.button("Logout"):
            st.session_state.owner_logged_in = False
            st.info("Logged out")
