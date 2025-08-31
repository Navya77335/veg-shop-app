import streamlit as st
import json, os, io
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from twilio.rest import Client
import boto3

# ----------------- Config -----------------
st.set_page_config(page_title="Vegetable Shop", layout="wide")

OWNER_USER = "Sidhu"
OWNER_PASS = "Mani@2"
INVENTORY_FILE = "inventory.json"
CUSTOMERS_FILE = "customers.json"

# ----------------- Load Secrets -----------------
AWS_ACCESS_KEY = "your_aws_access_key_id"
AWS_SECRET_KEY = "your_aws_secret_access_key"
AWS_BUCKET_NAME = "your-bucket-name"

TWILIO_SID = "your_twilio_account_sid"
TWILIO_AUTH = "your_twilio_auth_token"
TWILIO_SMS = "+1234567890"   # your Twilio phone number (SMS capable)

# ----------------- Helpers -----------------
def safe_load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default
    return default

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

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
        unit_price_label = f"₹{item['price']}/kg" if qu == "g" else f"₹{item['price']}/pc"
        data.append([item["name"], item["qty"], unit_price_label, f"₹{total:.2f}"])
    data.append(["", "", "Grand Total", f"₹{grand_total:.2f}"])

    table = Table(data, colWidths=[180, 120, 120, 100])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.lightblue),
        ("GRID", (0,0), (-1,-1), 1, colors.black),
    ]))
    elements.append(table)
    doc.build(elements)
    buffer.seek(0)
    return buffer.read()

def upload_pdf_to_s3(file_bytes, filename):
    """Upload PDF to S3 and return public URL, or None if AWS not set"""
    if not (AWS_ACCESS_KEY and AWS_SECRET_KEY and AWS_BUCKET_NAME):
        return None
    try:
        s3 = boto3.client(
            "s3",
            aws_access_key_id=AWS_ACCESS_KEY,
            aws_secret_access_key=AWS_SECRET_KEY,
        )
        s3.put_object(Bucket=AWS_BUCKET_NAME, Key=filename, Body=file_bytes, ContentType="application/pdf")
        url = f"https://{AWS_BUCKET_NAME}.s3.amazonaws.com/{filename}"
        return url
    except Exception as e:
        st.error(f"S3 upload failed: {e}")
        return None

def send_receipt_via_whatsapp(phone, pdf_link):
    try:
        client = Client(TWILIO_SID, TWILIO_AUTH)
        message = client.messages.create(
            body=f"✅ Thank you for shopping! Download your receipt here: {pdf_link}",
            from_=TWILIO_WHATSAPP,
            to=f"whatsapp:+91{phone}"
        )
        return message.sid
    except Exception as e:
        st.error(f"WhatsApp failed: {e}")
        return None

def send_receipt_via_sms(phone, pdf_link):
    try:
        client = Client(TWILIO_SID, TWILIO_AUTH)
        message = client.messages.create(
            body=f"✅ Thank you for shopping! Download your receipt here: {pdf_link}",
            from_=TWILIO_SMS,
            to=f"+91{phone}"
        )
        return message.sid
    except Exception as e:
        st.error(f"SMS failed: {e}")
        return None

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
    st.session_state.inventory = safe_load_json(INVENTORY_FILE, default_inventory)
if "customers" not in st.session_state:
    st.session_state.customers = safe_load_json(CUSTOMERS_FILE, [])
if "cart" not in st.session_state:
    st.session_state.cart = []
if "owner_logged_in" not in st.session_state:
    st.session_state.owner_logged_in = False

# ----------------- UI -----------------
st.title("🛒 Vegetable Shop")

# Inventory
st.subheader("Inventory")
st.table(st.session_state.inventory)

# Add to cart
st.subheader("Add to Cart")
item_names = [it["name"] for it in st.session_state.inventory]
item = st.selectbox("Select Item", item_names)
qty = st.text_input("Quantity (e.g. 2 kg, 3 pcs)")
if st.button("Add to Cart"):
    st.session_state.cart.append({"name": item, "qty": qty, "price": next(i["price"] for i in st.session_state.inventory if i["name"] == item)})
    st.success(f"Added {qty} of {item}")

# Cart
st.subheader("Cart")
if st.session_state.cart:
    st.table(st.session_state.cart)

# Checkout
st.subheader("Checkout")
phone = st.text_input("Customer Phone (10 digits)")
if st.button("Generate Bill & Send"):
    if not phone.isdigit() or len(phone) != 10:
        st.error("Phone must be 10 digits")
    elif not st.session_state.cart:
        st.error("Cart is empty")
    else:
        grand_total = sum([row_total(*parse_qty(c["qty"]), c["price"]) for c in st.session_state.cart])
        pdf_bytes = generate_pdf_receipt_bytes(phone, st.session_state.cart, grand_total)

        # Local download
        st.download_button("⬇️ Download Receipt", pdf_bytes, file_name="receipt.pdf", mime="application/pdf")

        # Upload to S3
        filename = f"receipt_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        pdf_url = upload_pdf_to_s3(pdf_bytes, filename)

        if pdf_url:
            # Send via WhatsApp
            sid = send_receipt_via_whatsapp(phone, pdf_url)
            if sid:
                st.success(f"✅ WhatsApp sent! SID: {sid}")

            # Send via SMS
            sid = send_receipt_via_sms(phone, pdf_url)
            if sid:
                st.success(f"✅ SMS sent! SID: {sid}")
        else:
            st.warning("⚠️ Could not upload to S3. Receipt only available for download.")

        # Clear cart
        st.session_state.cart = []

