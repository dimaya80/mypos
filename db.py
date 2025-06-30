import mysql.connector
from datetime import datetime
import bcrypt

def db_connect():
    return mysql.connector.connect(
        host="localhost",
        user="root",        # tukar ikut setting sebenar anda
        password="",        # tukar ikut setting sebenar anda
        database="mypos"
    )

# --------- LOGIN USER ----------
def login_user(username, password):
    conn = db_connect()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM users WHERE username=%s", (username,))
    user = cur.fetchone()
    cur.close(); conn.close()
    if user and bcrypt.checkpw(password.encode(), user['password'].encode()):
        return user
    return None

# --------- AMBIL PRODUK (IKUT API.PHP) ----------
def get_products(search=''):
    conn = db_connect()
    cur = conn.cursor(dictionary=True)
    query = """
        SELECT 
            i.id,
            i.item_name as name,
            (SELECT sp.supplier_price_unit 
             FROM supplier_prices sp 
             WHERE sp.item_id = i.id 
             ORDER BY sp.date_keyin DESC 
             LIMIT 1) as price,
            i.barcode_per_unit as barcode,
            (COALESCE(SUM(sp.stock_per_unit), 0) - 
             COALESCE((SELECT SUM(si.quantity) 
                       FROM sales_items si
                       JOIN sales s ON si.sale_id = s.id
                       WHERE si.item_id = i.id), 0)) as stock
        FROM items i
        LEFT JOIN supplier_prices sp ON i.id = sp.item_id
    """
    if search:
        query += " WHERE i.item_name LIKE %s"
        cur.execute(query + " GROUP BY i.id", ('%' + search + '%',))
    else:
        cur.execute(query + " GROUP BY i.id")
    rows = cur.fetchall()
    cur.close(); conn.close()
    return rows

def get_product_by_barcode(barcode):
    conn = db_connect()
    cur = conn.cursor(dictionary=True)
    query = """
        SELECT i.id, i.item_name as name,
            (SELECT sp.supplier_price_unit FROM supplier_prices sp WHERE sp.item_id = i.id ORDER BY sp.date_keyin DESC LIMIT 1) as price,
            i.barcode_per_unit as barcode
        FROM items i
        WHERE i.barcode_per_unit=%s OR i.barcode_per_pack=%s OR i.barcode_per_box=%s
        LIMIT 1
    """
    cur.execute(query, (barcode, barcode, barcode))
    product = cur.fetchone()
    cur.close(); conn.close()
    return product

def check_stock(product_name, quantity):
    conn = db_connect()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT id FROM items WHERE item_name=%s", (product_name,))
    row = cur.fetchone()
    if not row:
        cur.close(); conn.close()
        return False
    item_id = row['id']
    cur.execute("SELECT COALESCE(SUM(stock_per_unit),0) as total_stock FROM supplier_prices WHERE item_id=%s", (item_id,))
    stock = cur.fetchone()['total_stock']
    cur.execute("SELECT COALESCE(SUM(quantity),0) as total_sold FROM sales_items WHERE item_id=%s", (item_id,))
    sold = cur.fetchone()['total_sold']
    cur.close(); conn.close()
    return (stock - sold) >= quantity

def get_low_stock_products(threshold=5):
    conn = db_connect()
    cur = conn.cursor(dictionary=True)
    query = """
        SELECT 
            i.id,
            i.item_name as name,
            (SELECT sp.supplier_price_unit FROM supplier_prices sp WHERE sp.item_id = i.id ORDER BY sp.date_keyin DESC LIMIT 1) as price,
            i.barcode_per_unit as barcode,
            (COALESCE(SUM(sp.stock_per_unit), 0) - 
             COALESCE((SELECT SUM(si.quantity) FROM sales_items si JOIN sales s ON si.sale_id = s.id WHERE si.item_id = i.id), 0)) as stock
        FROM items i
        LEFT JOIN supplier_prices sp ON i.id = sp.item_id
        GROUP BY i.id
        HAVING stock <= %s
        ORDER BY stock ASC
    """
    cur.execute(query, (threshold,))
    result = cur.fetchall()
    cur.close(); conn.close()
    return result

# --------- SUPPLIER ----------
def get_suppliers():
    conn = db_connect()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT id, supplier_name FROM suppliers ORDER BY supplier_name")
    result = cur.fetchall()
    cur.close(); conn.close()
    return result

# --------- RESTOCK (ikut api.php) ----------
def restock_product(item_id, quantity, supplier_id, price_cost, invoice_no, notes, user_id):
    conn = db_connect()
    cur = conn.cursor()
    dt_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # Insert ke supplier_prices
    cur.execute(
        "INSERT INTO supplier_prices (item_id, supplier_id, stock_per_unit, supplier_price_unit, price_cost, invoice_no, notes, date_keyin, user_id) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
        (item_id, supplier_id, quantity, price_cost, price_cost, invoice_no, notes, dt_now, user_id)
    )
    conn.commit()
    cur.close(); conn.close()
    return True

# --------- TRANSAKSI / JUALAN ----------
def save_transaction(trx_data, items):
    conn = db_connect()
    cur = conn.cursor()
    # Simpan jualan utama
    sql_trx = """
        INSERT INTO sales (receipt_no, sale_date, user_id, total, discount, payment_received, change_given, payment_method_id)
        VALUES (%s, NOW(), %s, %s, %s, %s, %s, %s)
    """
    cur.execute(sql_trx, (
        trx_data['receipt_no'],
        trx_data['user_id'],
        trx_data['total'],
        trx_data.get('discount', 0),
        trx_data['amount_paid'],
        trx_data['change_given'],
        trx_data['payment_method_id'],
    ))
    sale_id = cur.lastrowid
    # Simpan items jualan
    for item in items:
        cur.execute(
            "INSERT INTO sales_items (sale_id, item_id, quantity, unit_price, total_price) VALUES (%s,%s,%s,%s,%s)",
            (sale_id, item['item_id'], item['quantity'], item['price'], item['total'])
        )
    conn.commit()
    cur.close(); conn.close()
    return sale_id

def get_transaction(receipt_no):
    conn = db_connect()
    cur = conn.cursor(dictionary=True)
    cur.execute("""
        SELECT s.*, pm.method_name as payment_method
        FROM sales s
        LEFT JOIN payment_methods pm ON s.payment_method_id=pm.id
        WHERE s.receipt_no=%s
    """, (receipt_no,))
    trx = cur.fetchone()
    if trx:
        cur.execute("""
            SELECT i.item_name as name, si.quantity, si.unit_price as price, si.total_price as total
            FROM sales_items si
            JOIN items i ON si.item_id = i.id
            WHERE si.sale_id=%s
        """, (trx['id'],))
        items = cur.fetchall()
        trx['items'] = items
    cur.close(); conn.close()
    return trx

def get_today_sales(user_id=None):
    conn = db_connect()
    cur = conn.cursor(dictionary=True)
    today = datetime.now().strftime("%Y-%m-%d")
    if user_id:
        cur.execute("SELECT * FROM sales WHERE DATE(sale_date)=%s AND user_id=%s", (today, user_id))
    else:
        cur.execute("SELECT * FROM sales WHERE DATE(sale_date)=%s", (today,))
    sales = cur.fetchall()
    cur.close(); conn.close()
    return sales

# ---------- SHIFT ----------
def check_shift(user_id):
    conn = db_connect()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM shifts WHERE user_id=%s AND shift_end IS NULL ORDER BY shift_start DESC LIMIT 1", (user_id,))
    shift = cur.fetchone()
    cur.close(); conn.close()
    return shift

def start_shift(user_id, cash_start):
    conn = db_connect()
    cur = conn.cursor()
    cur.execute("INSERT INTO shifts (user_id, shift_start, cash_start, cash_end) VALUES (%s,NOW(),%s,%s)", (user_id, cash_start, cash_start))
    conn.commit()
    shift_id = cur.lastrowid
    cur.close(); conn.close()
    return shift_id

def end_shift(user_id, cash_end):
    conn = db_connect()
    cur = conn.cursor()
    cur.execute("UPDATE shifts SET shift_end=NOW(), cash_end=%s WHERE user_id=%s AND shift_end IS NULL", (cash_end, user_id))
    conn.commit()
    cur.close(); conn.close()
    return True

def get_shift_details(user_id):
    conn = db_connect()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM shifts WHERE user_id=%s AND shift_end IS NULL ORDER BY shift_start DESC LIMIT 1", (user_id,))
    shift = cur.fetchone()
    cur.close(); conn.close()
    return shift

# ---------- CUSTOMER ----------
def save_customer(name, phone, address):
    conn = db_connect()
    cur = conn.cursor()
    cur.execute("INSERT INTO customer_credit (customer_name, phone, address, amount, sale_id) VALUES (%s,%s,%s,0,0)", (name, phone, address))
    customer_id = cur.lastrowid
    conn.commit()
    cur.close(); conn.close()
    return customer_id

def get_customers():
    conn = db_connect()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT DISTINCT customer_name, phone, address FROM customer_credit")
    result = cur.fetchall()
    cur.close(); conn.close()
    return result

# Anda boleh tambah fungsi lain ikut keperluan table sebenar anda.
