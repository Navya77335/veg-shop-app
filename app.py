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

def parse_qty_to_kg(qty_str):
    qty_str = qty_str.strip().lower()
    parts = qty_str.split()
    if len(parts) == 2:
        num, unit = parts
        try:
            num = float(num)
        except:
            return 0
        if unit in ["kg", "kgs"]:
            return num
        elif unit == "g":
            return num / 1000
        elif unit in ["pcs", "liters"]:
            return num  # treat pcs and liters as count
    return 0

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
        unit_price_label = f"₹{item['price']}/kg" if qu == "g" else f"₹{item['price']}/pc"
        data.append([item["name"], item["qty"], unit_price_label, f"₹{total:.2f}"])
    data.append(["", "", "Grand Total", f"₹{grand_total:.2f}"])

    table = Table(data, colWidths=[180, 120, 120, 100])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.lightblue),
        ("TEXTCOLOR", (0,0), (-1,0), colors.black),
        ("ALIGN", (0,0), (-1,-1), "CENTER"),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("BOTTOMPADDING", (0,0), (-1,0), 12),
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
    loaded = safe_load_json(INVENTORY_FILE, default_inventory)
    st.session_state.inventory = remove_duplicates(loaded)
if "customers" not in st.session_state:
    st.session_state.customers = safe_load_json(CUSTOMERS_FILE, [])
if "cart" not in st.session_state:
    st.session_state.cart = []
if "owner_logged_in" not in st.session_state:
    st.session_state.owner_logged_in = False

# ----------------- UI -----------------
st.title("🛒 Vegetable Shop (Web)")
st.caption("Customer view + Owner controls. Weight items use ₹/kg; pieces use ₹/pc/liter.")

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
inv_rows = []
for item in st.session_state.inventory:
    qn, qu = avail_map[item["name"]]
    show = {
        "Name": item["name"],
        "Available": format_qty(qn, qu),
        "Price": f"₹{item['price']}/kg" if qu == "g" else f"₹{item['price']}/pc",
    }
    if st.session_state.owner_logged_in:
        show["Cost"] = f"₹{item['cost']}"
    inv_rows.append(show)
st.dataframe(inv_rows, use_container_width=True, hide_index=True)

# Add to cart
st.subheader("Add to Cart")
item_names = [it["name"] for it in st.session_state.inventory]
col1, col2, col3, col4 = st.columns([2, 1.5, 1.5, 1])
with col1:
    selected_name = st.selectbox("Item", item_names, key="add_item")
with col2:
    qty_number = st.number_input("Quantity", min_value=0.1, step=0.1, key="add_qty_num")
with col3:
    unit = st.selectbox("Unit", ["kg", "g", "pcs", "liters"], key="add_qty_unit")
with col4:
    if st.button("Add", key="add_button"):
        if qty_number <= 0:
            st.warning("Enter quantity greater than 0")
        else:
            stock_item = next(i for i in st.session_state.inventory if i["name"] == selected_name)
            sn, su = parse_qty(stock_item["qty"])
            qn = qty_number * 1000 if unit == "kg" and su == "g" else qty_number
            if su and su != unit and not (unit == "kg" and su == "g"):
                st.error(f"Use unit '{su}' for this item.")
            elif qn > sn:
                st.error("Not enough stock")
            else:
                qty_text = f"{qty_number} {unit}"
                st.session_state.cart.append({"name": selected_name, "qty": qty_text, "price": stock_item["price"]})
                st.success(f"Added {qty_text} of {selected_name}")

# Cart view
st.subheader("Cart")
if not st.session_state.cart:
    st.info("Cart is empty")
else:
    grand_total = 0
    for idx, c in enumerate(st.session_state.cart):
        qn, qu = parse_qty(c["qty"])
        total = row_total(qn, qu, c["price"])
        grand_total += total
        with st.expander(f"{idx+1}. {c['name']} - {c['qty']} (₹{total:.2f})"):
            st.write(f"Unit Price: ₹{c['price']}/{'kg' if qu=='g' else 'pc'}")
            new_qty = st.text_input(f"Edit quantity for {c['name']}", value=c["qty"], key=f"edit_qty_{idx}")
            cols = st.columns([1, 1])
            with cols[0]:
                if st.button("Update", key=f"update_{idx}"):
                    stock_item = next(i for i in st.session_state.inventory if i["name"] == c["name"])
                    sn, su = parse_qty(stock_item["qty"])
                    qn_new, qu_new = parse_qty(new_qty)
                    if qu_new != su:
                        st.error(f"Use unit '{su}' for this item.")
                    elif qn_new > sn:
                        st.error("Not enough stock")
                    elif qn_new <= 0:
                        st.error("Quantity must be greater than 0")
                    else:
                        st.session_state.cart[idx]["qty"] = new_qty
                        st.success("Updated!")
                        st.rerun()
            with cols[1]:
                if st.button("Remove", key=f"remove_{idx}"):
                    st.session_state.cart.pop(idx)
                    st.rerun()
    st.markdown(f"**Grand Total: ₹{grand_total:.2f}**")

# Checkout
st.subheader("Checkout")
with st.form("checkout_form"):
    phone = st.text_input("Customer Phone (10 digits)", max_chars=10)
    submitted = st.form_submit_button("Generate Bill & Update Stock")
if submitted:
    if not st.session_state.cart:
        st.error("Cart is empty")
    elif not (phone.isdigit() and len(phone) == 10):
        st.error("Phone must be 10 digits")
    else:
        for c in st.session_state.cart:
            item = next(i for i in st.session_state.inventory if i["name"] == c["name"])
            base_num, base_unit = parse_qty(item["qty"])
            qn, qu = parse_qty(c["qty"])
            if qu == base_unit:
                item["qty"] = format_qty(max(base_num - qn, 0), base_unit)
        grand_total = sum([row_total(*parse_qty(c["qty"]), c["price"]) for c in st.session_state.cart])
        order = {"time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "phone": phone,
                 "items": st.session_state.cart.copy(), "total": grand_total}
        st.session_state.customers.append(order)
        save_json(INVENTORY_FILE, st.session_state.inventory)
        save_json(CUSTOMERS_FILE, st.session_state.customers)
        pdf_bytes = generate_pdf_receipt_bytes(phone, st.session_state.cart, grand_total)
        st.download_button("⬇️ Download PDF Receipt", data=pdf_bytes,
                           file_name=f"receipt_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                           mime="application/pdf")
        st.session_state.cart = []
        st.success(f"Checkout complete. Total ₹{grand_total:.2f}")

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
