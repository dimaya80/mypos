import tkinter as tk
from tkinter import ttk, messagebox
import customtkinter as ctk
import requests
import serial
import serial.tools.list_ports
import time
import threading
from datetime import datetime

# === PATCH: Printer Support (USB/Serial) ===
try:
    import win32print
except ImportError:
    win32print = None

API_URL = "http://127.0.0.1/api/api.php"
PRIMARY_COLOR = "#2B7A78"

def auto_sync():
    while True:
        try:
            print("🔄 Auto‑sync bermula...")

            r1 = requests.get("http://127.0.0.1/api/sync_push.php", timeout=60)
            print("➡️ Push Response:", r1.status_code, r1.text.strip())

            r2 = requests.get("http://127.0.0.1/api/sync_pull.php", timeout=60)
            print("⬅️ Pull Response:", r2.status_code, r2.text.strip())

            print("✅ Auto‑sync selesai. Tunggu 30 saat...\n")

        except requests.exceptions.RequestException as e:
            print("❌ Auto‑sync error:", str(e))

        time.sleep(60)
        
def print_usb_receipt(receipt_text, printer_name=None):
    if not win32print:
        messagebox.showerror("Printer Error", "pywin32 tidak dipasang. Tidak boleh print ke printer USB/Windows.")
        return
    if not printer_name:
        printer_name = win32print.GetDefaultPrinter()
    hprinter = win32print.OpenPrinter(printer_name)
    try:
        hjob = win32print.StartDocPrinter(hprinter, 1, ("MyPOS Receipt", None, "RAW"))
        win32print.StartPagePrinter(hprinter)
        win32print.WritePrinter(hprinter, receipt_text.encode('utf-8'))
        win32print.EndPagePrinter(hprinter)
        win32print.EndDocPrinter(hprinter)
    finally:
        win32print.ClosePrinter(hprinter)

def select_windows_printer(master):
    if not win32print:
        messagebox.showerror("Printer Error", "pywin32 tidak dipasang.")
        return None
    printers = [p[2] for p in win32print.EnumPrinters(win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS)]
    if not printers:
        messagebox.showwarning("Tiada Printer", "Tiada printer Windows dikesan!", parent=master)
        return None
    # Simple popup select printer (basic)
    win = tk.Toplevel(master)
    win.title("Pilih Printer")
    win.geometry("350x160")
    tk.Label(win, text="Pilih printer Windows:", font=("Arial", 12)).pack(pady=10)
    printer_var = tk.StringVar(value=printers[0])
    listbox = tk.Listbox(win, listvariable=tk.StringVar(value=printers), height=6)
    listbox.pack(padx=8)
    def on_ok():
        sel = listbox.curselection()
        if sel:
            printer_var.set(printers[sel[0]])
        win.destroy()
    tk.Button(win, text="OK", command=on_ok, width=12, bg="#32CD32", fg="white").pack(pady=8)
    win.transient(master)
    win.grab_set()
    win.wait_window()
    return printer_var.get()

# ========== VIRTUAL KEYBOARD CTK ==========
class CTkVirtualKeyboard(ctk.CTkToplevel):
    last_target_entry = None

    def __init__(self, master):
        super().__init__(master)
        self.title("Virtual Keyboard")
        self.resizable(False, False)
        self.configure(fg_color="#222831")
        self.attributes('-topmost', True)
        self.protocol("WM_DELETE_WINDOW", self.destroy)

        # QWERTY rows (kiri)
        qwerty_rows = [
            ['Q','W','E','R','T','Y','U','I','O','P'],
            ['A','S','D','F','G','H','J','K','L'],
            ['Z','X','C','V','B','N','M']
        ]
        # Numpad (kanan)
        numpad_keys = [
            ['1','2','3'],
            ['4','5','6'],
            ['7','8','9']
        ]

        # Lukis QWERTY dan numpad
        for r in range(3):
            # QWERTY kiri
            for c, key in enumerate(qwerty_rows[r]):
                btn = ctk.CTkButton(
                    self, text=key, width=50, height=50, fg_color="#393e46",
                    text_color="#eeeeee", font=("Arial", 18, "bold"),
                    command=lambda k=key: self.press(k)
                )
                btn.grid(row=r, column=c, padx=2, pady=2)
            # Numpad kanan (offset kanan, grid dari col 12)
            col_offset = 12
            for nc, nkey in enumerate(numpad_keys[r]):
                btn = ctk.CTkButton(
                    self, text=nkey, width=50, height=50, fg_color="#393e46",
                    text_color="#eeeeee", font=("Arial", 18, "bold"),
                    command=lambda k=nkey: self.press(k)
                )
                btn.grid(row=r, column=col_offset+nc, padx=2, pady=2)

        # Baris bawah (special keys)
        r = 3
        # Space (span 3)
        btn_space = ctk.CTkButton(
            self, text='Space', width=170, height=50, fg_color="#393e46",
            text_color="#eeeeee", font=("Arial", 18, "bold"),
            command=lambda k=' ': self.press(k)
        )
        btn_space.grid(row=r, column=0, columnspan=3, padx=2, pady=2, sticky='ew')

        # Enter (span 2)
        btn_enter = ctk.CTkButton(
            self, text='Enter', width=110, height=50, fg_color="#00adb5",
            text_color="#eeeeee", font=("Arial", 18, "bold"),
            command=self.press_enter
        )
        btn_enter.grid(row=r, column=3, columnspan=2, padx=2, pady=2, sticky='ew')

        # Kosongkan tengah (col 5-10)
        # 0
        btn_0 = ctk.CTkButton(
            self, text='0', width=50, height=50, fg_color="#393e46",
            text_color="#eeeeee", font=("Arial", 18, "bold"),
            command=lambda k='0': self.press(k)
        )
        btn_0.grid(row=r, column=12, padx=2, pady=2)
        # .
        btn_dot = ctk.CTkButton(
            self, text='.', width=50, height=50, fg_color="#222831",
            text_color="#FFD700", font=("Arial", 18, "bold"),
            command=lambda k='.': self.special_press('.')
        )
        btn_dot.grid(row=r, column=13, padx=2, pady=2)
        # Back
        btn_back = ctk.CTkButton(
            self, text='Back', width=50, height=50, fg_color="#393e46",
            text_color="#00adb5", font=("Arial", 18, "bold"),
            command=lambda k='Back': self.press(k)
        )
        btn_back.grid(row=r, column=14, padx=2, pady=2)
        # F1
        btn_f1 = ctk.CTkButton(
            self, text='F1', width=50, height=50, fg_color="#222831",
            text_color="#00adb5", font=("Arial", 18, "bold"),
            command=lambda k='F1': self.special_press('F1')
        )
        btn_f1.grid(row=r, column=15, padx=2, pady=2)
        # F2
        btn_f2 = ctk.CTkButton(
            self, text='F2', width=50, height=50, fg_color="#222831",
            text_color="#00adb5", font=("Arial", 18, "bold"),
            command=lambda k='F2': self.special_press('F2')
        )
        btn_f2.grid(row=r, column=16, padx=2, pady=2)
        # F5
        btn_f5 = ctk.CTkButton(
            self, text='F5', width=50, height=50, fg_color="#222831",
            text_color="#00adb5", font=("Arial", 18, "bold"),
            command=lambda k='F5': self.special_press('F5')
        )
        btn_f5.grid(row=r, column=17, padx=2, pady=2)

    @classmethod
    def set_target_entry(cls, entry):
        cls.last_target_entry = entry

    def press(self, key):
        entry = CTkVirtualKeyboard.last_target_entry
        if not entry:
            return
        if key == 'Back':
            try:
                current = entry.get()
                if len(current) > 0:
                    entry.delete(len(current)-1, 'end')
            except Exception:
                pass
        else:
            try:
                entry.insert('end', key)
            except Exception:
                pass

    def special_press(self, key):
        entry = CTkVirtualKeyboard.last_target_entry
        if not entry:
            return
        if key == '.':
            try:
                entry.insert('end', '.')
            except Exception:
                pass
        elif key in ('F1', 'F2', 'F5'):
            entry.event_generate(f'<KeyPress-{key}>')

    def press_enter(self):
        entry = CTkVirtualKeyboard.last_target_entry
        if not entry:
            return
        try:
            entry.event_generate('<Return>')
        except Exception:
            pass

# ========== FUNGSI AMBIL MAKLUMAT KEDAI DARI API ==========
def get_store_info():
    try:
        response = requests.get(f"{API_URL}?action=get_store_info", timeout=5)
        if response.status_code == 200:
            data = response.json()
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
        raise Exception("Gagal dapatkan maklumat kedai")
    except Exception as e:
        messagebox.showerror("Error", f"Gagal dapatkan info kedai: {str(e)}")
        return {
            'store_name': 'NAMA KEDAI TIDAK DITEMUI',
            'address': '-',
            'phone': '-'
        }

# ========== PRINT RESIT & BUKA LACI ==========
import win32api
def print_receipt(
    items,
    total,
    amount_paid,
    payment_method,
    customer_info=None,
    discount=0,
    tax=0,
    receipt_no=None,
    sale_date=None
):
    try:
        store_info = get_store_info()
        if not receipt_no:
            receipt_no = "INV" + datetime.now().strftime("%Y%m%d%H%M%S")
        if not sale_date:
            sale_date = datetime.now()
        elif isinstance(sale_date, str):
            try:
                sale_date = datetime.strptime(sale_date, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                sale_date = datetime.now()

        LEBAR = 48
        receipt_lines = [
            "\x1B\x40",         # Initialize
            "\x1B\x21\x20",     # Font B, bold
            "\x1B\x61\x01",     # Center
            f"{store_info['store_name']}\n",
            f"{store_info['address']}\n",
            f"{store_info['phone']}\n",
            "\x1B\x21\x00",     # Normal font
            "\x1B\x61\x00",     # Left align
            "=" * LEBAR + "\n",
            f"Tarikh: {sale_date.strftime('%d/%m/%Y %H:%M:%S')}\n",
            f"No Resit: {receipt_no}\n",
            "-" * LEBAR + "\n",
            f"{'Perkara':<20}{'Qty':>6}{'Harga':>10}{'Jumlah':>12}\n",
            "-" * LEBAR + "\n"
        ]

        for item in items:
            name = item['name'][:20]
            quantity = float(item['quantity'])
            price = float(item['price'])
            item_total = float(item['total'])
            qty_str = f"{quantity:.3f}" if quantity != int(quantity) else f"{int(quantity)}"
            price_str = f"{price:.2f}"
            total_str = f"{item_total:.2f}"
            receipt_lines.append(
                f"{name:<20}{qty_str:>6}{price_str:>10}{total_str:>12}\n"
            )

        subtotal = sum(float(item['total']) for item in items)
        total_after_discount = subtotal - discount
        grand_total = total_after_discount + tax
        change = amount_paid - grand_total

        receipt_lines.extend([
            "-" * LEBAR + "\n",
            f"{'Subtotal:':<30}{subtotal:>18.2f}\n",
            f"{'Diskaun:':<30}{discount:>18.2f}\n",
            f"{'Cukai:':<30}{tax:>18.2f}\n",
            f"{'Dibayar:':<30}{amount_paid:>18.2f}\n",
            f"{'Baki Kembali:':<30}{change:>18.2f}\n",
            f"{'Total:':<30}{grand_total:>18.2f}\n",
            "=" * LEBAR + "\n",
            f"Kaedah Pembayaran: {payment_method}\n",
            "=" * LEBAR + "\n",
            "\x1B\x61\x01",
            "Terima kasih atas kunjungan Anda\n",
            "Barang yang sudah dibeli tidak boleh ditukar\n",
            "\x1B\x61\x00",
            "=" * LEBAR + "\n"
        ])

        # ========== CETAK BARCODE DI BAWAH RESIT ==========
        barcode_data = receipt_no
        # Center
        receipt_lines.append("\x1B\x61\x01")
        # Set barcode height (80 px)
        receipt_lines.append("\x1D\x68\x50")
        # Set barcode width (2)
        receipt_lines.append("\x1D\x77\x02")
        # Print CODE128 barcode (ESC/POS)
        # Format: \x1D\x6B\x49[length][data]
        receipt_lines.append(f"\x1D\x6B\x49{chr(len(barcode_data))}{barcode_data}\n")
        # Back to left
        receipt_lines.append("\x1B\x61\x00")
        # ========== POTONG KERTAS ==========
        receipt_lines.append("\n\n\n\x1D\x56\x41\x03")

        receipt_text = "".join(receipt_lines)
        port = SELECTED_PRINTER_PORT or detect_thermal_printer_serial()
        # PATCH: Cuba serial dulu, kalau gagal cuba printer Windows/USB (pywin32)
        printed = False
        if port:
            try:
                import serial
                with serial.Serial(port, baudrate=9600, timeout=1) as printer:
                    printer.write(receipt_text.encode('utf-8'))
                    time.sleep(0.5)
                printed = True
            except Exception as e:
                messagebox.showerror("Printer Error", f"Gagal mencetak ke printer {port}:\n{str(e)}\nMencuba printer USB/Windows...")
        if not printed:
            # Cuba print ke printer Windows/USB
            try:
                # Pilih printer Windows (jika mahu popup, boleh enum dulu)
                printer_name = win32print.GetDefaultPrinter()
                # Kalau nak popup/ubah printer, boleh guna win32print.EnumPrinters
                hprinter = win32print.OpenPrinter(printer_name)
                try:
                    hjob = win32print.StartDocPrinter(hprinter, 1, ("MyPOS Receipt", None, "RAW"))
                    win32print.StartPagePrinter(hprinter)
                    win32print.WritePrinter(hprinter, receipt_text.encode('utf-8'))
                    win32print.EndPagePrinter(hprinter)
                    win32print.EndDocPrinter(hprinter)
                    printed = True
                    messagebox.showinfo("Printer", f"Resit telah dicetak ke printer Windows: {printer_name}")
                finally:
                    win32print.ClosePrinter(hprinter)
            except Exception as e:
                messagebox.showerror("Printer Error", f"Thermal printer serial & Windows/USB tidak dijumpai/gagal print:\n{str(e)}")
                print(receipt_text)
                return False
        return printed
    except Exception as e:
        messagebox.showerror("Error", f"Error saat mencetak:\n{str(e)}")
        return False

def open_cash_drawer():
    port = detect_thermal_printer_serial()
    if not port:
        messagebox.showerror("Printer Error", "Thermal printer serial tidak dijumpai!")
        return
    try:
        ser = serial.Serial(port, baudrate=9600, timeout=1)
        time.sleep(2)
        ser.write(b'\x1B\x70\x00\x19\xFA')
        ser.close()
        messagebox.showinfo("Berjaya", "Laci wang berjaya dibuka!")
    except Exception as e:
        messagebox.showerror("Error", f"Gagal membuka laci wang: {e}")

shift_popup_open = False
main_root = None

def show_login_window():
    root = tk.Tk()
    root.title("My POS System - Login")
    root.geometry("400x400")
    root.resizable(False, False)

    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")

    frame = ctk.CTkFrame(root)
    frame.pack(pady=50, padx=20, fill="both", expand=True)

    ctk.CTkLabel(frame, text="KAK NAH KEDAI RUNCIT", font=("Arial", 20, "bold")).pack(pady=20)
    ctk.CTkLabel(frame, text="Username:").pack()

    entry_username = ctk.CTkEntry(frame)
    entry_username.pack()
    entry_username.focus()

    ctk.CTkLabel(frame, text="Password:").pack()
    entry_password = ctk.CTkEntry(frame, show="*")
    entry_password.pack()

    def login():
        username = entry_username.get().strip()
        password = entry_password.get().strip()
        if not username or not password:
            messagebox.showwarning("Peringatan", "Username dan password wajib diisi!", parent=root)
            return

        try:
            response = requests.post(API_URL, json={
                "action": "login",
                "username": username,
                "password": password
            }, timeout=5)

            result = response.json()
            if result.get("status") == "success":
                user_id = result["user"]["id"]
                root.withdraw()  # SEMBUNYIKAN window login
                check_or_start_shift(user_id, root)
            else:
                messagebox.showerror("Login Gagal", result.get("message", "Login gagal"), parent=root)
        except Exception as e:
            messagebox.showerror("Error", f"Gagal login: {str(e)}", parent=root)

    ctk.CTkButton(frame, text="Login", command=login, fg_color=PRIMARY_COLOR).pack(pady=20)
    root.bind('<Return>', lambda e: login())
    root.mainloop()

def check_or_start_shift(user_id, root_window):
    global shift_popup_open
    if shift_popup_open:
        return

    try:
        resp = requests.get(f"{API_URL}?action=check_shift&user_id={user_id}", timeout=5)
        data = resp.json()
        if data.get('status') == 'success' and data.get('has_shift'):
            # Terus ke dashboard
            root_window.destroy()
            open_cashier_dashboard(user_id)
        else:
            show_shift_start_modal(user_id, root_window)
    except Exception as e:
        messagebox.showerror("Ralat", f"Gagal semak shift: {str(e)}", parent=root_window)

def show_shift_start_modal(user_id, root_window):
    global shift_popup_open
    if shift_popup_open:
        return
    shift_popup_open = True

    win = ctk.CTkToplevel(master=root_window)
    win.title("Mula Shift")
    win.geometry("350x250")
    win.attributes('-topmost', True)

    ctk.CTkLabel(win, text="Shift belum bermula!", font=("Arial", 16, "bold")).pack(pady=10)
    ctk.CTkLabel(win, text="Masukkan Cash Awal (RM):").pack()

    entry_cash = ctk.CTkEntry(win)
    entry_cash.pack(pady=10)
    entry_cash.focus()

    def submit_start_shift():
        try:
            cash_awal = float(entry_cash.get())
            res = requests.post(API_URL, json={
                "action": "start_shift",
                "user_id": user_id,
                "cash_start": cash_awal
            }, timeout=10)
            data2 = res.json()
            if data2.get("status") == "success":
                messagebox.showinfo("Berjaya", "Shift bermula!", parent=win)
                win.destroy()
                root_window.destroy()
                global shift_popup_open
                shift_popup_open = False
                open_cashier_dashboard(user_id)
            else:
                raise Exception(data2.get("message", "Gagal mula shift!"))
        except Exception as e:
            messagebox.showerror("Ralat", f"Gagal mula shift: {e}", parent=win)

    def reset_shift_flag():
        global shift_popup_open
        shift_popup_open = False

    ctk.CTkButton(win, text="Mula Shift", command=submit_start_shift, fg_color="#32CD32").pack(pady=10)
    ctk.CTkButton(win, text="Batal", command=lambda: [win.destroy(), reset_shift_flag()]).pack(pady=5)

    win.transient(root_window)
    win.grab_set()
    win.protocol("WM_DELETE_WINDOW", lambda: [win.destroy(), reset_shift_flag()])
    win.wait_window()

def open_cashier_dashboard(user_id):
    dashboard = tk.Tk()
    dashboard.title("Sistem Kasir")
    dashboard.geometry("1600x900")
    dashboard.attributes("-fullscreen", True)

    # --- Flag untuk popup carian produk ---
    global search_popup_open
    search_popup_open = False
    global update_qty_popup_open
    update_qty_popup_open = False

    # HEADER BAR ATAS
    header_frame = ctk.CTkFrame(dashboard, height=54, fg_color="#205065")
    header_frame.pack(fill="x", side="top")
    ctk.CTkLabel(
        header_frame, text="MyPOS System v1.0",
        font=("Arial", 20, "bold"), text_color="white"
    ).pack(side="left", padx=20)
    label_shift_info = ctk.CTkLabel(
        header_frame,
        text="Shift: - | Cashier: - | Cash Awal: RM 0.00 | Baki Cash: RM 0.00",
        font=("Arial", 15, "bold"), text_color="#e6e6e6"
    )
    label_shift_info.pack(side="right", padx=20)
    def update_shift_info():
        try:
            resp = requests.get(f"{API_URL}?action=check_shift&user_id={user_id}", timeout=5)
            data = resp.json()
            if data.get('status') == 'success' and data.get('has_shift'):
                shift = data['shift_data']
                cashier = shift.get('cashier_name', '-') if shift.get('cashier_name') else '-'
                shift_start = shift.get('shift_start', '-') if shift.get('shift_start') else '-'
                cash_start = float(shift.get('cash_start', 0))
                cash_end = float(shift.get('cash_end', 0))
                info = (
                    f"Shift: {shift_start} | "
                    f"Cashier: {cashier} | "
                    f"Cash Awal: RM {cash_start:.2f} | "
                    f"Baki Cash: RM {cash_end:.2f}"
                )
            else:
                info = "Shift: - | Cashier: - | Cash Awal: RM 0.00 | Baki Cash: RM 0.00"
            label_shift_info.configure(text=info)
        except Exception as e:
            label_shift_info.configure(text="Shift Info: Tidak dapat hubung API")
        dashboard.after(10000, update_shift_info)
    update_shift_info()

    print_receipt_var = tk.BooleanVar(value=True)
    open_drawer_var = tk.BooleanVar(value=True)

    main = tk.Frame(dashboard)
    main.pack(fill="both", expand=True)
    main.columnconfigure(0, weight=2)
    main.columnconfigure(1, weight=3)
    main.rowconfigure(0, weight=1)

    left = tk.Frame(main)
    left.grid(row=0, column=0, sticky="nsew")
    scan_frame = ctk.CTkFrame(left)
    scan_frame.pack(fill="x", pady=10)
    ctk.CTkLabel(scan_frame, text="Scan Barcode:", font=("Arial", 18, "bold")).pack(side="left", padx=(8, 4))
    entry_barcode = ctk.CTkEntry(scan_frame, font=("Arial", 18, "bold"), width=220)
    entry_barcode.pack(side="left", padx=(4, 8))
    entry_barcode.focus_set()
    entry_barcode.bind("<FocusIn>", lambda e: CTkVirtualKeyboard.set_target_entry(entry_barcode))
    ctk.CTkCheckBox(scan_frame, text="Cetak Resit", variable=print_receipt_var, checkbox_height=22, checkbox_width=22, font=("Arial", 18, "bold")).pack(side="left", padx=(8, 6))
    ctk.CTkCheckBox(scan_frame, text="Buka Laci", variable=open_drawer_var, checkbox_height=22, checkbox_width=22, font=("Arial", 18, "bold")).pack(side="left", padx=(6, 4))

    notebook = ttk.Notebook(left)
    notebook.pack(fill="both", expand=True)
    cart_frame = tk.Frame(notebook)
    notebook.add(cart_frame, text="Troli Jualan")
    style = ttk.Style()
    style.theme_use("clam")
    style.configure("Cart.Treeview", font=("Arial", 18, "bold"), rowheight=38)
    style.configure("Cart.Treeview.Heading", font=("Arial", 18, "bold"))
    columns = ("ID", "Nama Produk", "Harga", "Kuantiti", "Total")
    tree_main = ttk.Treeview(cart_frame, columns=columns, show="headings", style="Cart.Treeview")
    tree_main.heading("ID", text="ID")
    tree_main.column("ID", width=30)
    tree_main.heading("Nama Produk", text="Nama Produk")
    tree_main.column("Nama Produk", width=250)
    tree_main.heading("Harga", text="Harga")
    tree_main.column("Harga", width=50)
    tree_main.heading("Kuantiti", text="Kuantiti")
    tree_main.column("Kuantiti", width=50)
    tree_main.heading("Total", text="Total")
    tree_main.column("Total", width=50)
    tree_main.pack(fill="both", expand=True, padx=10, pady=10)
    sales_frame = tk.Frame(notebook)
    notebook.add(sales_frame, text="Jualan Hari Ini")
    sales_columns = ("No", "Resit", "Tarikh/Masa", "Jumlah", "Diskaun", "Jumlah Bayaran", "Baki Pulangan", "Kaedah Bayaran", "Status")
    sales_tree = ttk.Treeview(sales_frame, columns=sales_columns, show="headings")
    for col in sales_columns:
        sales_tree.heading(col, text=col)
        sales_tree.column(col, width=110)
    sales_tree.pack(fill="both", expand=True, padx=10, pady=10)
    sales_btn_frame = tk.Frame(sales_frame)
    sales_btn_frame.pack(fill="x", padx=10, pady=(6,2))

    def load_today_sales():
        sales_tree.delete(*sales_tree.get_children())
        today = datetime.now().strftime("%Y-%m-%d")
        try:
            response = requests.get(f"{API_URL}?action=get_today_sales&date={today}", timeout=5)
            data = response.json()
            if data.get('status') == 'success':
                for sale in data['data']:
                    sales_tree.insert("", "end", values=(
                        sale['no'], sale['receipt_no'], sale['sale_time'],
                        f"RM {float(sale['total']):.2f}", f"RM {float(sale['discount']):.2f}",
                        f"RM {float(sale['amount_paid']):.2f}", f"RM {float(sale['change_given']):.2f}",
                        sale['payment_method'], sale['status']
                    ))
        except Exception as e:
            messagebox.showerror("Error", f"Gagal muat jualan: {str(e)}")

    def print_selected_receipt():
        selected = sales_tree.focus()
        if not selected:
            messagebox.showwarning("Peringatan", "Sila pilih satu resit dari senarai!")
            return
        vals = sales_tree.item(selected, 'values')
        if len(vals) < 2:
            messagebox.showwarning("Peringatan", "Data resit tidak lengkap!")
            return
        receipt_no = vals[1]
        try:
            res = requests.get(f"{API_URL}?action=get_transaction&receipt_no={receipt_no}", timeout=8)
            data = res.json()
            if data.get('status') != 'success' or 'data' not in data:
                raise Exception(data.get('message', 'Gagal ambil data transaksi'))
            trx = data['data']
            items = trx['items']
            total = float(trx['total'])
            amount_paid = float(trx['amount_paid'])
            payment_method = trx['payment_method']
            discount = float(trx.get('discount', 0))
            tax = float(trx.get('tax', 0))
            sale_date = trx.get('sale_date')
            customer_info = trx.get('customer_info', None)
            print_receipt(
                items=items,
                total=total,
                amount_paid=amount_paid,
                payment_method=payment_method,
                customer_info=customer_info,
                discount=discount,
                tax=tax,
                receipt_no=receipt_no,
                sale_date=sale_date
            )
        except Exception as e:
            messagebox.showerror("Error", f"Gagal dapatkan/print resit: {str(e)}")

    btn_refresh = tk.Button(sales_btn_frame, text="Refresh", command=load_today_sales, bg="#3498db", fg="white", font=("Arial", 11, "bold"))
    btn_refresh.pack(side="left", padx=2)
    btn_print = tk.Button(sales_btn_frame, text="Print Resit", command=print_selected_receipt, bg="#27ae60", fg="white", font=("Arial", 11, "bold"))
    btn_print.pack(side="left", padx=2)

    # INVENTORY BUTTON PATCH
    from inventory_gui import open_inventory_management

    btn_inventory = tk.Button(sales_btn_frame, text="Inventory", bg="#FF9900", fg="white", font=("Arial", 11, "bold"), command=lambda: open_inventory_management(user_id))
    btn_inventory.pack(side="left", padx=2)

    # ====== BUTTON TUTUP SHIFT ======
    def tutup_shift():
        win = tk.Toplevel(dashboard)
        win.title("Tutup Shift")
        win.geometry("350x200")
        tk.Label(win, text="Anda pasti ingin tutup shift?", font=("Arial", 13, "bold")).pack(pady=10)
        tk.Label(win, text="Baki Tunai Akhir (RM):").pack()
        entry_baki = tk.Entry(win, font=("Arial", 15), width=15)
        entry_baki.pack(pady=7)
        entry_baki.focus()
        def submit_tutup():
            try:
                baki_akhir = float(entry_baki.get())
                resp = requests.post(API_URL, json={"action": "close_shift", "user_id": user_id, "cash_end": baki_akhir}, timeout=10)
                data = resp.json()
                if data.get("status") == "success":
                    messagebox.showinfo("Sukses", "Shift berjaya ditutup!", parent=win)
                    win.destroy()
                    dashboard.destroy()
                    show_login_window()
                else:
                    raise Exception(data.get("message", "Gagal tutup shift!"))
            except Exception as e:
                messagebox.showerror("Error", f"Gagal tutup shift: {e}", parent=win)
        tk.Button(win, text="Tutup Shift", command=submit_tutup, bg="#32CD32", fg="white", font=("Arial", 12, "bold")).pack(pady=10)
        tk.Button(win, text="Batal", command=win.destroy).pack()
        win.transient(dashboard)
        win.grab_set()
        win.wait_window()

    btn_tutup_shift = tk.Button(sales_btn_frame, text="Tutup Shift", bg="#FFA500", fg="black", font=("Arial", 11, "bold"), command=tutup_shift)
    btn_tutup_shift.pack(side="left", padx=2)

    low_stock_frame = tk.Frame(notebook)
    notebook.add(low_stock_frame, text="Stok Rendah")
    low_stock_columns = ("No", "Nama Produk", "Stok", "Status")
    tree_low_stock = ttk.Treeview(low_stock_frame, columns=low_stock_columns, show="headings")
    for col in low_stock_columns:
        tree_low_stock.heading(col, text=col)
        tree_low_stock.column(col, width=120)
    tree_low_stock.pack(fill="both", expand=True, padx=10, pady=10)
    
    right = ctk.CTkFrame(main)
    right.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
    ctk.CTkLabel(right, text="Transaksi", font=("Arial", 20, "bold")).pack(pady=10, fill="x")

# ... (bahagian awal open_cashier_dashboard kekal sama)

    button_grid = ctk.CTkFrame(right)
    button_grid.pack(pady=3, fill="x", padx=26)
    btn_detect = ctk.CTkButton(
        button_grid, text="Detect \n Printer", fg_color="#9444DD", text_color="white",
        font=("Arial", 17, "bold"), command=lambda: select_printer_popup(dashboard),
        width=120, height=50
    )
    btn_detect.grid(row=0, column=0, padx=5, pady=5, sticky="ew")
    btn_virtual = ctk.CTkButton(
        button_grid, text="Virtual \n Keyboard", fg_color="#20B2AA", text_color="white",
        font=("Arial", 17, "bold"), command=lambda: CTkVirtualKeyboard(dashboard),
        width=120, height=50
    )
    btn_virtual.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
    btn_cari = ctk.CTkButton(
        button_grid, text="Cari \n Produk", fg_color="#FFD700", text_color="black",
        font=("Arial", 17, "bold"), command=lambda: open_search_product(),
        width=120, height=50
    )
    btn_cari.grid(row=1, column=0, padx=5, pady=5, sticky="ew")
    btn_hapus = ctk.CTkButton(
        button_grid, text="Hapus \n Produk", fg_color="#FF6347", text_color="white",
        font=("Arial", 17, "bold"), command=lambda: remove_item(),
        width=120, height=50
    )
    btn_hapus.grid(row=1, column=1, padx=5, pady=5, sticky="ew")
    btn_laci = ctk.CTkButton(
        button_grid, text="Buka \n Laci", fg_color="#4169E1", text_color="white",
        font=("Arial", 17, "bold"), command=open_cash_drawer,
        width=120, height=50
    )
    btn_laci.grid(row=2, column=0, padx=5, pady=5, sticky="ew")

    def confirm_logout(dashboard, user_id):
        def on_keluar_tanpa_shift():
            result = messagebox.askyesno(
                "Keluar Tanpa Tutup Shift",
                "Anda pasti mahu keluar tanpa tutup shift?\nShift masih aktif.",
                parent=dashboard
            )
            if result:
                dashboard.destroy()
                show_login_window()

        def on_tutup_shift():
            tutup_shift()

        def on_batal():
            confirm_win.destroy()

        confirm_win = tk.Toplevel(dashboard)
        confirm_win.title("Keluar Sistem")
        confirm_win.geometry("360x180")
        tk.Label(confirm_win, text="Anda mahu keluar tanpa tutup shift?", font=("Arial", 13, "bold")).pack(pady=10)
        btn1 = tk.Button(confirm_win, text="Keluar tanpa tutup shift", command=lambda: [confirm_win.destroy(), on_keluar_tanpa_shift()], width=28, bg="#f1c40f")
        btn1.pack(pady=6)
        btn2 = tk.Button(confirm_win, text="Tutup shift & keluar", command=lambda: [confirm_win.destroy(), on_tutup_shift()], width=28, bg="#27ae60", fg="white")
        btn2.pack(pady=6)
        btn3 = tk.Button(confirm_win, text="Tak Jadi", command=on_batal, width=28)
        btn3.pack(pady=6)
        confirm_win.transient(dashboard)
        confirm_win.grab_set()
        confirm_win.wait_window()
    btn_keluar = ctk.CTkButton(
        button_grid, text="Keluar", fg_color="#B22222", text_color="white",
        font=("Arial", 17, "bold"),
        command=lambda: confirm_logout(dashboard, user_id),
        width=120, height=50
    )
    btn_keluar.grid(row=2, column=1, padx=5, pady=5, sticky="ew")
    button_grid.columnconfigure(0, weight=1)
    button_grid.columnconfigure(1, weight=1)

# ... (baki kod open_cashier_dashboard kekal sama)

    ctk.CTkButton(
        right, text="Selesaikan Transaksi", font=("Arial", 19, "bold"), width=120, height=80,
        fg_color="#32CD32", command=lambda: complete_transaction()
    ).pack(fill="x", padx=30, pady=30)

    subtotal_frame = ctk.CTkFrame(right)
    subtotal_frame.pack(fill="x", padx=10, pady=2)
    ctk.CTkLabel(subtotal_frame, text="Subtotal:", font=("Arial", 16)).pack(side="left")
    label_subtotal = ctk.CTkLabel(subtotal_frame, text="RM 0.00", font=("Arial", 18, "bold"))
    label_subtotal.pack(side="right")
    discount_frame = ctk.CTkFrame(right)
    discount_frame.pack(fill="x", padx=10, pady=2)
    ctk.CTkLabel(discount_frame, text="Diskaun:", font=("Arial", 16)).pack(side="left")
    entry_discount = ctk.CTkEntry(discount_frame, font=("Arial", 18, "bold"), width=120)
    entry_discount.insert(0, "0.00")
    entry_discount.pack(side="right")
    entry_discount.bind("<FocusIn>", lambda e: CTkVirtualKeyboard.set_target_entry(entry_discount))
    tax_frame = ctk.CTkFrame(right)
    tax_frame.pack(fill="x", padx=10, pady=2)
    ctk.CTkLabel(tax_frame, text="Cukai:", font=("Arial", 16)).pack(side="left")
    entry_tax = ctk.CTkEntry(tax_frame, font=("Arial", 18, "bold"), width=120)
    entry_tax.insert(0, "0.00")
    entry_tax.pack(side="right")
    entry_tax.bind("<FocusIn>", lambda e: CTkVirtualKeyboard.set_target_entry(entry_tax))
    total_frame = ctk.CTkFrame(right)
    total_frame.pack(fill="x", padx=10, pady=7)
    ctk.CTkLabel(total_frame, text="Total:", font=("Arial", 18, "bold")).pack(side="left")
    label_total = ctk.CTkLabel(total_frame, text="RM 0.00", font=("Arial", 22, "bold"))
    label_total.pack(side="right")
    method_frame = ctk.CTkFrame(right)
    method_frame.pack(fill="x", padx=10, pady=2)
    ctk.CTkLabel(method_frame, text="Kaedah Bayar:", font=("Arial", 15)).pack(anchor="w")
    payment_var = tk.StringVar(value="Tunai")
    for m in ["Tunai", "Hutang", "Kad Kredit/Debit", "Online Transfer", "QR Kod"]:
        ctk.CTkRadioButton(method_frame, text=m, variable=payment_var, value=m, font=("Arial", 14)).pack(anchor="w")
    amount_paid_frame = ctk.CTkFrame(right)
    amount_paid_frame.pack(fill="x", padx=10, pady=2)
    ctk.CTkLabel(amount_paid_frame, text="Jumlah Bayar:", font=("Arial", 16)).pack(side="left")
    entry_amount_paid = ctk.CTkEntry(amount_paid_frame, font=("Arial", 18, "bold"), width=120)
    entry_amount_paid.pack(side="right")
    entry_amount_paid.bind("<FocusIn>", lambda e: CTkVirtualKeyboard.set_target_entry(entry_amount_paid))
    change_frame = ctk.CTkFrame(right)
    change_frame.pack(fill="x", padx=10, pady=2)
    ctk.CTkLabel(change_frame, text="Baki:", font=("Arial", 16)).pack(side="left")
    label_change = ctk.CTkLabel(change_frame, text="RM 0.00", font=("Arial", 18, "bold"))
    label_change.pack(side="right")

    item_counter = [1]
    customer_data = {}

    # PATCH: update_totals selamat untuk parsing float
    def update_totals(*args):
        try:
            subtotal = 0
            for item in tree_main.get_children():
                v = tree_main.item(item, 'values')
                total_str = str(v[4]).replace("RM", "").replace(",", "").strip()
                if total_str:
                    subtotal += float(total_str)
            discount = float(entry_discount.get() or 0)
            tax = float(entry_tax.get() or 0)
            total = subtotal - discount + tax
            label_subtotal.configure(text=f"RM {subtotal:.2f}")
            label_total.configure(text=f"RM {total:.2f}")
            calculate_change()
        except Exception:
            label_subtotal.configure(text="RM 0.00")
            label_total.configure(text="RM 0.00")
            label_change.configure(text="RM 0.00")

    def calculate_change(*args):
        try:
            if payment_var.get() == "Hutang":
                label_change.configure(text="Hutang", text_color="orange")
                return
            total = float(label_total.cget("text").replace("RM", "").strip())
            paid = float(entry_amount_paid.get() or 0)
            change = paid - total
            label_change.configure(
                text=f"RM {change:.2f}" if change >= 0 else f"-RM {abs(change):.2f}",
                text_color="white" if change >= 0 else "red"
            )
        except Exception:
            label_change.configure(text="RM 0.00", text_color="white")

    def customer_info_popup():
        win = tk.Toplevel(dashboard)
        win.title("Info Pelanggan Hutang")
        win.geometry("350x220")
        tk.Label(win, text="Nama Pelanggan*").pack()
        name = tk.Entry(win)
        name.pack()
        name.bind("<FocusIn>", lambda e: CTkVirtualKeyboard.set_target_entry(name))
        tk.Label(win, text="Telefon").pack()
        phone = tk.Entry(win)
        phone.pack()
        phone.bind("<FocusIn>", lambda e: CTkVirtualKeyboard.set_target_entry(phone))
        tk.Label(win, text="Alamat").pack()
        addr = tk.Entry(win)
        addr.pack()
        addr.bind("<FocusIn>", lambda e: CTkVirtualKeyboard.set_target_entry(addr))
        def simpan():
            if not name.get().strip():
                messagebox.showwarning("Peringatan", "Nama pelanggan wajib diisi!", parent=win)
                return
            customer_data["name"] = name.get().strip()
            customer_data["phone"] = phone.get().strip()
            customer_data["address"] = addr.get().strip()
            win.destroy()
        tk.Button(win, text="Simpan", command=simpan).pack(pady=10)
        win.transient(dashboard)
        win.grab_set()
        win.wait_window()

    def highlight_last_cart_item():
        items = tree_main.get_children()
        if items:
            last_item = items[-1]
            tree_main.selection_set(last_item)
            tree_main.see(last_item)

    def scan_barcode(barcode):
        if not barcode:
            return
        try:
            res = requests.get(f"{API_URL}?barcode={barcode}")
            res.raise_for_status()
            product = res.json()
            if not product or 'id' not in product:
                messagebox.showwarning("Peringatan", "Produk tidak ditemukan!")
                return
            product_name = product['name']
            price_float = float(product['price'])
            is_weighable = int(product.get('is_weighable', 0))
            if is_weighable:
                win = tk.Toplevel()
                win.title("Masukkan Berat (KG)")
                win.geometry("320x120")
                tk.Label(win, text=f"Masukkan berat (kg) untuk {product_name}:", font=("Arial", 13)).pack()
                qty_entry = tk.Entry(win, font=("Arial", 15), width=10)
                qty_entry.pack(pady=7)
                qty_entry.focus()
                result = {'quantity': None}
                def submit_qty():
                    try:
                        q = float(qty_entry.get())
                        if q <= 0 or q > 999:
                            raise ValueError
                        result['quantity'] = q
                        win.destroy()
                    except:
                        messagebox.showerror("Input Salah", "Sila masukkan berat dalam KG (cth: 0.185)", parent=win)
                tk.Button(win, text="OK", command=submit_qty, width=10).pack()
                win.transient()
                win.grab_set()
                win.wait_window()
                quantity = result['quantity']
                if not quantity:
                    return
            else:
                quantity = 1
                for item in tree_main.get_children():
                    values = tree_main.item(item, 'values')
                    if values[1] == product_name:
                        old_qty = float(values[3])
                        new_quantity = old_qty + 1
                        new_total = new_quantity * price_float
                        tree_main.item(item, values=(
                            values[0], values[1], f"RM {price_float:.2f}", new_quantity, f"RM {new_total:.2f}"
                        ))
                        update_totals()
                        entry_barcode.delete(0, tk.END)
                        highlight_last_cart_item()
                        return
            idx = item_counter[0]
            total = quantity * price_float
            tree_main.insert("", "end", values=(idx, product_name, f"RM {price_float:.2f}", quantity, f"RM {total:.2f}"))
            item_counter[0] += 1
            update_totals()
            entry_barcode.delete(0, tk.END)
            highlight_last_cart_item()
        except Exception as e:
            messagebox.showerror("Error", f"Gagal scan barcode: {str(e)}")

    def remove_item():
        selected = tree_main.selection()
        if not selected:
            messagebox.showwarning("Peringatan", "Pilih item untuk dihapus")
            return
        tree_main.delete(selected)
        item_counter[0] = 1
        for item in tree_main.get_children():
            values = tree_main.item(item, 'values')
            tree_main.item(item, values=(item_counter[0], values[1], values[2], values[3], values[4]))
            item_counter[0] += 1
        update_totals()

    def open_search_product():
        global search_popup_open
        if search_popup_open:
            return
        search_popup_open = True
        win = tk.Toplevel(dashboard)
        win.title("Cari Produk")
        win.geometry("700x500")
        tk.Label(win, text="Cari:").pack(anchor="w")
        search_var = tk.StringVar()
        search_entry = tk.Entry(win, textvariable=search_var, font=("Arial", 14), width=30)
        search_entry.pack(anchor="w", padx=10)
        search_entry.bind("<FocusIn>", lambda e: CTkVirtualKeyboard.set_target_entry(search_entry))
        results_tree = ttk.Treeview(win, columns=("Nama", "Harga", "Stok", "Barcode"), show="headings", height=12)
        for col in results_tree["columns"]:
            results_tree.heading(col, text=col)
            results_tree.column(col, width=150)
        results_tree.pack(fill="both", expand=True, padx=10, pady=10)
        products_data = []
        def do_search(*args):
            query = search_var.get().strip()
            if len(query) < 2:
                results_tree.delete(*results_tree.get_children())
                return
            try:
                params = {'action': 'search_products', 'query': query, 'limit': 50}
                response = requests.get(API_URL, params=params, timeout=10)
                data = response.json()
                if not isinstance(data, dict) or 'data' not in data:
                    raise ValueError("Format response tidak valid")
                products = data['data']
                products_data.clear()
                products_data.extend(products)
                results_tree.delete(*results_tree.get_children())
                for product in products:
                    results_tree.insert("", "end", values=(
                        product.get("name", ""), f"RM {float(product.get('price', 0)):.2f}",
                        product.get("stock", ""), product.get("barcode", "")
                    ))
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=win)
        def close_popup():
            global search_popup_open
            search_popup_open = False
            win.destroy()
            entry_barcode.focus_set()
            
        def add_selected_product():
            selected = results_tree.focus()
            if not selected:
                messagebox.showwarning("Peringatan", "Pilih produk.", parent=win)
                return
            vals = results_tree.item(selected, "values")
            product_name = vals[0]
            price_str = vals[1].replace("RM", "").strip()
            price = float(price_str)
            is_weighable = 0
            for product in products_data:
                if product.get('name') == product_name:
                    is_weighable = int(product.get('is_weighable', 0))
                    break
            if is_weighable:
                berat_win = tk.Toplevel(win)
                berat_win.title("Masukkan Berat (KG)")
                berat_win.geometry("320x120")
                tk.Label(berat_win, text=f"Masukkan berat (kg) untuk {product_name}:", font=("Arial", 13)).pack()
                qty_entry = tk.Entry(berat_win, font=("Arial", 15), width=10)
                qty_entry.pack(pady=7)
                qty_entry.focus()
                result = {'quantity': None}
                def submit_qty():
                    try:
                        q = float(qty_entry.get())
                        if q <= 0 or q > 999:
                            raise ValueError
                        result['quantity'] = q
                        berat_win.destroy()
                    except:
                        messagebox.showerror("Input Salah", "Sila masukkan berat dalam KG (cth: 0.185)", parent=berat_win)
                tk.Button(berat_win, text="OK", command=submit_qty, width=10).pack()
                berat_win.transient()
                berat_win.grab_set()
                berat_win.wait_window()
                quantity = result['quantity']
                if not quantity:
                    return
            else:
                quantity = 1
                for item in tree_main.get_children():
                    v = tree_main.item(item, 'values')
                    if v[1] == product_name:
                        old_qty = float(v[3])
                        new_quantity = old_qty + 1
                        new_total = new_quantity * price
                        tree_main.item(item, values=(v[0], v[1], f"RM {price:.2f}", new_quantity, f"RM {new_total:.2f}"))
                        update_totals()
                        win.destroy()
                        highlight_last_cart_item()
                        return
            idx = item_counter[0]
            total = price * quantity
            tree_main.insert("", "end", values=(idx, product_name, f"RM {price:.2f}", quantity, f"RM {total:.2f}"))
            item_counter[0] += 1
            update_totals()
            win.destroy()
            highlight_last_cart_item()
            close_popup()
        search_var.trace_add("write", do_search)
        search_entry.bind("<Return>", do_search)
        results_tree.bind("<Double-1>", lambda e: add_selected_product())
        win.protocol("WM_DELETE_WINDOW", close_popup)

    def update_quantity_modal(item_id, tree):
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
        try:
            is_weighable = (float(current_quantity) != int(float(current_quantity)))
        except Exception:
            is_weighable = False
        modal = tk.Toplevel(tree.master)
        modal.title(f"Kemaskini Kuantiti: {product_name}")
        modal.geometry("320x160")
        tk.Label(modal, text=f"Produk: {product_name}", font=("Arial", 13, "bold")).pack(pady=10)
        tk.Label(modal, text="Kuantiti Baru:", font=("Arial", 13)).pack(pady=5)
        quantity_entry = tk.Entry(modal, font=("Arial", 14), width=10)
        quantity_entry.insert(0, str(current_quantity))
        quantity_entry.pack(pady=5)
        quantity_entry.focus()
        def submit_quantity():
            try:
                val = quantity_entry.get().strip()
                if is_weighable:
                    new_quantity = float(val)
                    if new_quantity < 0.001:
                        raise ValueError("Kuantiti mestilah > 0")
                else:
                    if '.' in val:
                        raise ValueError("Kuantiti untuk barang unit mesti nombor bulat")
                    new_quantity = int(val)
                    if new_quantity < 1:
                        raise ValueError("Kuantiti mestilah > 0")
                price = float(current_values[2].replace("RM", ""))
                new_total = price * new_quantity
                tree.item(selected_item, values=(
                    current_values[0], current_values[1], current_values[2], new_quantity, f"RM {new_total:.2f}"
                ))
                update_totals()
                modal.destroy()
            except Exception as e:
                messagebox.showerror("Input Tidak Sah", str(e), parent=modal)
                quantity_entry.focus()
        tk.Button(modal, text="Simpan", command=submit_quantity, width=12, bg="#32CD32", fg="white").pack(pady=10)
        tk.Button(modal, text="Batal", command=modal.destroy, width=12).pack()
        modal.bind('<Return>', lambda e: submit_quantity())

    def update_quantity_popup():
        global update_qty_popup_open
        if update_qty_popup_open:
            return
        selection = tree_main.selection()
        if not selection:
            messagebox.showwarning("Peringatan", "Tiada item dipilih untuk dikemaskini!")
            return
        item_id = selection[0]
        current_values = tree_main.item(item_id, 'values')
        product_name = current_values[1]
        current_quantity = current_values[3]
        modal = tk.Toplevel(dashboard)
        modal.title(f"Kemaskini Kuantiti: {product_name}")
        modal.geometry("320x160")
        update_qty_popup_open = True
        def on_close():
            global update_qty_popup_open
            update_qty_popup_open = False
            modal.destroy()
        tk.Label(modal, text=f"Produk: {product_name}", font=("Arial", 13, "bold")).pack(pady=10)
        tk.Label(modal, text="Kuantiti Baru:", font=("Arial", 13)).pack(pady=5)
        quantity_entry = tk.Entry(modal, font=("Arial", 14), width=10)
        quantity_entry.insert(0, str(current_quantity))
        quantity_entry.pack(pady=5)
        quantity_entry.focus()
        def submit_quantity():
            try:
                val = quantity_entry.get().strip()
                new_quantity = float(val) if "." in val else int(val)
                if new_quantity <= 0:
                    raise ValueError("Kuantiti mesti lebih 0")
                price = float(current_values[2].replace("RM", ""))
                new_total = price * new_quantity
                tree_main.item(item_id, values=(
                    current_values[0], current_values[1], current_values[2], new_quantity, f"RM {new_total:.2f}"
                ))
                update_totals()
                on_close()
                entry_barcode.focus_set()
            except Exception as e:
                messagebox.showerror("Input Tidak Sah", str(e), parent=modal)
                quantity_entry.focus()
        tk.Button(modal, text="Simpan", command=submit_quantity, width=12, bg="#32CD32", fg="white").pack(pady=10)
        tk.Button(modal, text="Batal", command=on_close, width=12).pack()
        modal.bind('<Return>', lambda e: submit_quantity())
        modal.protocol("WM_DELETE_WINDOW", on_close)
        modal.transient(dashboard)
        modal.grab_set()
        modal.wait_window()

    def tree_main_double_click(event):
        sel = tree_main.focus()
        if not sel:
            return
        item_id = tree_main.item(sel, 'values')[0]
        update_quantity_modal(item_id, tree_main)
    tree_main.bind("<Double-1>", tree_main_double_click)
    tree_low_stock.bind("<Double-1>", lambda e: None)  # keep as is for now

    def load_low_stock_products():
        tree_low_stock.delete(*tree_low_stock.get_children())
        try:
            response = requests.get(f"{API_URL}?action=get_low_stock_products", timeout=5)
            data = response.json()
            if data.get('status') == 'success':
                for idx, prod in enumerate(data.get('products', []), start=1):
                    stok = int(prod.get('stock', 0))
                    status = "HABIS" if stok <= 0 else "RENDAH" if stok <= 5 else ""
                    if status:
                        tree_low_stock.insert("", "end", values=(idx, prod.get('name', ''), stok, status))
        except Exception as e:
            messagebox.showerror("Error", f"Gagal muat stok rendah: {str(e)}")

    def complete_transaction():
        try:
            items = []
            for item in tree_main.get_children():
                values = tree_main.item(item, 'values')
                product_name = values[1]
                qty = float(values[3])
                price = float(values[2].replace("RM", ""))
                total = float(values[4].replace("RM", ""))
                items.append({
                    'name': product_name,
                    'quantity': qty,
                    'price': price,
                    'total': total
                })
            if not items:
                messagebox.showwarning("Peringatan", "Tidak ada item dalam troli!")
                return
            subtotal = sum(i["total"] for i in items)
            discount = float(entry_discount.get() or 0)
            tax = float(entry_tax.get() or 0)
            total = subtotal - discount + tax
            payment_method = payment_var.get()
            payment_method_map = {
                "Tunai": 1,
                "Hutang": 2,
                "Kad Kredit/Debit": 3,
                "Online Transfer": 4,
                "QR Kod": 5
            }
            payment_method_id = payment_method_map.get(payment_method, 1)
            if payment_method == "Hutang":
                if not customer_data.get("name"):
                    messagebox.showwarning("Peringatan", "Maklumat pelanggan hutang perlu diisi!")
                    return
                amount_paid = 0.0
            else:
                amount_paid = float(entry_amount_paid.get() or 0)
                if amount_paid < total:
                    messagebox.showwarning("Peringatan", "Jumlah bayar kurang dari total")
                    return
            transaction_data = {
                "action": "save_transaction",
                "items": items,
                "total": total,
                "discount": discount,
                "tax": tax,
                "amount_paid": amount_paid,
                "user_id": user_id,
                "payment_method": payment_method,
                "payment_method_id": payment_method_id,
                "customer_info": customer_data if payment_method == "Hutang" else None
            }
            response = requests.post(API_URL, json=transaction_data, timeout=10)
            result = response.json()
            if result.get("status") != "success":
                messagebox.showerror("Error", result.get("message", "Gagal simpan transaksi"))
                return

            if print_receipt_var.get():
                print_receipt(items, total, amount_paid, payment_method)
            if open_drawer_var.get():
                open_cash_drawer()

            messagebox.showinfo("Sukses", "Transaksi berjaya!")
            for item in tree_main.get_children():
                tree_main.delete(item)
            entry_discount.delete(0, tk.END)
            entry_tax.delete(0, tk.END)
            entry_amount_paid.delete(0, tk.END)
            entry_discount.insert(0, "0.00")
            entry_tax.insert(0, "0.00")
            customer_data.clear()
            update_totals()
            load_today_sales()
        except Exception as e:
            messagebox.showerror("Error", f"Gagal proses transaksi: {str(e)}")

    dashboard.bind('<F3>', lambda e: CTkVirtualKeyboard(dashboard))
    dashboard.after(700, lambda: CTkVirtualKeyboard(dashboard))
    entry_barcode.bind("<Return>", lambda e: scan_barcode(entry_barcode.get()))
    entry_discount.bind("<KeyRelease>", update_totals)
    entry_tax.bind("<KeyRelease>", update_totals)
    entry_amount_paid.bind("<KeyRelease>", calculate_change)
    payment_var.trace_add("write", lambda *args: (
        customer_info_popup() if payment_var.get() == "Hutang" else None,
        entry_amount_paid.configure(state="disabled" if payment_var.get() == "Hutang" else "normal"),
        entry_amount_paid.delete(0, tk.END),
        label_change.configure(text="Hutang" if payment_var.get() == "Hutang" else "RM 0.00", text_color="orange" if payment_var.get() == "Hutang" else "white")
    ))

    # PATCH: auto fokus barcode (letak selepas SEMUA entry didefinisi)
    def keep_focus_barcode():
        focus_widget = dashboard.focus_get()
        allowed_entries = {entry_barcode, entry_discount, entry_tax, entry_amount_paid}
        if not search_popup_open and not update_qty_popup_open and (focus_widget not in allowed_entries):
            try:
                entry_barcode.focus_set()
            except Exception:
                pass
        dashboard.after(10000, keep_focus_barcode)
    keep_focus_barcode()

    # PATCH: HOTKEY
    dashboard.bind('<F1>', lambda e: entry_amount_paid.focus_set())
    dashboard.bind('<F2>', lambda e: complete_transaction())
    dashboard.bind('<F5>', lambda e: update_quantity_popup())

    load_today_sales()
    load_low_stock_products()
    dashboard.mainloop()

if __name__ == "__main__":
    threading.Thread(target=auto_sync, daemon=True).start()
    show_login_window()
