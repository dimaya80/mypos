import mysql.connector
from datetime import datetime

def db_connect():
    return mysql.connector.connect(
        host="localhost",
        user="root",          # Ubah ikut setup anda
        password="",          # Ubah ikut setup anda
        database="mypos"
    )

# ---------- LOGIN ----------
def login_user(username, password):
    conn = db_connect()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM users WHERE username=%s AND password=%s", (username, password))
    user = cur.fetchone()
    cur.close(); conn.close()
    return user

# ---------- PRODUK ----------
def get_products(search=''):
    conn = db_connect()
    cur = conn.cursor(dictionary=True)
    if search:
        cur.execute("SELECT * FROM products WHERE name LIKE %s", ('%' + search + '%',))
    else:
        cur.execute("SELECT * FROM products")
    rows = cur.fetchall()
    cur.close(); conn.close()
    return rows

def get_product_by_barcode(barcode):
    conn = db_connect()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM products WHERE barcode=%s", (barcode,))
    product = cur.fetchone()
    cur.close(); conn.close()
    return product

def check_stock(product_id, quantity):
    conn = db_connect()
    cur = conn.cursor()
    cur.execute("SELECT stock FROM products WHERE id=%s", (product_id,))
    row = cur.fetchone()
    cur.close(); conn.close()
    return row and row[0] >= quantity

def get_low_stock_products(threshold=5):
    conn = db_connect()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM products WHERE stock <= %s", (threshold,))
    result = cur.fetchall()
    cur.close(); conn.close()
    return result

# ---------- SUPPLIER ----------
def get_suppliers():
    conn = db_connect()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM suppliers")
    result = cur.fetchall()
    cur.close(); conn.close()
    return result

# ---------- RESTOCK ----------
def restock_product(product_id, quantity, supplier_id, price_cost, invoice_no, notes, user_id):
    conn = db_connect()
    cur = conn.cursor()
    dt_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cur.execute("INSERT INTO restocks (product_id, quantity, supplier_id, price_cost, invoice_no, notes, user_id, created_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                (product_id, quantity, supplier_id, price_cost, invoice_no, notes, user_id, dt_now))
    cur.execute("UPDATE products SET stock=stock+%s WHERE id=%s", (quantity, product_id))
    conn.commit()
    cur.close(); conn.close()
    return True

# ---------- TRANSAKSI ----------
def save_transaction(trx_data, items):
    conn = db_connect()
    cur = conn.cursor()
    # Simpan transaksi utama
    sql_trx = "INSERT INTO transactions (user_id, total, discount, tax, payment_method, amount_paid, created_at) VALUES (%s,%s,%s,%s,%s,%s,%s)"
    cur.execute(sql_trx, (
        trx_data['user_id'],
        trx_data['total'],
        trx_data.get('discount', 0),
        trx_data.get('tax', 0),
        trx_data['payment_method'],
        trx_data['amount_paid'],
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ))
    trx_id = cur.lastrowid
    # Simpan item transaksi dan update stok
    for item in items:
        cur.execute(
            "INSERT INTO transaction_items (transaction_id, product_id, quantity, price) VALUES (%s,%s,%s,%s)",
            (trx_id, item['product_id'], item['quantity'], item['price'])
        )
        cur.execute("UPDATE products SET stock=stock-%s WHERE id=%s", (item['quantity'], item['product_id']))
    conn.commit()
    cur.close(); conn.close()
    return trx_id

def get_transaction(transaction_id):
    conn = db_connect()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM transactions WHERE id=%s", (transaction_id,))
    trx = cur.fetchone()
    if trx:
        cur.execute("SELECT * FROM transaction_items WHERE transaction_id=%s", (transaction_id,))
        items = cur.fetchall()
        trx['items'] = items
    cur.close(); conn.close()
    return trx

def get_today_sales(user_id=None):
    conn = db_connect()
    cur = conn.cursor(dictionary=True)
    today = datetime.now().strftime("%Y-%m-%d")
    if user_id:
        cur.execute("SELECT * FROM transactions WHERE DATE(created_at)=%s AND user_id=%s", (today, user_id))
    else:
        cur.execute("SELECT * FROM transactions WHERE DATE(created_at)=%s", (today,))
    sales = cur.fetchall()
    cur.close(); conn.close()
    return sales

# ---------- SHIFT ----------
def check_shift(user_id):
    conn = db_connect()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM shifts WHERE user_id=%s AND is_active=1", (user_id,))
    shift = cur.fetchone()
    cur.close(); conn.close()
    return shift

def start_shift(user_id, cash_start):
    conn = db_connect()
    cur = conn.cursor()
    dt_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cur.execute("INSERT INTO shifts (user_id, cash_start, is_active, shift_start) VALUES (%s,%s,1,%s)", (user_id, cash_start, dt_now))
    conn.commit()
    shift_id = cur.lastrowid
    cur.close(); conn.close()
    return shift_id

def end_shift(user_id, cash_end):
    conn = db_connect()
    cur = conn.cursor()
    dt_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cur.execute("UPDATE shifts SET cash_end=%s, is_active=0, shift_end=%s WHERE user_id=%s AND is_active=1", (cash_end, dt_now, user_id))
    conn.commit()
    cur.close(); conn.close()
    return True

def get_shift_details(user_id):
    conn = db_connect()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM shifts WHERE user_id=%s AND is_active=1", (user_id,))
    shift = cur.fetchone()
    cur.close(); conn.close()
    return shift

# ---------- LAIN-LAIN (CONTOH TAMBAHAN: HUTANG, CUSTOMER) ----------
def save_customer(name, phone, address):
    conn = db_connect()
    cur = conn.cursor()
    cur.execute("INSERT INTO customers (name, phone, address) VALUES (%s,%s,%s)", (name, phone, address))
    customer_id = cur.lastrowid
    conn.commit()
    cur.close(); conn.close()
    return customer_id

def get_customers():
    conn = db_connect()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM customers")
    result = cur.fetchall()
    cur.close(); conn.close()
    return result

# Anda boleh tambah fungsi lain mengikut table & keperluan anda
