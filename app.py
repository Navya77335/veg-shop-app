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

# ----------------- Defaults -----------------
def remove_duplicates(items):
    seen = {}
    for item in items:
        seen[item["name"]] = item
    return list(seen.values())

def to_base_unit(num, unit):
    """Converts kg/g to grams; liters/pcs stay as is."""
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

# Sidebar: Owner login
st.sidebar.subheader("Owner Login")
if not st.session_state.owner_logged_in:
    with st.sidebar.form("owner_login_form"):
        u = st.text_input("Username")
        p = st.text_input("Password", type="password")
        login = st.form_submit_button("Login")
    if login:
        if u == OWNER_USER and p == OWNER_PASS:
            st.session_state.owner_logged_in = True
            st.sidebar.success("Owner access granted!")
        else:
            st.sidebar.error("Incorrect credentials")
else:
    st.sidebar.success("Logged in as owner")
    if st.sidebar.button("Logout"):
        st.session_state.owner_logged_in = False


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
# Owner section
if st.session_state.owner_logged_in:
    st.divider()
    st.subheader("Owner: Manage Inventory")
    with st.form("add_item_form"):
        col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
        with col1: name = st.text_input("Item Name")
        with col2: qty = st.text_input("Quantity (e.g., 5 kg, 500 g, 3 pcs, 2 liters)")
        with col3: price = st.number_input("Selling Price", min_value=0, step=1, value=0)
        with col4: cost = st.number_input("Cost Price", min_value=0, step=1, value=0)
        add_btn = st.form_submit_button("Add Item")
    if add_btn and name and qty:
        qty_clean = qty.strip()
        existing = next((i for i in st.session_state.inventory if i["name"].lower() == name.lower()), None)
        if existing:
            old_qty_kg = parse_qty_to_kg(existing["qty"])
            new_qty_kg = parse_qty_to_kg(qty_clean)
            total_qty_kg = old_qty_kg + new_qty_kg
            if "pcs" in existing["qty"].lower():
                existing.update({"qty": f"{int(total_qty_kg)} pcs", "price": int(price), "cost": int(cost)})
            elif "liter" in existing["qty"].lower():
                existing.update({"qty": f"{total_qty_kg} liters", "price": int(price), "cost": int(cost)})
            else:
                existing.update({"qty": f"{total_qty_kg} kg", "price": int(price), "cost": int(cost)})
            st.success("Item updated (quantity added)")
        else:
            st.session_state.inventory.append({"name": name, "qty": qty_clean, "price": int(price), "cost": int(cost)})
            st.success("Item added")
        save_json(INVENTORY_FILE, remove_duplicates(st.session_state.inventory))

    st.markdown("### Update / Remove")
    names = [i["name"] for i in st.session_state.inventory]
    if names:
        sel = st.selectbox("Select Item", names, key="owner_select")
        item = next(i for i in st.session_state.inventory if i["name"] == sel)
        u_qty = st.text_input("New Quantity", value=item["qty"], key="owner_qty")
        u_price = st.number_input("New Price", value=int(item["price"]), step=1, key="owner_price")
        u_cost = st.number_input("New Cost", value=int(item.get("cost", 0)), step=1, key="owner_cost")
        cols = st.columns(2)
        if cols[0].button("Update", key="owner_update"):
            item.update({"qty": u_qty, "price": int(u_price), "cost": int(u_cost)})
            save_json(INVENTORY_FILE, remove_duplicates(st.session_state.inventory))
            st.success("Updated")
        if cols[1].button("Remove", key="owner_remove"):
            st.session_state.inventory = [i for i in st.session_state.inventory if i["name"] != sel]
            save_json(INVENTORY_FILE, st.session_state.inventory)
            st.success("Removed")



