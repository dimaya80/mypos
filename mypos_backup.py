import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, BooleanVar
import customtkinter as ctk
import requests
import json
import os
import serial
import time
from datetime import datetime

KEY = b'admin123'  # Ganti dengan key yang aman

def save_credentials(username, password):
    try:
        credentials = {
            'username': username,
            'password': password  # Disimpan tanpa enkripsi (HANYA UNTUK DEVELOPMENT)
        }
        
        with open('credentials.json', 'w') as f:
            json.dump(credentials, f)
    except Exception as e:
        print(f"Error saving credentials: {e}")

def load_saved_credentials():
    try:
        if os.path.exists('credentials.json'):
            with open('credentials.json', 'r') as f:
                credentials = json.load(f)
            
            entry_username.insert(0, credentials['username'])
            entry_password.insert(0, credentials['password'])
            remember_me_var.set(True)
    except Exception as e:
        print(f"Error loading credentials: {e}")

def clear_saved_credentials():
    try:
        if os.path.exists('credentials.json'):
            os.remove('credentials.json')
    except Exception as e:
        print(f"Error clearing credentials: {e}")

# ===================== KONFIGURASI =====================
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

API_URL = "http://127.0.0.1/api/api.php"
PRIMARY_COLOR = "#2B7A78"
SECONDARY_COLOR = "#3AAFA9"
ACCENT_COLOR = "#DEF2F1"
TEXT_COLOR = "#17252A"
BUTTON_COLOR = "#FEFFFF"
XTRALARGE_FONT = ("Arial", 16, "bold")
LARGE_FONT = ("Arial", 14)
MEDIUM_FONT = ("Arial", 12)

# ===================== VARIABEL GLOBAL =====================
entry_username = None
entry_password = None
remember_me_var = None
root = None
cashier_dashboard = None
tree_main = None
sales_tree = None
item_counter = 1
print_receipt_var = None
open_drawer_var = None
payment_var = None
search_var = None
results_tree = None
search_window = None
entry_amount_paid = None
entry_discount = None
entry_tax = None
label_subtotal_value = None
label_total_value = None
label_change_value = None
current_customer = None
entry_barcode = None
current_user_id = None
label_cash_end = None

# Daftar metode pembayaran
payment_methods = {
    1: "Tunai",
    2: "Hutang",
    3: "Kad Kredit/Debit",
    4: "Online Transfer",
    5: "QR Kod"
}

# ===================== FUNGSI UTAMA LENGKAP =====================

def create_login_window():
    global root, entry_username, entry_password, remember_me_var
    
    root = ctk.CTk()
    root.title("My POS System - Login")
    root.geometry("400x450")  # Tinggi ditambah untuk checkbox
    center_window(root, 400, 450)
    
    frame = ctk.CTkFrame(root)
    frame.pack(pady=50, padx=20, fill="both", expand=True)
    
    title_label = ctk.CTkLabel(frame, text="KAK NAH MINI MARKET", font=("Arial", 20, "bold"))
    title_label.pack(pady=20)
    
    # Username Frame
    username_frame = ctk.CTkFrame(frame, fg_color="transparent")
    username_frame.pack(pady=5, padx=10, fill="x")
    ctk.CTkLabel(username_frame, text="Username:").pack(side="left", padx=5)
    entry_username = ctk.CTkEntry(username_frame)
    entry_username.pack(side="right", expand=True, fill="x")
    
    # Password Frame
    password_frame = ctk.CTkFrame(frame, fg_color="transparent")
    password_frame.pack(pady=5, padx=10, fill="x")
    ctk.CTkLabel(password_frame, text="Password:").pack(side="left", padx=5)
    entry_password = ctk.CTkEntry(password_frame, show="*")
    entry_password.pack(side="right", expand=True, fill="x")
    
    # Remember Me Checkbox
    remember_me_var = ctk.BooleanVar(value=False)
    remember_me = ctk.CTkCheckBox(
        frame, 
        text="Remember Password", 
        variable=remember_me_var,
        font=("Arial", 12)
    )
    remember_me.pack(pady=10)
    
    # Login Button
    login_button = ctk.CTkButton(
        frame, 
        text="Login", 
        command=login,
        fg_color=PRIMARY_COLOR,
        font=MEDIUM_FONT
    )
    login_button.pack(pady=20)
    
    # Load saved credentials if exists
    load_saved_credentials()
    
    entry_username.focus()
    root.bind('<Return>', lambda e: login())
    
    return root

def center_window(window, width, height):
    screen_width = window.winfo_screenwidth()
    screen_height = window.winfo_screenheight()
    x = (screen_width // 2) - (width // 2)
    y = (screen_height // 2) - (height // 2)
    window.geometry(f'{width}x{height}+{x}+{y}')

def login():
    global current_user_id  # Tambahkan ini
    
    try:
        username = entry_username.get().strip()
        password = entry_password.get().strip()
        
        if not username or not password:
            messagebox.showwarning("Peringatan", "Username dan password wajib diisi!")
            return

        response = requests.post(
            API_URL,
            json={
                "action": "login",
                "username": username,
                "password": password
            },
            timeout=5
        )
        response.raise_for_status()
        result = response.json()

        if result.get("status") == "success":
            # Simpan credentials jika remember me dicentang
            if remember_me_var.get():
                save_credentials(username, password)
            else:
                clear_saved_credentials()
                
            current_user_id = result["user"]["id"]  # Simpan user ID ke variabel global
            
            # Cek shift aktif
            has_shift, shift_data = check_shift(current_user_id)
            
            if has_shift:
                open_cashier_dashboard(current_user_id)
            else:
                show_cash_start_form(current_user_id)
        else:
            messagebox.showerror("Error", result.get("message", "Login gagal"))
                
    except requests.exceptions.RequestException as e:
        messagebox.showerror("Error", f"Gagal terhubung ke server: {str(e)}")
    except Exception as e:
        messagebox.showerror("Error", f"Terjadi kesalahan: {str(e)}")

def logout():
    global current_user_id  # Tambahkan ini
    
    try:
        # Cek apakah ada user yang login
        if current_user_id is None:
            messagebox.showwarning("Peringatan", "Tidak ada user yang login")
            return
            
        # Cek apakah ada shift aktif
        has_shift, shift_data = check_shift(current_user_id)
        
        if has_shift:
            response = messagebox.askyesnocancel(
                "Peringatan",
                "Anda masih memiliki shift aktif. Pilih tindakan:\n\n"
                "Yes - Tutup shift dan keluar\n"
                "No - Keluar tanpa tutup shift\n"
                "Cancel - Batal keluar"
            )
            
            if response is None:  # Cancel
                return
            elif response:  # Yes - tutup shift
                show_cash_end_form(current_user_id)
                return
        
        # Hancurkan dashboard kasir
        if 'cashier_dashboard' in globals() and cashier_dashboard is not None:
            cashier_dashboard.destroy()
            
        # Reset user ID
        current_user_id = None
            
        # Tampilkan login window
        create_login_window().deiconify()
            
    except Exception as e:
        messagebox.showerror("Error", f"Gagal keluar: {str(e)}")
        
def check_shift(user_id):
    try:
        params = {'action': 'check_shift', 'user_id': user_id}
        response = requests.get(API_URL, params=params, timeout=5)
        response.raise_for_status()
        
        data = response.json()
        if data.get('status') == 'success':
            return data.get('has_shift', False), data.get('shift_data')
        return False, None
            
    except Exception as e:
        print(f"Error checking shift: {str(e)}")
        return False, None

def start_shift(user_id, cash_start):
    try:
        shift_data = {
            'action': 'start_shift',
            'user_id': user_id,
            'cash_start': cash_start
        }
        
        response = requests.post(
            API_URL,
            json=shift_data,
            timeout=5
        )
        response.raise_for_status()
        
        data = response.json()
        if data.get('status') == 'success':
            return True, data.get('shift_id')
        else:
            raise Exception(data.get('message', 'Gagal memulai shift'))
            
    except requests.exceptions.RequestException as e:
        messagebox.showerror("Error", f"Gagal terhubung ke server: {str(e)}")
        return False, None
    except Exception as e:
        messagebox.showerror("Error", f"Gagal memulai shift: {str(e)}")
        return False, None

def show_cash_start_form(user_id):
    global current_user_id
    current_user_id = user_id
    form = ctk.CTkToplevel()
    form.title("Mulai Shift Baru")
    form.geometry("400x300")
    form.transient(root)
    form.grab_set()
    
    def submit_cash():
        try:
            cash_amount = float(cash_entry.get())
            if cash_amount < 0:
                raise ValueError("Jumlah tidak boleh negatif")
                
            success, shift_id = start_shift(user_id, cash_amount)
            
            if success:
                messagebox.showinfo("Berhasil", 
                    f"Shift dimulai dengan cash awal: RM {cash_amount:.2f}\n"
                    f"Cash end juga diset ke RM {cash_amount:.2f}")
                form.destroy()
                open_cashier_dashboard(user_id)
            else:
                messagebox.showerror("Error", "Gagal memulai shift")
                
        except ValueError as e:
            messagebox.showerror("Error", f"Input tidak valid: {str(e)}")
            cash_entry.focus()
    
    ctk.CTkLabel(form, text="Mulai Shift Baru", font=("Arial", 18)).pack(pady=20)
    
    frame = ctk.CTkFrame(form)
    frame.pack(pady=10, padx=20, fill="both")
    
    ctk.CTkLabel(frame, text="Cash Awal:").pack(pady=5)
    cash_entry = ctk.CTkEntry(frame, font=MEDIUM_FONT)
    cash_entry.pack(pady=5)
    cash_entry.focus()
    
    btn_submit = ctk.CTkButton(
        form, 
        text="Mulai Shift", 
        command=submit_cash,
        font=MEDIUM_FONT
    )
    btn_submit.pack(pady=20)
    
    form.bind('<Return>', lambda e: submit_cash())

def get_shift_details(user_id):
    """Get detailed information about current shift including cash_end"""
    try:
        params = {'action': 'get_shift_details', 'user_id': user_id}
        response = requests.get(API_URL, params=params, timeout=5)
        response.raise_for_status()
        
        data = response.json()
        if data.get('status') == 'success':
            return data['shift_data']
        return None
        
    except Exception as e:
        print(f"Error getting shift details: {str(e)}")
        return None
    
def show_shift_details(user_id):
    # Buat window terlebih dahulu
    detail_window = ctk.CTkToplevel()
    detail_window.title("Maklumat Shift")
    detail_window.geometry("400x350")
    detail_window.resizable(False, False)
    
    # Frame utama
    main_frame = ctk.CTkFrame(detail_window)
    main_frame.pack(pady=20, padx=20, fill="both", expand=True)
    
    # Judul
    title_label = ctk.CTkLabel(main_frame, 
                             text="MAKLUMAT SHIFT", 
                             font=("Arial", 18, "bold"))
    title_label.pack(pady=10)
    
    # Grid info
    info_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
    info_frame.pack(fill="x", padx=10, pady=10)
    
    # Buat dictionary untuk menyimpan label nilai
    value_labels = {}
    
    # Data yang akan ditampilkan
    detail_keys = [
        ("Mula Shift:", "shift_start"),
        ("Tempoh:", "duration"),
        ("Cash Awal:", "cash_start"),
        ("Transaksi Tunai:", "total_cash_transactions"),
        ("Cash Semasa:", "cash_end")
    ]
    
    # Tampilkan setiap info
    for label_text, data_key in detail_keys:
        row = ctk.CTkFrame(info_frame, fg_color="transparent")
        row.pack(fill="x", pady=4)
        
        ctk.CTkLabel(row, 
                    text=label_text, 
                    font=("Arial", 14), 
                    width=150, 
                    anchor="w").pack(side="left")
        
        # Buat label untuk nilai yang akan di-update
        value_label = ctk.CTkLabel(row, 
                                 text="Loading...", 
                                 font=("Arial", 14, "bold"))
        value_label.pack(side="right")
        value_labels[data_key] = value_label
    
    # Fungsi untuk update data
    def update_shift_data():
        try:
            # Dapatkan data terbaru dari API
            params = {'action': 'get_shift_details', 'user_id': user_id}
            response = requests.get(API_URL, params=params, timeout=3)
            response.raise_for_status()
            data = response.json()

            if data.get('status') != 'success':
                raise Exception(data.get('message', 'Gagal mendapatkan data shift'))
            
            shift_data = data['shift_data']
            
            # Update nilai di tampilan
            for label_text, data_key in detail_keys:
                if data_key == 'duration':
                    value = shift_data.get(data_key, '00:00:00')
                elif data_key in ['cash_start', 'total_cash_transactions', 'cash_end']:
                    value = f"RM {float(shift_data.get(data_key, 0)):.2f}"
                else:
                    value = shift_data.get(data_key, 'N/A')
                
                value_labels[data_key].configure(text=value)
            
            # Cek perbezaan cash
            expected_cash = float(shift_data['cash_start']) + float(shift_data['total_cash_transactions'])
            current_cash = float(shift_data['cash_end'])
            
            if abs(expected_cash - current_cash) > 0.01:
                value_labels['cash_end'].configure(text_color="red")
            else:
                value_labels['cash_end'].configure(text_color=("#000000", "#FFFFFF"))  # Sesuaikan dengan theme
            
        except Exception as e:
            print(f"Error updating shift data: {str(e)}")
        finally:
            # Jadwalkan refresh berikutnya
            if detail_window.winfo_exists():
                detail_window.after(10000, update_shift_data)  # Refresh setiap 10 detik
    
    # Tombol tutup
    btn_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
    btn_frame.pack(pady=10)
    
    ctk.CTkButton(btn_frame,
                 text="Tutup",
                 command=detail_window.destroy,
                 fg_color="#6c757d",
                 width=120,
                 font=("Arial", 14)).pack(pady=10)
    
    # Mulai auto-refresh
    update_shift_data()
    
    # Handle window close
    def on_close():
        detail_window.destroy()
    
    detail_window.protocol("WM_DELETE_WINDOW", on_close)

def close_shift(user_id, cash_end):
    """Function to close the current shift"""
    try:
        response = requests.post(
            API_URL,
            json={
                "action": "end_shift",
                "user_id": user_id,
                "cash_end": cash_end
            },
            timeout=5
        )
        response.raise_for_status()
        
        result = response.json()
        if result.get("status") == "success":
            return True, result.get("data", {})
        else:
            raise Exception(result.get("message", "Gagal menutup shift"))
            
    except requests.exceptions.RequestException as e:
        messagebox.showerror("Error", f"Gagal terhubung ke server: {str(e)}")
        return False, None
    except Exception as e:
        messagebox.showerror("Error", f"Gagal menutup shift: {str(e)}")
        return False, None

def show_cash_end_form(user_id=None):
    global current_user_id
    
    # Jika user_id tidak diberikan, gunakan current_user_id
    if user_id is None:
        if current_user_id is None:
            messagebox.showerror("Error", "Tidak ada user yang login")
            return
        user_id = current_user_id

    """Enhanced shift closing form with auto-calculations"""
    try:
        # Get current shift details
        shift_details = get_shift_details(user_id)
        if not shift_details:
            messagebox.showerror("Error", "Tidak dapat memuat data shift")
            return
            
        current_cash = float(shift_details.get('cash_end', 0))
        cash_start = float(shift_details.get('cash_start', 0))
        cash_sales = float(shift_details.get('total_cash_transactions', 0))
        expected_cash = cash_start + cash_sales
        
        form = ctk.CTkToplevel()
        form.title("Tutup Shift")
        form.geometry("500x450")
        form.transient(cashier_dashboard)
        form.grab_set()
        
        def validate_cash():
            try:
                entered_cash = float(cash_entry.get())
                difference = entered_cash - expected_cash
                
                # Update difference label
                difference_label.configure(text=f"RM {difference:.2f}")
                
                # Color coding
                if abs(difference) < 0.01:  # Perfect match
                    difference_label.configure(text_color="green")
                elif abs(difference) < 10.00:  # Small difference
                    difference_label.configure(text_color="orange")
                else:  # Large difference
                    difference_label.configure(text_color="red")
                    
            except ValueError:
                pass
        
        def submit_cash():
            try:
                cash_amount = float(cash_entry.get())
                
                # Warn if significant difference
                if abs(cash_amount - expected_cash) > 10.00:
                    if not messagebox.askyesno(
                        "Peringatan", 
                        f"Perbezaan besar dengan jangkaan (RM {expected_cash:.2f}).\n"
                        "Anda yakin ingin meneruskan?"
                    ):
                        return
                
                success, shift_data = close_shift(user_id, cash_amount)
                
                if success:
                    message = (
                        f"Shift ditutup dengan sukses!\n\n"
                        f"Cash Awal: RM {cash_start:.2f}\n"
                        f"Total Penjualan Tunai: RM {cash_sales:.2f}\n"
                        f"Cash Akhir: RM {cash_amount:.2f}\n"
                        f"Perbezaan: RM {shift_data.get('cash_difference', 0):.2f}"
                    )
                    
                    messagebox.showinfo("Berhasil", message)
                    form.destroy()
                    logout()
                else:
                    messagebox.showerror("Error", "Gagal menutup shift")
                    
            except ValueError as e:
                messagebox.showerror("Error", f"Input tidak valid: {str(e)}")
                cash_entry.focus()
        
        # Main frame
        main_frame = ctk.CTkFrame(form)
        main_frame.pack(pady=20, padx=20, fill="both", expand=True)
        
        # Info section
        info_frame = ctk.CTkFrame(main_frame)
        info_frame.pack(pady=10, fill="x")
        
        # Create info rows
        def create_info_row(frame, label, value):
            row = ctk.CTkFrame(frame, fg_color="transparent")
            row.pack(fill="x", pady=2)
            ctk.CTkLabel(row, text=label, font=("Arial", 12)).pack(side="left")
            ctk.CTkLabel(row, text=value, font=("Arial", 12, "bold")).pack(side="right")
            return row
        
        create_info_row(info_frame, "Cash Awal:", f"RM {cash_start:.2f}")
        create_info_row(info_frame, "Jualan Tunai:", f"RM {cash_sales:.2f}")
        create_info_row(info_frame, "Jangkaan Cash:", f"RM {expected_cash:.2f}")
        create_info_row(info_frame, "Cash Semasa:", f"RM {current_cash:.2f}")
        
        # Cash entry section
        entry_frame = ctk.CTkFrame(main_frame)
        entry_frame.pack(pady=10, fill="x")
        
        ctk.CTkLabel(entry_frame, text="Cash Akhir:", font=("Arial", 14)).pack(pady=5)
        
        # Cash entry with calculator button
        cash_entry_frame = ctk.CTkFrame(entry_frame, fg_color="transparent")
        cash_entry_frame.pack(fill="x")
        
        cash_entry = ctk.CTkEntry(
            cash_entry_frame, 
            font=("Arial", 16),
            width=200
        )
        cash_entry.insert(0, f"{current_cash:.2f}")
        cash_entry.pack(side="left", expand=True)
        cash_entry.bind("<KeyRelease>", lambda e: validate_cash())
        
        # Calculator button
        calc_btn = ctk.CTkButton(
            cash_entry_frame,
            text="🖩",
            width=40,
            command=lambda: show_virtual_keyboard(cash_entry, "Cash Akhir")
        )
        calc_btn.pack(side="right", padx=5)
        
        # Difference display
        diff_frame = ctk.CTkFrame(entry_frame, fg_color="transparent")
        diff_frame.pack(pady=5)
        
        ctk.CTkLabel(diff_frame, text="Perbezaan:").pack(side="left")
        difference_label = ctk.CTkLabel(
            diff_frame, 
            text="RM 0.00",
            font=("Arial", 12, "bold")
        )
        difference_label.pack(side="right")
        validate_cash()  # Initial calculation
        
        # Button frame
        btn_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        btn_frame.pack(pady=10)
        
        btn_submit = ctk.CTkButton(
            btn_frame, 
            text="Tutup Shift", 
            command=submit_cash,
            font=("Arial", 14),
            fg_color="#28a745",
            height=40
        )
        btn_submit.pack(side="left", padx=5, fill="x", expand=True)
        
        btn_cancel = ctk.CTkButton(
            btn_frame,
            text="Batal",
            command=form.destroy,
            font=("Arial", 14),
            fg_color="#dc3545",
            height=40
        )
        btn_cancel.pack(side="right", padx=5, fill="x", expand=True)
        
        form.bind('<Return>', lambda e: submit_cash())
        cash_entry.focus()
        cash_entry.select_range(0, tk.END)
        
    except Exception as e:
        messagebox.showerror("Error", f"Gagal memuat form tutup shift: {str(e)}")
        
def open_cash_drawer():
    if not open_drawer_var.get():
        return
        
    try:
        ser = serial.Serial('COM5', baudrate=9600, timeout=1)
        time.sleep(2)
        ser.write(b'\x1B\x70\x00\x19\xFA')
        ser.close()
        messagebox.showinfo("Berhasil", "Laci wang berhasil dibuka!")
    except Exception as e:
        messagebox.showerror("Error", f"Gagal membuka laci wang: {e}")

def get_store_info():
    try:
        print("Mengambil maklumat kedai dari API...")
        response = requests.get(f"{API_URL}?action=get_store_info", timeout=3)
        
        print(f"Status Code: {response.status_code}")
        print(f"Response Text: {response.text}")
        
        if response.status_code == 200:
            try:
                data = response.json()
                print("Data store info dari API:", data)
                
                if 'store_name' in data and 'address' in data and 'phone' in data:
                    return {
                        'store_name': data['store_name'],
                        'address': data['address'],
                        'phone': data['phone']
                    }
                elif isinstance(data, dict) and data.get('status') == 'success' and isinstance(data.get('data'), dict):
                    store_data = data['data']
                    if 'store_name' in store_data and 'address' in store_data and 'phone' in store_data:
                        return {
                            'store_name': store_data['store_name'],
                            'address': store_data['address'],
                            'phone': store_data['phone']
                        }
                
                print("Format data tidak dikenali, tetapi status 200. Data:", data)
                
            except json.JSONDecodeError as e:
                print("Format JSON tidak valid untuk info toko:", e)
        else:
            print(f"Permintaan gagal dengan status {response.status_code}")
            
    except Exception as e:
        print("Error mendapatkan info toko:", e)
    
    raise Exception("Gagal mendapatkan maklumat kedai dari server")

def check_stock(product_name, quantity):
    """Memeriksa stok produk"""
    try:
        response = requests.get(f"{API_URL}?action=check_stock&product={product_name}", timeout=3)
        if response.status_code == 200:
            try:
                data = response.json()
                return data.get('stock', 0) >= quantity
            except json.JSONDecodeError:
                print("Format JSON tidak valid untuk cek stok")
    except Exception as e:
        print("Error memeriksa stok:", e)
    return True  # Default izinkan jika error

def get_today_sales():
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        response = requests.get(
            f"{API_URL}?action=get_today_sales&date={today}",
            timeout=5
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get('status') == 'success':
                return data['data']
            else:
                print("API Error:", data.get('message', 'Unknown error'))
        else:
            print(f"API request failed with status {response.status_code}")
    except Exception as e:
        print("Error getting today sales:", str(e))
    
    return []

def print_receipt(items, total, amount_paid, payment_method, customer_info=None, 
                 discount=0, tax=0, receipt_no=None, sale_date=None):
    """Fungsi untuk mencetak resit sebenar ke printer thermal"""
    try:
        store_info = get_store_info()
        print("Maklumat kedai yang digunakan:", store_info)
        
        if not receipt_no:
            receipt_no = "INV" + datetime.now().strftime("%Y%m%d%H%M%S")
        if not sale_date:
            sale_date = datetime.now()
        elif isinstance(sale_date, str):
            # Jika sale_date adalah string, coba parse ke datetime
            try:
                sale_date = datetime.strptime(sale_date, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                sale_date = datetime.now()

        receipt_lines = [
            "\x1B\x40",  # Initialize printer
            "\x1B\x21\x20",  # Set font size: double height
            "\x1B\x61\x01",  # Center align
            f"{store_info['store_name']}\n",
            "\x1B\x61\x01",
            f"{store_info['address']}\n",
            "\x1B\x61\x01",
            f"{store_info['phone']}\n",
            "\x1B\x21\x00",  # Reset font size
            "\x1B\x61\x00",  # Left align
            "===============================================\n",
            f"Tarikh: {sale_date.strftime('%d/%m/%Y %H:%M:%S')}\n",
            f"No Resit: {receipt_no}\n",
            "-----------------------------------------------\n",
            "Perkara               Kuantiti   Harga   Jumlah\n",
            "-----------------------------------------------\n"
        ]

        for item in items:
            name = item['name'][:15]
            quantity = int(item['quantity'])
            price = float(item['price'])
            item_total = float(item['total'])
            
            price_str = f"{price:.4f}" if price < 0.01 else f"{price:.2f}"
            
            receipt_lines.append(
                f"{name:<26} {quantity:>3} {price_str:>7} {item_total:>8.2f}\n"
            )

        subtotal = sum(float(item['total']) for item in items)
        total_after_discount = subtotal - discount
        grand_total = total_after_discount + tax
        change = amount_paid - grand_total

        receipt_lines.extend([
            "-----------------------------------------------\n",
            f"Subtotal:{'':>28}{subtotal:>10.2f}\n",
            f"Diskaun:{'':>29}{discount:>10.2f}\n",
            f"Cukai:{'':>31}{tax:>10.2f}\n",
            f"Dibayar:{'':>29}{amount_paid:>10.2f}\n",
            f"Baki Kembali:{'':>24}{change:>10.2f}\n",
            f"Total:{'':>31}{grand_total:>10.2f}\n",
            "===============================================\n",
            f"Kaedah Pembayaran:{'':>20}{payment_method}\n",
            "===============================================\n",
            "\x1B\x61\x01",  # Center align
            "Terima kasih atas kunjungan Anda\n",
            "Barang yang sudah dibeli tidak boleh ditukar\n",
            "\x1B\x61\x00",  # Left align
            "===============================================\n",
            "\n\n\n\x1D\x56\x41\x03"  # Cut paper
        ])

        receipt_text = "".join(receipt_lines)

        try:
            print("Mencoba mencetak ke printer thermal...")
            with serial.Serial('COM5', baudrate=9600, timeout=1) as printer:
                printer.write(receipt_text.encode('utf-8'))
                time.sleep(0.5)
            
            print("Resit berhasil dicetak di printer!")
            return True
            
        except Exception as e:
            error_msg = f"Gagal mencetak ke printer:\n{str(e)}"
            print("\n=== SIMULASI CETAK RESIT ===\n")
            print(receipt_text)
            print("\n=== AKHIR SIMULASI ===\n")
            messagebox.showerror("Printer Error", error_msg)
            return False

    except Exception as e:
        error_msg = f"Error saat mencetak:\n{str(e)}"
        messagebox.showerror("Error", error_msg)
        return False

def print_selected_receipt():
    selected = sales_tree.selection()
    if not selected:
        messagebox.showwarning("Peringatan", "Sila pilih transaksi terlebih dahulu")
        return
    
    try:
        receipt_no = sales_tree.item(selected[0], 'values')[1]
        print(f"Memproses resit: {receipt_no}")
        
        print("Mengambil data transaksi dari API...")
        transaction_data = get_transaction_data(receipt_no)
        
        print("Data transaksi diterima:", json.dumps(transaction_data, indent=2))
        
        if not transaction_data or 'status' not in transaction_data:
            raise ValueError("Format respons API tidak valid")
            
        if transaction_data['status'] != 'success':
            error_msg = transaction_data.get('message', 'Gagal mendapatkan data transaksi')
            raise ValueError(error_msg)
            
        if 'data' not in transaction_data:
            raise ValueError("Data transaksi tidak ditemukan dalam respons")
            
        data = transaction_data['data']
        
        required_fields = ['items', 'total', 'amount_paid', 'payment_method']
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            raise ValueError(f"Data transaksi tidak lengkap. Field yang hilang: {', '.join(missing_fields)}")
            
        if not isinstance(data['items'], list) or len(data['items']) == 0:
            raise ValueError("Daftar item tidak valid")
            
        receipt_data = {
            'items': data['items'],
            'total': float(data['total']),
            'discount': float(data.get('discount', 0)),
            'tax': float(data.get('tax', 0)),
            'amount_paid': float(data['amount_paid']),
            'payment_method': data['payment_method'],
            'customer_info': data.get('customer_info'),
            'receipt_no': data.get('receipt_no', receipt_no),
            'sale_date': data.get('sale_date')
        }
        
        print("Data yang akan dicetak:", receipt_data)
        
        print("Memulai proses cetak...")
        if print_receipt(**receipt_data):
            messagebox.showinfo("Berjaya", "Resit berhasil dicetak")
        else:
            messagebox.showerror("Gagal", "Gagal mencetak resit")
            
    except Exception as e:
        error_msg = f"Gagal mencetak resit:\n{str(e)}"
        print(error_msg)
        messagebox.showerror("Error", error_msg)
        import traceback
        traceback.print_exc()

def get_transaction_data(receipt_no):
    """Fungsi untuk mendapatkan data transaksi dengan validasi lengkap"""
    try:
        if not receipt_no or not isinstance(receipt_no, str):
            raise ValueError("Nomor resit tidak valid")
            
        params = {
            'action': 'get_transaction',
            'receipt_no': receipt_no,
            '_': int(time.time())
        }
        
        print(f"Mengambil data transaksi dengan parameter: {params}")
        
        response = requests.get(
            API_URL,
            params=params,
            timeout=10
        )
        
        print(f"Status Code: {response.status_code}")
        print(f"Response Text: {response.text[:200]}")
        
        if response.status_code != 200:
            error_msg = f"HTTP Error {response.status_code}"
            if response.text:
                error_msg += f" - {response.text[:200]}"
            raise ValueError(error_msg)
            
        if not response.text.strip():
            raise ValueError("Response dari server kosong")
            
        try:
            data = response.json()
        except json.JSONDecodeError as e:
            raise ValueError(f"Response bukan JSON valid. Server mengembalikan: {response.text[:200]}")
            
        return data
        
    except requests.exceptions.RequestException as e:
        raise ValueError(f"Gagal terhubung ke server: {str(e)}")
    except Exception as e:
        raise ValueError(f"Error tidak terduga: {str(e)}")
        
def update_quantity(item_id, tree):
    global cashier_dashboard
    
    # Cari item yang dipilih
    selected_item = None
    for item in tree.get_children():
        if tree.item(item, 'values')[0] == item_id:
            selected_item = item
            break
    
    if not selected_item:
        return
        
    current_values = tree.item(selected_item, 'values')
    product_name = current_values[1]
    current_quantity = current_values[3]
    
    # Cipta modal window dengan saiz yang lebih besar
    modal = ctk.CTkToplevel(cashier_dashboard)
    modal.title(f"Ubah Kuantiti: {product_name}")
    modal.geometry("500x600")  # Saiz modal diperbesar
    modal.transient(cashier_dashboard)
    modal.grab_set()
    
    # Pusatkan modal
    cashier_x = cashier_dashboard.winfo_x()
    cashier_y = cashier_dashboard.winfo_y()
    cashier_width = cashier_dashboard.winfo_width()
    modal_x = cashier_x + (cashier_width - 500) // 2
    modal_y = cashier_y + 100
    modal.geometry(f"+{modal_x}+{modal_y}")
    
    # Frame utama
    main_frame = ctk.CTkFrame(modal)
    main_frame.pack(pady=20, padx=20, fill="both", expand=True)
    
    # Label nama produk
    ctk.CTkLabel(main_frame, 
                 text=f"Produk: {product_name}", 
                 font=("Arial", 16, "bold")).pack(pady=10)
    
    # Label dan entry kuantiti
    ctk.CTkLabel(main_frame, 
                 text="Kuantiti Baru:", 
                 font=("Arial", 14)).pack(pady=5)
    
    quantity_entry = ctk.CTkEntry(main_frame, 
                                 font=("Arial", 18),
                                 width=250)
    quantity_entry.insert(0, str(current_quantity))
    quantity_entry.pack(pady=10)
    quantity_entry.focus()
    
    # Virtual keyboard khusus
    def on_key_press(key):
        current = quantity_entry.get()
        if key == '⌫':  # Backspace
            quantity_entry.delete(len(current)-1, tk.END)
        elif key == 'OK':
            try:
                new_quantity = int(quantity_entry.get())
                if new_quantity < 1:
                    raise ValueError("Kuantiti harus lebih besar dari 0")
                
                price = float(current_values[2].replace("RM ", ""))
                new_total = price * new_quantity
                
                # Kemas kini item di treeview
                tree.item(selected_item, values=(
                    current_values[0],
                    current_values[1],
                    current_values[2],
                    new_quantity,
                    f"RM {new_total:.2f}"
                ))
                
                # Kemas kini jumlah
                update_totals()
                
                modal.destroy()
                messagebox.showinfo("Berjaya", f"Kuantiti untuk {product_name} dikemas kini")
                
            except ValueError as e:
                messagebox.showwarning("Input Tidak Valid", 
                                     str(e) if str(e) != "" else "Masukkan nombor bulat yang valid")
                quantity_entry.focus()
        else:
            quantity_entry.insert(tk.END, key)
    
    # Frame untuk papan kekunci maya
    num_frame = ctk.CTkFrame(main_frame)
    num_frame.pack(pady=10)
    
    # Gaya butang yang lebih besar
    btn_style = {'font': ('Arial', 18), 'width': 80, 'height': 80}
    
    # Baris 1: 1-2-3
    row1 = ctk.CTkFrame(num_frame)
    row1.pack(pady=5)
    ctk.CTkButton(row1, text="1", command=lambda: on_key_press("1"), **btn_style).grid(row=0, column=0, padx=5, pady=5)
    ctk.CTkButton(row1, text="2", command=lambda: on_key_press("2"), **btn_style).grid(row=0, column=1, padx=5, pady=5)
    ctk.CTkButton(row1, text="3", command=lambda: on_key_press("3"), **btn_style).grid(row=0, column=2, padx=5, pady=5)
    
    # Baris 2: 4-5-6
    row2 = ctk.CTkFrame(num_frame)
    row2.pack(pady=5)
    ctk.CTkButton(row2, text="4", command=lambda: on_key_press("4"), **btn_style).grid(row=0, column=0, padx=5, pady=5)
    ctk.CTkButton(row2, text="5", command=lambda: on_key_press("5"), **btn_style).grid(row=0, column=1, padx=5, pady=5)
    ctk.CTkButton(row2, text="6", command=lambda: on_key_press("6"), **btn_style).grid(row=0, column=2, padx=5, pady=5)
    
    # Baris 3: 7-8-9
    row3 = ctk.CTkFrame(num_frame)
    row3.pack(pady=5)
    ctk.CTkButton(row3, text="7", command=lambda: on_key_press("7"), **btn_style).grid(row=0, column=0, padx=5, pady=5)
    ctk.CTkButton(row3, text="8", command=lambda: on_key_press("8"), **btn_style).grid(row=0, column=1, padx=5, pady=5)
    ctk.CTkButton(row3, text="9", command=lambda: on_key_press("9"), **btn_style).grid(row=0, column=2, padx=5, pady=5)
    
    # Baris 4: 0-Backspace-OK
    row4 = ctk.CTkFrame(num_frame)
    row4.pack(pady=5)
    ctk.CTkButton(row4, text="0", command=lambda: on_key_press("0"), **btn_style).grid(row=0, column=0, padx=5, pady=5)
    ctk.CTkButton(row4, text="⌫", command=lambda: on_key_press("⌫"), **btn_style).grid(row=0, column=1, padx=5, pady=5)
    ctk.CTkButton(row4, text="OK", command=lambda: on_key_press("OK"), **btn_style).grid(row=0, column=2, padx=5, pady=5)
    
    # Frame tombol aksi
    button_frame = ctk.CTkFrame(main_frame)
    button_frame.pack(pady=10)
    
    # Tombol Batal
    ctk.CTkButton(button_frame,
                 text="Batal",
                 command=modal.destroy,
                 fg_color="#dc3545",
                 font=("Arial", 16),
                 width=120,
                 height=40).pack(side="right", padx=5)
    
    # Binding Enter untuk submit
    modal.bind('<Return>', lambda e: submit_quantity())
    
def remove_item():
    selected_item = tree_main.selection()
    if not selected_item:
        messagebox.showwarning("Peringatan", "Pilih item yang ingin dihapus")
        return
        
    tree_main.delete(selected_item)
    global item_counter
    item_counter = 1
    for item in tree_main.get_children():
        values = tree_main.item(item, 'values')
        tree_main.item(item, values=(
            item_counter,
            values[1],
            values[2],
            values[3],
            values[4]
        ))
        item_counter += 1
    update_totals()

def update_totals():
    try:
        subtotal = sum(float(tree_main.item(item, 'values')[4].replace("RM ", "")) 
                      for item in tree_main.get_children())
        discount = float(entry_discount.get() or 0)
        tax = float(entry_tax.get() or 0)
        total = subtotal - discount + tax
        
        label_subtotal_value.configure(text=f"RM {subtotal:.2f}")
        label_total_value.configure(text=f"RM {total:.2f}")
        
        calculate_change()  # Sentiasa panggil calculate_change
    except ValueError:
        # Handle error jika input tidak valid
        messagebox.showwarning("Input Tidak Valid", "Harap masukkan angka yang valid")
        label_subtotal_value.configure(text="RM 0.00")
        label_total_value.configure(text="RM 0.00")
        label_change_value.configure(text="RM 0.00", text_color=TEXT_COLOR)
        
def calculate_change(*args):
    try:
        total = float(label_total_value.cget("text").replace("RM ", ""))
        amount_paid = float(entry_amount_paid.get() or 0)
        change = amount_paid - total
        
        print(f"DEBUG: calculate_change - Total: {total:.2f}, Amount Paid: {amount_paid:.2f}, Change: {change:.2f}")
        
        if change >= 0:
            label_change_value.configure(text=f"RM {change:.2f}", text_color="white")
        else:
            label_change_value.configure(text=f"RM {abs(change):.2f}", text_color="red")
    except ValueError:
        print("DEBUG: calculate_change - Input tidak valid, menetapkan baki ke 0.00")
        label_change_value.configure(text="RM 0.00", text_color=TEXT_COLOR)
        
def get_customer_info():
    """Tampilkan form informasi pelanggan untuk pembayaran hutang"""
    customer_window = ctk.CTkToplevel(cashier_dashboard)
    customer_window.title("Info Pelanggan Hutang")
    customer_window.geometry("400x300")
    customer_window.transient(cashier_dashboard)
    customer_window.grab_set()
    
    # Variabel untuk menyimpan input
    customer_data = {
        'name': tk.StringVar(),
        'phone': tk.StringVar(),
        'address': tk.StringVar()
    }
    
    # Frame utama
    main_frame = ctk.CTkFrame(customer_window)
    main_frame.pack(pady=20, padx=20, fill="both", expand=True)
    
    # Form fields
    fields = [
        ("Nama Pelanggan*", "name", name_entry := ctk.CTkEntry(main_frame, textvariable=customer_data['name'], font=MEDIUM_FONT, width=300)),
        ("No Telepon", "phone", phone_entry := ctk.CTkEntry(main_frame, textvariable=customer_data['phone'], font=MEDIUM_FONT, width=300)),
        ("Alamat", "address", address_entry := ctk.CTkEntry(main_frame, textvariable=customer_data['address'], font=MEDIUM_FONT, width=300))
    ]
    
    for label, field_key, entry in fields:
        ctk.CTkLabel(main_frame, text=label, font=MEDIUM_FONT).pack(pady=(10,0))
        entry.pack(pady=5)
    
    # Tombol aksi
    button_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
    button_frame.pack(pady=20)
    
    def on_submit():
        if not customer_data['name'].get().strip():
            messagebox.showwarning("Peringatan", "Nama pelanggan wajib diisi!")
            name_entry.focus()
            return
            
        # Simpan data pelanggan ke variabel global
        global current_customer
        current_customer = {
            'name': customer_data['name'].get().strip(),
            'phone': customer_data['phone'].get().strip(),
            'address': customer_data['address'].get().strip()
        }
        
        # Update UI pembayaran
        payment_var.set("Hutang")
        entry_amount_paid.configure(state='disabled')
        entry_amount_paid.delete(0, tk.END)
        label_change_value.configure(text="Hutang", text_color="orange")
        
        customer_window.destroy()
        messagebox.showinfo("Berhasil", "Data pelanggan tersimpan untuk pembayaran hutang")
    
    ctk.CTkButton(
        button_frame,
        text="Simpan",
        command=on_submit,
        fg_color="#2e8b57",
        hover_color="#3cb371",
        font=MEDIUM_FONT
    ).pack(side="left", padx=10)
    
    ctk.CTkButton(
        button_frame,
        text="Batal",
        command=customer_window.destroy,
        fg_color="#cd5c5c",
        hover_color="#f08080",
        font=MEDIUM_FONT
    ).pack(side="right", padx=10)
    
    # Fokus ke input nama pertama kali
    name_entry.focus()
    
    # Handle window close
    customer_window.protocol("WM_DELETE_WINDOW", customer_window.destroy)
    
    # Tunggu hingga window ditutup
    cashier_dashboard.wait_window(customer_window)
    
    return current_customer if 'current_customer' in globals() else None

def format_price(price):
    """Format harga untuk tampilan, tampilkan harga sebenar jika < RM0.01"""
    price_float = float(price)
    if price_float < 0.01 and price_float > 0:
        return f"RM {price_float:.4f}"
    else:
        return f"RM {price_float:.2f}"
    
def complete_transaction():
    global item_counter, current_customer, current_user_id
    
    # 1. Validasi user_id
    if not current_user_id:
        messagebox.showerror("Error", "User ID tidak tersedia. Silakan login kembali.")
        return

    # 2. Kumpulkan item dari keranjang belanja
    items = []
    for item in tree_main.get_children():
        try:
            values = tree_main.item(item, 'values')
            product_name = values[1]
            quantity = int(values[3])
            
            # Format harga dengan benar
            price_str = values[2].replace("RM", "").strip()
            unit_price = round(float(price_str), 4)
            total_price = round(unit_price * quantity, 4)
            
            items.append({
                'name': product_name,
                'price': unit_price,
                'quantity': quantity,
                'total': total_price
            })
        except (IndexError, ValueError) as e:
            messagebox.showerror("Error", f"Format item tidak valid: {str(e)}")
            return

    # 3. Validasi keranjang belanja
    if not items:
        messagebox.showwarning("Peringatan", "Tidak ada item dalam keranjang!")
        return

    # 4. Cek stok untuk semua item
    for item in items:
        if not check_stock(item['name'], item['quantity']):
            messagebox.showwarning("Stok Habis", f"Stok {item['name']} tidak mencukupi!")
            return

    # 5. Hitung total transaksi
    try:
        subtotal = sum(item['total'] for item in items)
        discount = float(entry_discount.get() or 0)
        tax = float(entry_tax.get() or 0)
        total = subtotal - discount + tax
    except ValueError:
        messagebox.showerror("Error", "Input diskon atau pajak tidak valid")
        return

    # 6. Proses pembayaran
    payment_method_name = payment_var.get()
    
    try:
        amount_paid = float(entry_amount_paid.get() or 0)
    except ValueError:
        amount_paid = 0

    # 7. Validasi khusus untuk pembayaran hutang
    if payment_method_name == "Hutang":
        if not current_customer or not current_customer.get('name'):
            messagebox.showwarning("Peringatan", "Data pelanggan wajib diisi untuk pembayaran hutang!")
            return
        amount_paid = 0.00
    elif amount_paid <= 0:
        messagebox.showwarning("Peringatan", "Harap masukkan jumlah pembayaran")
        return
    elif amount_paid < total:
        messagebox.showwarning("Peringatan", "Jumlah pembayaran kurang dari total")
        return

    # 8. Siapkan data transaksi
    try:
        payment_method_id = [k for k, v in payment_methods.items() if v == payment_method_name][0]
        
        transaction_data = {
            'action': 'save_transaction',
            'items': items,
            'total': total,
            'discount': discount,
            'tax': tax,
            'payment_method_id': payment_method_id,
            'payment_method': payment_method_name,
            'amount_paid': amount_paid,
            'customer_info': current_customer if payment_method_name == "Hutang" else None,
            'user_id': current_user_id
        }

        # Debugging: Log data transaksi dan user_id
        print(f"DEBUG: current_user_id: {current_user_id}")
        print(f"DEBUG: Data transaksi yang dikirim:\n{json.dumps(transaction_data, indent=2)}")

        # 9. Kirim ke API
        headers = {'Content-Type': 'application/json'}
        response = requests.post(API_URL, json=transaction_data, headers=headers, timeout=10)
        
        # Debugging: Log respons API
        print(f"DEBUG: Status Code: {response.status_code}")
        print(f"DEBUG: Response Text: {response.text[:500]}")  # Batasi output untuk keterbacaan
        
        response.raise_for_status()
        
        result = response.json()
        
        if result.get('status') != 'success':
            raise Exception(result.get('message', 'Gagal menyimpan transaksi'))

        # 10. Proses setelah transaksi berhasil
        if print_receipt_var.get():
            print_receipt(
                items=items,
                total=total,
                amount_paid=amount_paid,
                payment_method=payment_method_name,
                customer_info=current_customer,
                discount=discount,
                tax=tax,
                receipt_no=result.get('receipt_no'),
                sale_date=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            )
        
        if open_drawer_var.get():
            open_cash_drawer()

        # Reset form transaksi
        for item in tree_main.get_children():
            tree_main.delete(item)
            
        entry_discount.delete(0, tk.END)
        entry_tax.delete(0, tk.END)
        entry_amount_paid.delete(0, tk.END)
        
        entry_discount.insert(0, "0.00")
        entry_tax.insert(0, "0.00")
        
        update_totals()
        item_counter = 1
        current_customer = None
        
        load_today_sales()
        
        if 'update_shift_display' in globals():
            update_shift_display()

        messagebox.showinfo("Sukses", "Transaksi berhasil diselesaikan!")

    except requests.exceptions.RequestException as e:
        messagebox.showerror("Error", f"Gagal terhubung ke server: {str(e)}")
        print(f"DEBUG: Request Exception: {str(e)}")
    except Exception as e:
        messagebox.showerror("Error", f"Gagal menyelesaikan transaksi: {str(e)}")
        print(f"DEBUG: Error detail: {str(e)}")
        import traceback
        traceback.print_exc()
        
def show_virtual_keyboard(entry_widget, title=""):
    # Cek apakah keyboard window sudah ada
    if hasattr(show_virtual_keyboard, "keyboard_window") and show_virtual_keyboard.keyboard_window.winfo_exists():
        show_virtual_keyboard.keyboard_window.lift()  # Bawa ke depan
        show_virtual_keyboard.keyboard_window.focus_force()
        return
    
    def on_key_press(key):
        if key == '⌫':  # Backspace
            entry_widget.delete(len(entry_widget.get())-1, tk.END)
        elif key == 'OK':
            show_virtual_keyboard.keyboard_window.destroy()
            if entry_widget in [entry_discount, entry_tax]:
                update_totals()  # Panggil update_totals untuk diskaun/cukai
            else:
                calculate_change()  # Panggil calculate_change untuk amount_paid
        else:
            entry_widget.insert(tk.END, key)
    
    # Buat window keyboard
    show_virtual_keyboard.keyboard_window = ctk.CTkToplevel(cashier_dashboard)
    show_virtual_keyboard.keyboard_window.title(f"Keyboard Nombor - {title}" if title else "Keyboard Nombor")
    show_virtual_keyboard.keyboard_window.geometry("300x450")
    show_virtual_keyboard.keyboard_window.resizable(False, False)
    
    # Pastikan keyboard selalu di atas cashier_dashboard
    show_virtual_keyboard.keyboard_window.transient(cashier_dashboard)
    show_virtual_keyboard.keyboard_window.grab_set()
    
    # Atur posisi di atas GUI kasir
    cashier_x = cashier_dashboard.winfo_x()
    cashier_y = cashier_dashboard.winfo_y()
    cashier_width = cashier_dashboard.winfo_width()
    
    keyboard_x = cashier_x + (cashier_width - 300) // 2  # Tengah horizontal
    keyboard_y = cashier_y + 100  # 100 pixel dari atas
    
    show_virtual_keyboard.keyboard_window.geometry(f"+{keyboard_x}+{keyboard_y}")
    
    # Style untuk tombol
    btn_style = {'font': ('Arial', 14), 'width': 60, 'height': 60}
    
    # Frame untuk tombol angka
    num_frame = ctk.CTkFrame(show_virtual_keyboard.keyboard_window)
    num_frame.pack(pady=5)
    
    # Baris 1
    row1 = ctk.CTkFrame(num_frame)
    row1.pack(pady=2)
    ctk.CTkButton(row1, text="1", command=lambda: on_key_press("1"), **btn_style).grid(row=0, column=0, padx=2, pady=2)
    ctk.CTkButton(row1, text="2", command=lambda: on_key_press("2"), **btn_style).grid(row=0, column=1, padx=2, pady=2)
    ctk.CTkButton(row1, text="3", command=lambda: on_key_press("3"), **btn_style).grid(row=0, column=2, padx=2, pady=2)
    
    # Baris 2
    row2 = ctk.CTkFrame(num_frame)
    row2.pack(pady=2)
    ctk.CTkButton(row2, text="4", command=lambda: on_key_press("4"), **btn_style).grid(row=0, column=0, padx=2, pady=2)
    ctk.CTkButton(row2, text="5", command=lambda: on_key_press("5"), **btn_style).grid(row=0, column=1, padx=2, pady=2)
    ctk.CTkButton(row2, text="6", command=lambda: on_key_press("6"), **btn_style).grid(row=0, column=2, padx=2, pady=2)
    
    # Baris 3
    row3 = ctk.CTkFrame(num_frame)
    row3.pack(pady=2)
    ctk.CTkButton(row3, text="7", command=lambda: on_key_press("7"), **btn_style).grid(row=0, column=0, padx=2, pady=2)
    ctk.CTkButton(row3, text="8", command=lambda: on_key_press("8"), **btn_style).grid(row=0, column=1, padx=2, pady=2)
    ctk.CTkButton(row3, text="9", command=lambda: on_key_press("9"), **btn_style).grid(row=0, column=2, padx=2, pady=2)
    
    # Baris 4
    row4 = ctk.CTkFrame(num_frame)
    row4.pack(pady=2)
    ctk.CTkButton(row4, text=".", command=lambda: on_key_press("."), **btn_style).grid(row=0, column=0, padx=2, pady=2)
    ctk.CTkButton(row4, text="0", command=lambda: on_key_press("0"), **btn_style).grid(row=0, column=1, padx=2, pady=2)
    ctk.CTkButton(row4, text="⌫", command=lambda: on_key_press("⌫"), **btn_style).grid(row=0, column=2, padx=2, pady=2)
    
    # Tombol OK
    ok_frame = ctk.CTkFrame(show_virtual_keyboard.keyboard_window)
    ok_frame.pack(pady=5)
    ctk.CTkButton(ok_frame, text="OK", command=lambda: on_key_press("OK"), 
                 font=('Arial', 16), width=200, height=50).pack(pady=5)

def open_search_product():
    global search_window, search_entry, results_tree, search_var
    
    # Cek jika window sudah ada
    if hasattr(open_search_product, 'search_window') and open_search_product.search_window.winfo_exists():
        open_search_product.search_window.lift()
        open_search_product.search_window.focus_force()
        return
    
    # Inisialisasi window
    search_window = ctk.CTkToplevel()
    search_window.title("Cari Produk")
    search_window.geometry("1000x700")
    open_search_product.search_window = search_window
    
    # Variabel pencarian
    search_var = ctk.StringVar()
    
    # Frame pencarian
    search_frame = ctk.CTkFrame(search_window)
    search_frame.pack(pady=10, padx=10, fill='x')
    
    # Entry field dengan nama khusus
    search_entry = ctk.CTkEntry(
        search_frame,
        textvariable=search_var,
        font=("Arial", 14),
        placeholder_text="Cari produk...",
        width=600
    )
    search_entry.pack(side='left', fill='x', expand=True, padx=5)
    search_entry.focus()
    
    # Tombol cari
    search_button = ctk.CTkButton(
        search_frame,
        text="Cari",
        command=lambda: do_search()
    )
    search_button.pack(side='left', padx=5)
    
    # Treeview hasil
    results_frame = ctk.CTkFrame(search_window)
    results_frame.pack(fill='both', expand=True, padx=10, pady=10)
    
    # Style untuk treeview
    style = ttk.Style()
    style.configure("Search.Treeview", font=("Arial", 12), rowheight=30)
    
    results_tree = ttk.Treeview(
        results_frame,
        columns=("No", "Nama", "Harga", "Stok", "Barcode"),
        show="headings",
        style="Search.Treeview"
    )
    
    # Konfigurasi kolom
    results_tree.column("No", width=50, anchor='center')
    results_tree.column("Nama", width=400, anchor='w')
    results_tree.column("Harga", width=100, anchor='e')
    results_tree.column("Stok", width=80, anchor='center')
    results_tree.column("Barcode", width=150, anchor='center')
    
    for col in results_tree['columns']:
        results_tree.heading(col, text=col)
    
    # Scrollbar
    scrollbar = ttk.Scrollbar(results_frame, orient="vertical", command=results_tree.yview)
    results_tree.configure(yscrollcommand=scrollbar.set)
    results_tree.pack(side='left', fill='both', expand=True)
    scrollbar.pack(side='right', fill='y')
    
    # Binding event
    search_var.trace_add("write", lambda *args: search_window.after(500, do_search))
    search_entry.bind("<Return>", lambda e: do_search())

    # Di bagian akhir fungsi open_search_product(), tambahkan:
    results_tree.bind("<Double-1>", lambda event: add_selected_product())
    
def do_search(event=None):
    global search_var, results_tree
    
    # Dapatkan query dari StringVar
    query = search_var.get().strip()
    print(f"DEBUG: Query pencarian - '{query}'")
    
    # Validasi panjang query
    if len(query) < 2:
        results_tree.delete(*results_tree.get_children())
        return
    
    try:
        # Buat parameter request
        params = {
            'action': 'search_products',
            'query': query,
            'limit': 50
        }
        print(f"DEBUG: Mengirim request ke API dengan params: {params}")
        
        # Lakukan request
        response = requests.get(API_URL, params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        print(f"DEBUG: Response dari API: {data}")
        
        # Validasi response
        if not isinstance(data, dict) or 'data' not in data:
            raise ValueError("Format response tidak valid")
            
        products = data['data']
        
        # Update treeview
        results_tree.delete(*results_tree.get_children())
        for idx, product in enumerate(products, start=1):
            try:
                results_tree.insert("", "end", values=(
                    idx,
                    product.get('name', 'N/A'),
                    f"RM {float(product.get('price', 0)):.2f}",
                    product.get('stock', 'N/A'),
                    product.get('barcode', '')
                ))
            except Exception as e:
                print(f"DEBUG: Gagal memproses produk {idx}: {str(e)}")
                continue
                
    except Exception as e:
        print(f"DEBUG: Error dalam pencarian: {str(e)}")
        messagebox.showerror("Error", f"Terjadi kesalahan: {str(e)}")

def add_selected_product():
    global item_counter, tree_main
    
    # Dapatkan item yang dipilih
    selected_item = results_tree.focus()
    
    if not selected_item:
        messagebox.showwarning("Peringatan", "Silakan pilih produk terlebih dahulu")
        return
    
    try:
        # Dapatkan nilai dari item yang dipilih
        item_values = results_tree.item(selected_item, 'values')
        
        # Validasi data
        if len(item_values) < 3:
            raise ValueError("Data produk tidak lengkap")
            
        product_name = item_values[1]
        price_str = item_values[2].replace("RM", "").strip()
        
        try:
            product_price = float(price_str)
        except ValueError:
            raise ValueError(f"Harga tidak valid: {price_str}")
            
        # Cek apakah produk sudah ada di keranjang
        for item in tree_main.get_children():
            values = tree_main.item(item, 'values')
            if values[1] == product_name:  # Bandingkan berdasarkan nama produk
                new_quantity = int(values[3]) + 1
                new_total = new_quantity * product_price
                
                # Update item yang sudah ada
                tree_main.item(item, values=(
                    values[0],
                    values[1],
                    f"RM {product_price:.2f}",
                    new_quantity,
                    f"RM {new_total:.2f}"
                ))
                
                update_totals()
                messagebox.showinfo("Berhasil", f"Kuantitas {product_name} ditambah")
                return
                
        # Jika produk belum ada di keranjang, tambahkan baru
        tree_main.insert("", "end", values=(
            item_counter,
            product_name,
            f"RM {product_price:.2f}",
            1,
            f"RM {product_price:.2f}"
        ))
        item_counter += 1
        update_totals()
        
        messagebox.showinfo("Berhasil", f"{product_name} ditambahkan ke keranjang")
        
    except Exception as e:
        messagebox.showerror("Error", f"Gagal menambahkan produk:\n{str(e)}")

def scan_barcode(barcode, tree):
    """Scan barcode dan tambahkan produk ke keranjang"""
    if not barcode:
        return

    try:
        response = requests.get(f"{API_URL}?barcode={barcode}")
        response.raise_for_status()
        
        product = response.json()
        
        if not product or 'id' not in product:
            messagebox.showwarning("Peringatan", "Produk tidak ditemukan!")
            return
            
        product_name = product['name']
        product_price = product['price']
        
        if not check_stock(product_name, 1):
            messagebox.showwarning("Stok Habis", f"Stok {product_name} tidak mencukupi!")
            return
            
        price_float = float(product_price)
        
        for item in tree.get_children():
            values = tree.item(item, 'values')
            if values[1] == product_name:
                new_quantity = int(values[3]) + 1
                if not check_stock(product_name, new_quantity):
                    messagebox.showwarning("Stok Habis", 
                        f"Stok {product_name} tidak cukup untuk kuantitas {new_quantity}!")
                    return
                
                new_total = new_quantity * price_float
                tree.item(item, values=(
                    values[0],
                    values[1],
                    format_price(product_price),
                    new_quantity,
                    format_price(str(new_total))
                ))
                update_totals()
                # Clear barcode entry after successful scan
                entry_barcode.delete(0, tk.END)
                return
        
        global item_counter
        tree.insert("", "end", values=(
            item_counter,
            product_name,
            format_price(product_price),
            1,
            format_price(product_price))
        )
        item_counter += 1
        update_totals()
        # Clear barcode entry after successful scan
        entry_barcode.delete(0, tk.END)
        
    except requests.exceptions.RequestException as e:
        messagebox.showerror("Error", f"Gagal terhubung ke server: {e}")
    except (json.JSONDecodeError, ValueError, KeyError) as e:
        messagebox.showerror("Error", f"Data produk tidak valid: {e}")

def load_today_sales():
    try:
        sales_tree.delete(*sales_tree.get_children())
        today_sales = get_today_sales()
        
        if not isinstance(today_sales, list):
            raise ValueError("Data penjualan harus berupa list")
        
        for sale in today_sales:
            if not all(key in sale for key in ['no', 'receipt_no', 'sale_time', 'total', 'discount', 'amount_paid', 'change_given', 'payment_method', 'status']):
                print("Data penjualan tidak valid:", sale)
                continue
                
            sales_tree.insert("", "end", values=(
                sale['no'],
                sale['receipt_no'],
                sale['sale_time'],
                f"RM {float(sale['total']):.2f}",
                f"RM {float(sale['discount']):.2f}",
                f"RM {float(sale['amount_paid']):.2f}",
                f"RM {float(sale['change_given']):.2f}",
                sale['payment_method'],
                sale['status']
            ))
    except Exception as e:
        messagebox.showerror("Error", f"Gagal memuat penjualan hari ini: {str(e)}")
        
def init_payment_system():
    global payment_var
    payment_var = ctk.StringVar(value="Tunai")
    payment_var.trace_add("write", on_payment_method_change)
    return payment_var

def on_payment_method_change(*args):
    if not hasattr(payment_var, 'get'):  # Pastikan payment_var valid
        return
        
    method = payment_var.get()
    
    # Pastikan widget yang diperlukan ada
    if 'entry_amount_paid' not in globals() or not entry_amount_paid.winfo_exists():
        return
    
    if method == "Hutang":
        # Pastikan cashier_dashboard ada dan valid
        if 'cashier_dashboard' in globals() and cashier_dashboard.winfo_exists():
            customer_info = get_customer_info()
            if not customer_info:
                payment_var.set("Tunai")  # Kembalikan ke Tunai jika tidak ada info customer
                return
        
        # Nonaktifkan entry amount paid untuk pembayaran hutang
        entry_amount_paid.configure(state='disabled')
        entry_amount_paid.delete(0, tk.END)
        
        # Reset change value
        if 'label_change_value' in globals():
            label_change_value.configure(text="RM 0.00", text_color=TEXT_COLOR)
    else:
        # Aktifkan entry amount paid untuk metode pembayaran lain
        entry_amount_paid.configure(state='normal')
        entry_amount_paid.delete(0, tk.END)
        
        # Reset change value
        if 'label_change_value' in globals():
            label_change_value.configure(text="RM 0.00", text_color=TEXT_COLOR)

def update_shift_display():
    global current_user_id, label_shift_info, label_cash_end
    
    if not current_user_id or not cashier_dashboard.winfo_exists():
        return
        
    try:
        # Dapatkan data shift terbaru dari API
        has_shift, shift_data = check_shift(current_user_id)
        print(f"Debug - Shift Data: {shift_data}")
        
        if has_shift and shift_data:
            print(f"Debug - Shift Data: {shift_data}")
            cash_start = float(shift_data.get('cash_start', 0))
            cash_end = float(shift_data.get('cash_end', 0))
            total_cash = float(shift_data.get('total_cash_transactions', 0))
            
            # Format teks untuk ditampilkan
            shift_text = (
                f"Shift Aktif | "
                f"Mulai: {shift_data.get('shift_start', 'N/A')} | "
                f"Cash Awal: RM {cash_start:.2f} | "
                f"Cash Akhir: RM {cash_end:.2f}"
            )
            
            # Update label
            if label_shift_info and label_shift_info.winfo_exists():
                label_shift_info.configure(text=shift_text)
                
                # Highlight jika ada perubahan cash_end
                if hasattr(update_shift_display, 'last_cash_end'):
                    if cash_end > update_shift_display.last_cash_end:
                        label_shift_info.configure(text_color="#90EE90")  # Hijau muda
                        cashier_dashboard.after(1000, lambda: label_shift_info.configure(text_color="white"))
                    elif cash_end < update_shift_display.last_cash_end:
                        label_shift_info.configure(text_color="#FFCCCB")  # Merah muda
                        cashier_dashboard.after(1000, lambda: label_shift_info.configure(text_color="white"))
                
                update_shift_display.last_cash_end = cash_end
                
    except Exception as e:
        print(f"Error updating shift display: {str(e)}")
    
    # Jadwalkan update berikutnya
    if cashier_dashboard.winfo_exists():
        cashier_dashboard.after(10000, update_shift_display)  # Update setiap 10 detik
        
def open_cashier_dashboard(user_id):
    global cashier_dashboard, tree_main, sales_tree, tree_low_stock, item_counter
    global print_receipt_var, open_drawer_var, payment_var, current_customer
    global entry_discount, entry_tax, entry_amount_paid, entry_barcode
    global label_subtotal_value, label_total_value, label_change_value
    global low_stock_frame, current_user_id, label_shift_info
    
    try:
        # Tutup window login jika masih terbuka
        if 'root' in globals() and root and root.winfo_exists():
            root.withdraw()
        
        # Buat window utama
        cashier_dashboard = ctk.CTk()
        cashier_dashboard.title("Sistem Kasir")
        cashier_dashboard.geometry("1400x900")
        cashier_dashboard.attributes("-fullscreen", True)

        # Style configuration
        XTRALARGE_FONT = ("Arial", 28, "bold")
        LARGE_FONT = ("Arial", 16)
        MEDIUM_FONT = ("Arial", 12)
        PRIMARY_COLOR = "#2B7A78"
        SECONDARY_COLOR = "#3AAFA9"
        TEXT_COLOR = "#17252A"
        
        # Payment methods
        payment_methods = {
            1: "Tunai",
            2: "Hutang",
            3: "Kad Kredit/Debit",
            4: "Online Transfer",
            5: "QR Kod"
        }
        
        # Initialize payment system
        payment_var = ctk.StringVar(value="Tunai")
        
        # Fungsi untuk handle close window
        def on_close():
            if messagebox.askokcancel("Keluar", "Anda yakin ingin keluar dari sistem?"):
                cashier_dashboard.destroy()
                if 'root' in globals() and root and root.winfo_exists():
                    root.deiconify()
        
        cashier_dashboard.protocol("WM_DELETE_WINDOW", on_close)

        # Initialize variables
        item_counter = 1
        print_receipt_var = ctk.BooleanVar(value=True)
        open_drawer_var = ctk.BooleanVar(value=True)
        current_customer = None

        # ==================== HEADER FRAME ====================
        header_frame = ctk.CTkFrame(cashier_dashboard, height=80, fg_color=PRIMARY_COLOR)
        header_frame.pack(fill="x", padx=0, pady=0)
        
        # App title (kiri)
        ctk.CTkLabel(header_frame, 
                    text="My POS System Ver 1.0", 
                    font=("Arial", 24, "bold"), 
                    text_color="white").pack(side="left", padx=20)
        
        # Shift info (kanan) - Hanya satu label
        label_shift_info = ctk.CTkLabel(
            header_frame,
            text="Memuat info shift...",
            font=("Arial", 14),
            text_color="white"
        )
        label_shift_info.pack(side="right", padx=20)
                
        # ==================== MAIN CONTENT FRAME ====================
        main_frame = ctk.CTkFrame(cashier_dashboard)
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        # ==================== LEFT PANEL ====================
        left_frame = ctk.CTkFrame(main_frame)
        left_frame.pack(side="left", fill="both", expand=True, padx=10)

        # Options frame
        option_frame = ctk.CTkFrame(left_frame)
        option_frame.pack(fill="x", pady=5)
        
        ctk.CTkCheckBox(option_frame, 
                       text="Cetak Resit", 
                       variable=print_receipt_var, 
                       font=MEDIUM_FONT).pack(side="left", padx=10)
        
        ctk.CTkCheckBox(option_frame,
                       text="Buka Laci Wang",
                       variable=open_drawer_var,
                       font=MEDIUM_FONT).pack(side="left", padx=10)

        # Barcode scan frame
        scan_frame = ctk.CTkFrame(left_frame)
        scan_frame.pack(fill="x", pady=10)
        
        # Function keys
        btn_f1 = ctk.CTkButton(scan_frame, text="F1\nBarcode", 
                             command=lambda: entry_barcode.focus_set(),
                             fg_color=SECONDARY_COLOR, 
                             font=("Arial", 12, "bold"),
                             height=40, width=80)
        btn_f1.pack(side="left", padx=5)
        
        btn_f2 = ctk.CTkButton(scan_frame, text="F2\nBayar", 
                             command=lambda: [entry_amount_paid.focus(), 
                                            show_virtual_keyboard(entry_amount_paid)],
                             fg_color=SECONDARY_COLOR, 
                             font=("Arial", 12, "bold"),
                             height=40, width=80)
        btn_f2.pack(side="left", padx=5)
        
        # Barcode entry
        ctk.CTkLabel(scan_frame, text="Scan Barcode:", font=MEDIUM_FONT).pack(side="left", padx=5)
        entry_barcode = ctk.CTkEntry(scan_frame, font=LARGE_FONT, width=300)
        entry_barcode.pack(side="left", padx=10)
        entry_barcode.bind("<Return>", lambda e: [scan_barcode(entry_barcode.get(), tree_main), entry_barcode.focus_set()])
        entry_barcode.focus_set()        

        # Keyboard shortcuts
        cashier_dashboard.bind('<F1>', lambda e: entry_barcode.focus_set())
        cashier_dashboard.bind('<F2>', lambda e: entry_amount_paid.focus_set())

        # Notebook for cart, sales and low stock
        notebook = ttk.Notebook(left_frame)
        notebook.pack(fill="both", expand=True)

        # ===== TAB 1: Shopping Cart =====
        cart_frame = ctk.CTkFrame(notebook)
        notebook.add(cart_frame, text="Troli Jualan")

        # Configure treeview style
        style = ttk.Style()
        # Ubah saiz fon kepada 18 dan tingkatkan rowheight
        style.configure("Large.Treeview", font=("Arial", 18), rowheight=40)
        style.configure("Large.Treeview.Heading", font=("Arial", 18, "bold"))

        # Create main table
        columns = ("ID", "Nama Produk", "Harga", "Kuantiti", "Total")
        tree_main = ttk.Treeview(cart_frame, columns=columns, show="headings", style="Large.Treeview")

        # Configure columns
        for col in columns:
            tree_main.heading(col, text=col)
            tree_main.column(col, width=100, anchor='center')

        tree_main.column("Nama Produk", width=250)
        tree_main.pack(fill="both", expand=True, padx=5, pady=5)

        # Bind double click event
        tree_main.bind("<Double-1>", lambda e: update_quantity(tree_main.item(tree_main.focus(), 'values')[0], tree_main))
        
        # ===== TAB 2: Sales History =====
        sales_frame = ctk.CTkFrame(notebook)
        notebook.add(sales_frame, text="Jualan Hari Ini")

        # Create sales treeview
        sales_columns = ("No", "Resit", "Tarikh/Masa", "Jumlah", "Diskaun", 
                        "Jumlah Bayaran", "Baki Pulangan", "Kaedah Bayaran", "Status")
        
        sales_tree = ttk.Treeview(sales_frame, columns=sales_columns, show="headings", style="Large.Treeview")
        
        # Configure columns
        for col in sales_columns:
            sales_tree.heading(col, text=col)
            sales_tree.column(col, width=80, anchor='center')
        
        sales_tree.column("Resit", width=120)
        sales_tree.column("Tarikh/Masa", width=150)
        sales_tree.pack(fill="both", expand=True, padx=5, pady=5)

        # Sales buttons frame
        sales_button_frame = ctk.CTkFrame(sales_frame)
        sales_button_frame.pack(fill="x", pady=5)

        # Refresh button
        refresh_btn = ctk.CTkButton(sales_button_frame, 
                                  text="Refresh", 
                                  command=load_today_sales,
                                  fg_color=SECONDARY_COLOR,
                                  font=MEDIUM_FONT)
        refresh_btn.pack(side="left", padx=5, fill="x", expand=True)

        # Print receipt button
        print_btn = ctk.CTkButton(sales_button_frame, 
                                text="Cetak Resit", 
                                command=print_selected_receipt,
                                fg_color="#32CD32",
                                font=MEDIUM_FONT)
        print_btn.pack(side="left", padx=5, fill="x", expand=True)

        # ===== TAB 3: Low Stock Products =====
        low_stock_frame = ctk.CTkFrame(notebook)
        notebook.add(low_stock_frame, text="Stok Kritikal")
        
        # Style for low stock treeview
        style.configure("LowStock.Treeview", font=MEDIUM_FONT, rowheight=30)
        style.configure("LowStock.Treeview.Heading", font=MEDIUM_FONT)
        
        # Create low stock treeview
        low_stock_columns = ("No", "Nama Produk", "Stok", "Status")
        tree_low_stock = ttk.Treeview(low_stock_frame, columns=low_stock_columns, 
                                     show="headings", style="LowStock.Treeview")
        
        # Configure columns
        for col in low_stock_columns:
            tree_low_stock.heading(col, text=col)
            tree_low_stock.column(col, width=100, anchor='center')
        
        tree_low_stock.column("Nama Produk", width=250)
        tree_low_stock.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Configure row colors
        tree_low_stock.tag_configure('out-of-stock', background='#ffcccc')  # Merah muda untuk stok habis
        tree_low_stock.tag_configure('low-stock', background='#fff3cd')     # Kuning muda untuk stok rendah
        
        # Refresh button for low stock
        btn_refresh_low_stock = ctk.CTkButton(low_stock_frame,
                                            text="Refresh Stok",
                                            command=lambda: load_low_stock_products(tree_low_stock),
                                            fg_color="#FF6347",
                                            font=MEDIUM_FONT)
        btn_refresh_low_stock.pack(pady=5)
        
        # Load initial data
        load_low_stock_products(tree_low_stock)
        add_restock_button_to_low_stock()
        
        # ==================== RIGHT PANEL ====================
        right_frame = ctk.CTkFrame(main_frame, width=350)
        right_frame.pack(side="right", fill="y", padx=10)

        # Payment method frame
        payment_method_frame = ctk.CTkFrame(right_frame)
        payment_method_frame.pack(fill="x", pady=10)
        
        ctk.CTkLabel(payment_method_frame, 
                    text="Kaedah Pembayaran", 
                    font=("Arial", 14, "bold")).pack(pady=5)

        # Add payment method radio buttons
        for method_id, method_name in payment_methods.items():
            rb = ctk.CTkRadioButton(payment_method_frame, 
                                  text=method_name,
                                  variable=payment_var, 
                                  value=method_name,
                                  font=MEDIUM_FONT)
            rb.pack(anchor="w", padx=5, pady=2)

        # Payment info frame
        payment_info_frame = ctk.CTkFrame(right_frame)
        payment_info_frame.pack(fill="x", pady=10)

        ctk.CTkLabel(payment_info_frame, 
                     text="Informasi Pembayaran", 
                     font=("Arial", 14, "bold")).pack(pady=5)

        # Subtotal
        subtotal_frame = ctk.CTkFrame(payment_info_frame)
        subtotal_frame.pack(fill="x", padx=5, pady=2)
        ctk.CTkLabel(subtotal_frame, text="Subtotal:", font=LARGE_FONT).pack(side="left")
        label_subtotal_value = ctk.CTkLabel(subtotal_frame, text="RM 0.00", font=XTRALARGE_FONT)
        label_subtotal_value.pack(side="right")

        # Discount
        discount_frame = ctk.CTkFrame(payment_info_frame)
        discount_frame.pack(fill="x", padx=5, pady=2)
        ctk.CTkLabel(discount_frame, text="Diskaun:", font=LARGE_FONT).pack(side="left")
        entry_discount = ctk.CTkEntry(discount_frame, font=XTRALARGE_FONT, width=120)
        entry_discount.insert(0, "0.00")
        entry_discount.pack(side="right")
        entry_discount.bind("<Button-1>", lambda e: show_virtual_keyboard(entry_discount, "Diskaun"))
        entry_discount.bind("<KeyRelease>", lambda e: update_totals())  # Tambah binding

        # Tax
        tax_frame = ctk.CTkFrame(payment_info_frame)
        tax_frame.pack(fill="x", padx=5, pady=2)
        ctk.CTkLabel(tax_frame, text="Cukai:", font=LARGE_FONT).pack(side="left")
        entry_tax = ctk.CTkEntry(tax_frame, font=XTRALARGE_FONT, width=120)
        entry_tax.insert(0, "0.00")
        entry_tax.pack(side="right")
        entry_tax.bind("<Button-1>", lambda e: show_virtual_keyboard(entry_tax, "Cukai"))
        entry_tax.bind("<KeyRelease>", lambda e: update_totals())  # Tambah binding

        # Total
        total_frame = ctk.CTkFrame(payment_info_frame)
        total_frame.pack(fill="x", padx=5, pady=5)
        ctk.CTkLabel(total_frame, text="Total:", font=LARGE_FONT).pack(side="left")
        label_total_value = ctk.CTkLabel(total_frame, text="RM 0.00", font=XTRALARGE_FONT)
        label_total_value.pack(side="right")

        # Payment details frame
        payment_detail_frame = ctk.CTkFrame(right_frame)
        payment_detail_frame.pack(fill="x", pady=10)

        ctk.CTkLabel(payment_detail_frame, 
                     text="Detail Pembayaran", 
                     font=("Arial", 14, "bold")).pack(pady=5)

        # Amount paid
        amount_paid_frame = ctk.CTkFrame(payment_detail_frame)
        amount_paid_frame.pack(fill="x", padx=5, pady=2)
        ctk.CTkLabel(amount_paid_frame, text="Jumlah Bayar:", font=LARGE_FONT).pack(side="left")
        entry_amount_paid = ctk.CTkEntry(amount_paid_frame, font=XTRALARGE_FONT, width=120)
        entry_amount_paid.pack(side="right")
        entry_amount_paid.bind("<Button-1>", lambda e: show_virtual_keyboard(entry_amount_paid, "Jumlah Bayar"))
        entry_amount_paid.bind("<KeyRelease>", lambda e: calculate_change())  # Binding sedia ada

        # Change
        change_frame = ctk.CTkFrame(payment_detail_frame)
        change_frame.pack(fill="x", padx=5, pady=2)
        ctk.CTkLabel(change_frame, text="Baki:", font=LARGE_FONT).pack(side="left")
        label_change_value = ctk.CTkLabel(change_frame, 
                                        text="RM 0.00", 
                                        font=XTRALARGE_FONT, 
                                        text_color=TEXT_COLOR)
        label_change_value.pack(side="right")

        # Complete transaction button
        btn_selesai = ctk.CTkButton(payment_detail_frame, 
                                   text="Selesaikan Transaksi", 
                                   command=complete_transaction,
                                   fg_color="#32CD32", 
                                   font=XTRALARGE_FONT, 
                                   height=30)
        btn_selesai.pack(fill="x", pady=2)

        # Action buttons frame
        button_frame = ctk.CTkFrame(right_frame)
        button_frame.pack(fill="x", pady=10)

        # Create action buttons
        def create_safe_button(text, bg_color, fg_color, command):
            try:
                return ctk.CTkButton(
                    button_frame,
                    text=text,
                    command=command,
                    fg_color=bg_color,
                    text_color=fg_color,
                    font=MEDIUM_FONT,
                    height=30,
                    width=60
                )
            except Exception as e:
                print(f"Error creating button {text}: {e}")
                return None

        buttons = [
            ("Cari Produk", "#FFD700", "black", open_search_product),
            ("Hapus Produk", "#FF6347", "white", remove_item),
            ("Buka Laci", "#4169E1", "white", open_cash_drawer)
         #   ("Info Shift", "#2E8B57", "white", lambda: show_shift_details(user_id))
        ]

        for text, bg, fg, command in buttons:
            btn = create_safe_button(text, bg, fg, command)
            if btn:
                btn.pack(side="left", padx=2, fill="x", expand=True)

        # Di bagian button_frame (setelah tombol Info Shift)
        ctk.CTkButton(
            button_frame,
            text="Tutup Shift",
            command=lambda: show_cash_end_form(user_id),
            fg_color="#dc3545",
            font=MEDIUM_FONT,
            height=30,
            width=60
        ).pack(side="left", padx=2, fill="x", expand=True)

        # Exit button
        exit_button_frame = ctk.CTkFrame(right_frame)  # Gunakan right_frame yang sudah ada
        exit_button_frame.pack(fill="x", pady=(10, 5))  # Sesuaikan padding

        btn_keluar = ctk.CTkButton(
        exit_button_frame, 
        text="Keluar", 
        command=logout,
        fg_color="#FF4500", 
        font=LARGE_FONT, 
        height=60
        )
        btn_keluar.pack(fill="x", pady=1)

        # Load initial data
        try:
            load_today_sales()
        except Exception as e:
            print(f"Error loading sales data: {str(e)}")
            messagebox.showerror("Error", f"Gagal memuat data penjualan: {str(e)}")

        cashier_dashboard.after(1000, update_shift_display)
        cashier_dashboard.mainloop()

    except Exception as e:
        messagebox.showerror("Error", f"Gagal memulai dashboard kasir: {str(e)}")
        print(f"Error in cashier dashboard: {str(e)}")
        if 'cashier_dashboard' in globals() and cashier_dashboard:
            try:
                cashier_dashboard.destroy()
            except:
                pass
        if 'root' in globals() and root and root.winfo_exists():
            root.deiconify()

def load_low_stock_products(tree):
    """Muat produk yang stok hampir habis atau sudah habis"""
    try:
        # Kosongkan treeview
        for item in tree.get_children():
            tree.delete(item)
            
        # Dapatkan data dari API
        response = requests.get(f"{API_URL}?action=get_low_stock_products", timeout=5)
        data = response.json()
        
        if data.get('status') == 'success':
            for idx, product in enumerate(data.get('products', []), start=1):
                # Tentukan status berdasarkan stok
                stock = int(product.get('stock', 0))
                if stock <= 0:
                    status = "HABIS"
                    tags = ('out-of-stock',)
                elif stock <= 5:  # Threshold stok rendah
                    status = "KRITIKAL"
                    tags = ('low-stock',)
                else:
                    continue  # Skip produk dengan stok cukup
                
                # Insert data ke treeview
                tree.insert("", "end", values=(
                    idx,
                    product.get('name', ''),
                    stock,
                    status
                ), tags=tags)
            
        else:
            messagebox.showerror("Error", data.get('message', 'Gagal memuat data stok'))
            
    except Exception as e:
        messagebox.showerror("Error", f"Gagal memuat stok produk:\n{str(e)}")

def show_restock_form(item_id=None, product_name=None, current_stock=None, barcode=None, last_price=0):
    """Tampilkan form untuk melakukan restock produk"""
    restock_window = ctk.CTkToplevel()
    restock_window.title("Form Restock Produk")
    restock_window.geometry("500x600")
    restock_window.transient(cashier_dashboard)
    restock_window.grab_set()
    
    # Frame utama
    main_frame = ctk.CTkFrame(restock_window)
    main_frame.pack(pady=20, padx=20, fill="both", expand=True)
    
    # Judul
    title = "Restock Produk" if item_id else "Restock Produk Baru"
    ctk.CTkLabel(main_frame, text=title, font=("Arial", 16, "bold")).pack(pady=10)
    
    # Info Produk
    info_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
    info_frame.pack(fill="x", pady=10)
    
    if item_id:
        # Tampilkan info produk yang akan di-restock
        ctk.CTkLabel(info_frame, text="Nama Produk:", font=MEDIUM_FONT).pack(anchor="w")
        ctk.CTkLabel(info_frame, text=product_name, font=("Arial", 14)).pack(anchor="w", pady=5)
        
        ctk.CTkLabel(info_frame, text="Barcode:", font=MEDIUM_FONT).pack(anchor="w")
        ctk.CTkLabel(info_frame, text=barcode if barcode else "-", font=("Arial", 14)).pack(anchor="w", pady=5)
        
        ctk.CTkLabel(info_frame, text="Stok Saat Ini:", font=MEDIUM_FONT).pack(anchor="w")
        ctk.CTkLabel(info_frame, text=str(current_stock), font=("Arial", 14)).pack(anchor="w", pady=5)
    
    
    # Frame form restock
    form_frame = ctk.CTkFrame(restock_window)
    form_frame.pack(pady=10, padx=10, fill="x")
    
    ctk.CTkLabel(form_frame, text="Data Restock", font=("Arial", 14, "bold")).pack(pady=5)
    
    # Supplier
    ctk.CTkLabel(form_frame, text="Supplier:").pack(anchor="w")
    supplier_combobox = ttk.Combobox(form_frame, state="readonly")
    supplier_combobox.pack(fill="x", pady=5)
    
    # Jumlah Restock
    ctk.CTkLabel(form_frame, text="Jumlah Restock:").pack(anchor="w")
    entry_quantity = ctk.CTkEntry(form_frame, placeholder_text="Contoh: 10")
    entry_quantity.pack(fill="x", pady=5)
    
    # Harga Beli
    ctk.CTkLabel(form_frame, text="Harga Beli (RM):").pack(anchor="w")
    entry_price = ctk.CTkEntry(form_frame, placeholder_text="Contoh: 5.50")
    entry_price.pack(fill="x", pady=5)
    
    # No Invoice
    ctk.CTkLabel(form_frame, text="No. Invoice:").pack(anchor="w")
    entry_invoice = ctk.CTkEntry(form_frame)
    entry_invoice.pack(fill="x", pady=5)
    
    # Catatan
    ctk.CTkLabel(form_frame, text="Catatan:").pack(anchor="w")
    entry_notes = ctk.CTkEntry(form_frame)
    entry_notes.pack(fill="x", pady=5)
    
    # Tombol
    button_frame = ctk.CTkFrame(restock_window, fg_color="transparent")
    button_frame.pack(pady=10)
    
    def submit_restock():
        try:
            quantity = int(entry_quantity.get())
            if quantity <= 0:
                raise ValueError("Jumlah restock harus lebih dari 0")
                
            selected_supplier = supplier_combobox.get()
            supplier_id = None
            for s in suppliers:
                if s['supplier_name'] == selected_supplier:
                    supplier_id = s['id']
                    break
            
            if not supplier_id:
                raise ValueError("Pilih supplier terlebih dahulu")
            
            restock_data = {
                'action': 'restock_product',
                'item_id': item_id,
                'quantity': quantity,
                'supplier_id': supplier_id,
                'price_cost': float(entry_price.get()) if entry_price.get() else 0,
                'invoice_no': entry_invoice.get(),
                'notes': entry_notes.get(),
                'user_id': 1  # Ganti dengan user_id yang sesuai
            }
            
            response = requests.post(API_URL, json=restock_data)
            result = response.json()
            
            if result.get('status') == 'success':
                messagebox.showinfo("Berhasil", "Restock berhasil dilakukan")
                restock_window.destroy()
                # Refresh tampilan stok jika perlu
            else:
                messagebox.showerror("Gagal", result.get('message', 'Gagal melakukan restock'))
                
        except ValueError as e:
            messagebox.showerror("Input Tidak Valid", str(e))
        except Exception as e:
            messagebox.showerror("Error", f"Terjadi kesalahan: {str(e)}")
    
    btn_submit = ctk.CTkButton(
        button_frame, 
        text="Submit", 
        command=submit_restock,
        fg_color="#28a745"
    )
    btn_submit.pack(side="left", padx=5)
    
    btn_cancel = ctk.CTkButton(
        button_frame,
        text="Batal",
        command=restock_window.destroy,
        fg_color="#dc3545"
    )
    btn_cancel.pack(side="right", padx=5)
    
    # Load data produk
    def load_product_data():
        try:
            # Define product_data dictionary to store product info variables
            product_data = {
                'name': tk.StringVar(),
                'barcode': tk.StringVar(),
                'current_stock': tk.StringVar()
            }
            params = {'action': 'get_product_for_restock', 'item_id': item_id}
            response = requests.get(API_URL, params=params)
            data = response.json()
            
            if data.get('status') == 'success':
                product = data['data']['product']
                product_data['name'].set(product['item_name'])
                product_data['barcode'].set(product['barcode_per_unit'] or "-")
                product_data['current_stock'].set(str(data['data']['stock']))
                
                global suppliers
                suppliers = data['data']['suppliers']
                supplier_combobox['values'] = [s['supplier_name'] for s in suppliers]
                if suppliers:
                    supplier_combobox.current(0)
                
                if data['data']['last_price']:
                    entry_price.insert(0, str(data['data']['last_price']['supplier_price_unit']))
            else:
                messagebox.showerror("Error", data.get('message', 'Gagal memuat data produk'))
        except Exception as e:
            messagebox.showerror("Error", f"Gagal memuat data: {str(e)}")
    
    load_product_data()

def add_restock_button_to_low_stock():
    """Tambahkan tombol restock dan fungsi double click ke treeview stok kritikal"""
    # Pastikan frame sudah didefinisikan
    if 'low_stock_frame' not in globals():
        return
    
    # Frame untuk tombol
    btn_frame = ctk.CTkFrame(low_stock_frame)
    btn_frame.pack(fill="x", pady=5, padx=5)
    
    # Tombol Restock Produk Baru
    ctk.CTkButton(
        btn_frame,
        text="Restock Produk Baru",
        command=lambda: show_restock_form(),
        fg_color="#28a745",
        hover_color="#218838",
        font=MEDIUM_FONT,
        height=40
    ).pack(side="left", padx=5, fill="x", expand=True)
    
    # Tombol Refresh
    ctk.CTkButton(
        btn_frame,
        text="Refresh Data",
        command=lambda: load_low_stock_products(tree_low_stock),
        fg_color="#17a2b8",
        hover_color="#138496",
        font=MEDIUM_FONT,
        height=40
    ).pack(side="right", padx=5)
    
    # Binding double click
    tree_low_stock.bind("<Double-1>", on_low_stock_double_click)

def on_low_stock_double_click(event):
    """Handle double click pada item stok kritikal"""
    selected_item = tree_low_stock.focus()
    if not selected_item:
        return
        
    try:
        # Dapatkan nilai dari item yang dipilih
        item_values = tree_low_stock.item(selected_item, 'values')
        
        if len(item_values) < 3:
            messagebox.showwarning("Peringatan", "Data produk tidak lengkap")
            return
            
        product_name = item_values[1]
        current_stock = item_values[2]
        
        # Dapatkan detail produk dari API
        params = {'action': 'get_product_by_name', 'name': product_name}
        response = requests.get(API_URL, params=params, timeout=5)
        response.raise_for_status()  # Ini akan raise exception jika status code bukan 200
        
        data = response.json()
        
        if data.get('status') != 'success':
            raise Exception(data.get('message', 'Gagal mendapatkan detail produk'))
            
        product = data.get('data', {})
        if not product:
            raise Exception("Data produk tidak ditemukan")
            
        # Tampilkan form restock dengan data produk
        show_restock_form(
            item_id=product['id'],
            product_name=product_name,
            current_stock=current_stock,
            barcode=product.get('barcode', ''),
            last_price=product.get('price', 0)
        )
        
    except requests.exceptions.RequestException as e:
        messagebox.showerror("Error", f"Gagal terhubung ke server: {str(e)}")
    except Exception as e:
        messagebox.showerror("Error", f"Gagal memuat detail produk:\n{str(e)}")

def show_restock_form(item_id=None, product_name=None, current_stock=None, barcode=None, last_price=0):
    """Tampilkan form untuk melakukan restock produk"""
    restock_window = ctk.CTkToplevel()
    restock_window.title("Form Restock Produk")
    restock_window.geometry("500x600")
    restock_window.transient(cashier_dashboard)
    restock_window.grab_set()
    
    # Frame utama
    main_frame = ctk.CTkFrame(restock_window)
    main_frame.pack(pady=20, padx=20, fill="both", expand=True)
    
    # Judul
    title = "Restock Produk" if item_id else "Restock Produk Baru"
    ctk.CTkLabel(main_frame, text=title, font=("Arial", 16, "bold")).pack(pady=10)
    
    # Info Produk
    info_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
    info_frame.pack(fill="x", pady=10)
    
    if item_id:
        # Tampilkan info produk yang akan di-restock
        ctk.CTkLabel(info_frame, text="Nama Produk:", font=MEDIUM_FONT).pack(anchor="w")
        ctk.CTkLabel(info_frame, text=product_name, font=("Arial", 14)).pack(anchor="w", pady=5)
        
        ctk.CTkLabel(info_frame, text="Barcode:", font=MEDIUM_FONT).pack(anchor="w")
        ctk.CTkLabel(info_frame, text=barcode if barcode else "-", font=("Arial", 14)).pack(anchor="w", pady=5)
        
        ctk.CTkLabel(info_frame, text="Stok Saat Ini:", font=MEDIUM_FONT).pack(anchor="w")
        ctk.CTkLabel(info_frame, text=str(current_stock), font=("Arial", 14)).pack(anchor="w", pady=5)
    
    # Form Restock
    form_frame = ctk.CTkFrame(main_frame)
    form_frame.pack(fill="x", pady=10)
    
    # Supplier
    ctk.CTkLabel(form_frame, text="Supplier:", font=MEDIUM_FONT).pack(anchor="w", pady=(5,0))
    supplier_combobox = ttk.Combobox(form_frame, font=MEDIUM_FONT, state="readonly")
    supplier_combobox.pack(fill="x", pady=5)
    
    # Jumlah Restock
    ctk.CTkLabel(form_frame, text="Jumlah Restock:", font=MEDIUM_FONT).pack(anchor="w", pady=(5,0))
    quantity_entry = ctk.CTkEntry(form_frame, font=MEDIUM_FONT)
    quantity_entry.pack(fill="x", pady=5)
    quantity_entry.insert(0, "1")
    
    # Harga Beli
    ctk.CTkLabel(form_frame, text="Harga Beli (RM):", font=MEDIUM_FONT).pack(anchor="w", pady=(5,0))
    price_entry = ctk.CTkEntry(form_frame, font=MEDIUM_FONT)
    price_entry.pack(fill="x", pady=5)
    price_entry.insert(0, str(last_price))
    
    # No Invoice
    ctk.CTkLabel(form_frame, text="No. Invoice:", font=MEDIUM_FONT).pack(anchor="w", pady=(5,0))
    invoice_entry = ctk.CTkEntry(form_frame, font=MEDIUM_FONT)
    invoice_entry.pack(fill="x", pady=5)
    
    # Catatan
    ctk.CTkLabel(form_frame, text="Catatan:", font=MEDIUM_FONT).pack(anchor="w", pady=(5,0))
    notes_entry = ctk.CTkEntry(form_frame, font=MEDIUM_FONT)
    notes_entry.pack(fill="x", pady=5)
    
    # Tombol Aksi
    button_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
    button_frame.pack(pady=10)
    
    def submit_restock():
        try:
            # Validasi input
            quantity = int(quantity_entry.get())
            if quantity <= 0:
                raise ValueError("Jumlah restock harus lebih dari 0")
                
            price = float(price_entry.get()) if price_entry.get() else 0
            if price < 0:
                raise ValueError("Harga tidak boleh negatif")
                
            # Dapatkan supplier_id dari combobox
            supplier_name = supplier_combobox.get()
            supplier_id = None
            for s in suppliers:
                if s['supplier_name'] == supplier_name:
                    supplier_id = s['id']
                    break
            
            if not supplier_id:
                raise ValueError("Pilih supplier terlebih dahulu")
            
            # Siapkan data restock
            restock_data = {
                'action': 'restock_product',
                'item_id': item_id,
                'quantity': quantity,
                'supplier_id': supplier_id,
                'price_cost': price,
                'invoice_no': invoice_entry.get(),
                'notes': notes_entry.get(),
                'user_id': current_user_id  # Pastikan ini tersedia
            }
            
            # Kirim ke API
            response = requests.post(API_URL, json=restock_data, timeout=5)
            result = response.json()
            
            if result.get('status') == 'success':
                messagebox.showinfo("Berhasil", "Restock berhasil dilakukan")
                restock_window.destroy()
                # Refresh daftar stok kritikal
                load_low_stock_products(tree_low_stock)
            else:
                messagebox.showerror("Gagal", result.get('message', 'Gagal melakukan restock'))
                
        except ValueError as e:
            messagebox.showwarning("Input Tidak Valid", str(e))
        except Exception as e:
            messagebox.showerror("Error", f"Terjadi kesalahan: {str(e)}")
    
    ctk.CTkButton(
        button_frame,
        text="Submit",
        command=submit_restock,
        fg_color="#28a745",
        hover_color="#218838",
        font=MEDIUM_FONT,
        width=120
    ).pack(side="left", padx=10)
    
    ctk.CTkButton(
        button_frame,
        text="Batal",
        command=restock_window.destroy,
        fg_color="#dc3545",
        hover_color="#c82333",
        font=MEDIUM_FONT,
        width=120
    ).pack(side="right", padx=10)
    
    # Load data supplier
    def load_suppliers():
        try:
            params = {'action': 'get_suppliers'}
            response = requests.get(API_URL, params=params, timeout=5)
            data = response.json()
            
            if data.get('status') == 'success':
                global suppliers
                suppliers = data.get('data', [])
                supplier_combobox['values'] = [s['supplier_name'] for s in suppliers]
                if suppliers:
                    supplier_combobox.current(0)
            else:
                messagebox.showerror("Error", data.get('message', 'Gagal memuat data supplier'))
        except Exception as e:
            messagebox.showerror("Error", f"Gagal memuat supplier: {str(e)}")
    
    load_suppliers()
    
def on_low_stock_double_click(event):
    """Handle double click pada item stok kritikal"""
    selected_item = tree_low_stock.focus()
    if not selected_item:
        return
        
    item_values = tree_low_stock.item(selected_item, 'values')
    if len(item_values) >= 3:
        product_name = item_values[1]
        current_stock = item_values[2]
        
        try:
            params = {'action': 'get_product_by_name', 'name': product_name}
            response = requests.get(API_URL, params=params, timeout=5)
            product = response.json().get('data', {})
            
            if product:
                show_restock_form(
                    product_id=product['id'],
                    product_name=product_name,
                    current_stock=current_stock
                )
        except Exception as e:
            messagebox.showerror("Error", f"Gagal mendapatkan detail produk: {str(e)}")
            
def show_shift_details(user_id):
    try:
        # Get shift data from API
        params = {'action': 'get_shift_details', 'user_id': user_id}
        response = requests.get(API_URL, params=params, timeout=5)
        data = response.json()

        if data.get('status') != 'success':
            raise Exception(data.get('message', 'Gagal mendapatkan data shift'))
        
        shift_data = data['shift_data']
        
        # Create details window
        detail_window = ctk.CTkToplevel()
        detail_window.title("Maklumat Shift")
        detail_window.geometry("400x350")
        detail_window.resizable(False, False)
        
        # Display shift information
        info_frame = ctk.CTkFrame(detail_window)
        info_frame.pack(pady=20, padx=20, fill="both", expand=True)
        
        details = [
            ("Mula Shift:", shift_data['shift_start']),
            ("Tempoh:", shift_data.get('duration', '00:00:00')),
            ("Cash Awal:", f"RM {float(shift_data['cash_start']):.2f}"),
            ("Transaksi Tunai:", f"RM {float(shift_data.get('total_cash_transactions', 0)):.2f}"),
            ("Cash Semasa:", f"RM {float(shift_data['cash_end']):.2f}")
        ]
        
        for label, value in details:
            row = ctk.CTkFrame(info_frame, fg_color="transparent")
            row.pack(fill="x", pady=5)
            ctk.CTkLabel(row, text=label, font=("Arial", 14), width=150, anchor="w").pack(side="left")
            ctk.CTkLabel(row, text=value, font=("Arial", 14, "bold")).pack(side="right")
        
        # Close button
        btn_close = ctk.CTkButton(
            info_frame,
            text="Tutup",
            command=detail_window.destroy,
            fg_color="#6c757d",
            font=("Arial", 14)
        )
        btn_close.pack(pady=10)
        
    except Exception as e:
        messagebox.showerror("Error", f"Gagal memuat maklumat shift:\n{str(e)}")

def check_shift(user_id):
    try:
        params = {'action': 'check_shift', 'user_id': user_id}
        response = requests.get(API_URL, params=params, timeout=5)
        data = response.json()
        
        if data.get('status') == 'success':
            return data.get('has_shift', False), data.get('shift_data', {})
        return False, {}
        
    except Exception as e:
        print(f"Error checking shift: {str(e)}")
        return False, {}
    
# ===================== MAIN PROGRAM =====================
if __name__ == "__main__":
    try:
        # Initialize the login window
        login_window = create_login_window()
        
        # Start the main event loop
        login_window.mainloop()
        
    except Exception as e:
        print(f"Error starting application: {str(e)}")
        import traceback
        traceback.print_exc()
        input("Press Enter to exit...")
