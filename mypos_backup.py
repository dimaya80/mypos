import tkinter as tk
from tkinter import ttk, messagebox
import customtkinter as ctk
import requests
import uuid
import serial
import serial.tools.list_ports
import time
import threading
from datetime import datetime, timezone
import queue
import json
import win32api
import os
from threading import Lock
from urllib.parse import quote

# Tetapkan tema secara global
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("green")

# === PATCH: Printer Support (USB/Serial) ===
try:
    import win32print
except ImportError:
    win32print = None

def load_config():
    config_file = 'config.json'
    if not os.path.exists(config_file):
        raise FileNotFoundError(f"Fail konfigurasi {config_file} tidak wujud! Pastikan fail ada di direktori: {os.getcwd()}")
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
    except json.JSONDecodeError as e:
        with open(config_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            error_line = lines[e.lineno - 1] if e.lineno <= len(lines) else "Unknown"
        raise ValueError(f"Fail konfigurasi {config_file} tidak sah: {str(e)}\nBaris {e.lineno}: {error_line.strip()}")
    
    required_keys = ['CASHIER_ID', 'API_URL', 'SYNC_PUSH_URL', 'SYNC_PULL_URL']
    missing_keys = [key for key in required_keys if key not in config]
    if missing_keys:
        raise KeyError(f"Key berikut tiada dalam {config_file}: {', '.join(missing_keys)}")
    
    config.setdefault('LAST_SYNC', '2025-01-01 00:00:00')
    config.setdefault('API_TOKEN', '')
    return config

try:
    config = load_config()
    CASHIER_ID = config['CASHIER_ID']
    API_URL = config['API_URL']
    SYNC_PUSH_URL = f"{config['SYNC_PUSH_URL']}?cashier_id={CASHIER_ID}"
    SYNC_PULL_URL = f"{config['SYNC_PULL_URL']}?cashier_id={CASHIER_ID}"  # Tambah cashier_id
except Exception as e:
    raise SystemExit(f"Ralat konfigurasi: {str(e)}")

# Thread lock untuk kemas kini UI yang selamat
ui_lock = Lock()

def save_last_sync():
    try:
        config['LAST_SYNC'] = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
        with open('config.json', 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2)
        print(f"[save_last_sync] Saved LAST_SYNC: {config['LAST_SYNC']}")
    except IOError as e:
        print(f"[save_last_sync] Error writing config.json: {str(e)}")
        raise

def auto_sync(sync_queue, sync_label, root, cashier_id):
    max_retries = 3
    while True:
        for attempt in range(max_retries):
            try:
                sync_message = f"🔄 Auto-sync starting for {cashier_id} (Attempt {attempt+1}/{max_retries})...\n"
                sync_queue.put(sync_message)
                print(f"[auto_sync] {sync_message.strip()}")

                # Push data
                print(f"[auto_sync] Pushing to {SYNC_PUSH_URL}")
                try:
                    r1 = requests.get(SYNC_PUSH_URL, timeout=30)
                    push_msg = f"➡️ Push Response ({cashier_id}): {r1.status_code} "
                    try:
                        result = r1.json()
                        push_msg += f"{result.get('status', 'unknown')}: {result.get('message', 'no message')}\n"
                        if r1.status_code != 200 or result.get('status') != 'success':
                            push_msg += f"Push failed: {result}\n"
                    except ValueError:
                        push_msg += f"Invalid JSON: {r1.text.strip()}\n"
                    sync_queue.put(push_msg)
                    print(f"[auto_sync] {push_msg.strip()}")
                except requests.exceptions.ConnectionError:
                    push_msg = f"❌ Push failed: No internet connection\n"
                    sync_queue.put(push_msg)
                    print(f"[auto_sync] {push_msg.strip()}")
                    break

                # Pull data
                since = quote(config.get('LAST_SYNC', '2025-01-01 00:00:00'))
                pull_url = f"{SYNC_PULL_URL}&since={since}"
                print(f"[auto_sync] Pulling from {pull_url}")
                try:
                    r2 = requests.get(pull_url, timeout=30)
                    pull_msg = f"⬅️ Pull Response ({cashier_id}): {r2.status_code} "
                    try:
                        result = r2.json()
                        if isinstance(result, dict):
                            if 'status' in result and result['status'] == 'success' and 'message' in result:
                                pull_msg += f"{result['status']}: {result['message']}\n"
                            else:
                                for table, status in result.items():
                                    pull_msg += f"{table}: {status.get('status', 'unknown')} ({status.get('message', 'no message')})\n"
                                    if status.get('status') != 'success':
                                        pull_msg += f"Details: {status}\n"
                                if r2.status_code != 200 or any(status.get('status') != 'success' for status in result.values()):
                                    pull_msg += f"Pull failed: {result}\n"
                        else:
                            pull_msg += f"Unexpected response (not a dict): {result}\n"
                            print(f"[auto_sync] Unexpected response content: {r2.text.strip()}")
                        sync_queue.put(pull_msg)
                        print(f"[auto_sync] {pull_msg.strip()}")
                    except ValueError:
                        pull_msg += f"Invalid JSON: {r2.text.strip()}\n"
                        print(f"[auto_sync] Invalid JSON content: {r2.text.strip()}")
                        sync_queue.put(pull_msg)
                except requests.exceptions.ConnectionError:
                    pull_msg = f"❌ Pull failed: No internet connection\n"
                    sync_queue.put(pull_msg)
                    print(f"[auto_sync] {pull_msg.strip()}")
                    break

                # Simpan LAST_SYNC jika berjaya
                if r1.status_code == 200 and r2.status_code == 200:
                    try:
                        r1_result = r1.json()
                        r2_result = r2.json()
                        if (r1_result.get('status') == 'success' and
                            (isinstance(r2_result, dict) and (
                                ('status' in r2_result and r2_result['status'] == 'success') or
                                all(status.get('status') == 'success' for status in r2_result.values())
                            ))):
                            save_last_sync()
                            print(f"[auto_sync] Saved LAST_SYNC: {config['LAST_SYNC']}")
                    except ValueError as e:
                        sync_queue.put(f"❌ JSON parsing error: {e}\n")
                        print(f"[auto_sync] JSON parsing error: {e}")

                sync_message = f"✅ Auto-sync completed for {cashier_id}. Waiting 30 seconds...\n"
                sync_queue.put(sync_message)
                print(f"[auto_sync] {sync_message.strip()}")
                break
            except Exception as e:
                error_msg = f"❌ Auto-sync error for {cashier_id}: {str(e)} (Attempt {attempt+1}/{max_retries})\n"
                sync_queue.put(error_msg)
                print(f"[auto_sync] {error_msg.strip()}")
                if attempt == max_retries - 1:
                    root.after(0, lambda: messagebox.showerror("Ralat Penyegerakan", f"Gagal menyegerakkan data setelah {max_retries} cubaan: {str(e)}"))
                time.sleep(5)
            time.sleep(30)

def update_sync_label(sync_queue, sync_label, root):
    current_text = ""
    def update_label_in_main_thread(text, color):
        try:
            with ui_lock:
                root.after(0, lambda: sync_label.configure(text=text, text_color=color))
                root.after(0, lambda: sync_label.update_idletasks())
                print(f"[update_sync_label] Teks semasa: {text[:50]}... (panjang: {len(text)})")
        except Exception as e:
            print(f"[update_sync_label] Ralat semasa menjadualkan kemas kini UI: {e}")

    while True:
        try:
            message = sync_queue.get(timeout=1)
            current_text = (current_text + message)[-1000:]  # Hadkan panjang teks
            update_label_in_main_thread(current_text, "white")
            sync_queue.task_done()
        except queue.Empty:
            continue
        except Exception as e:
            print(f"[update_sync_label] Ralat: {e}")
            update_label_in_main_thread("Sync status: Error", "red")

PRIMARY_COLOR = "#2B7A78"
SELECTED_PRINTER_PORT = None

def detect_thermal_printer_serial():
    ports = serial.tools.list_ports.comports()
    for port in ports:
        if "USB" in port.description or "Thermal" in port.description:
            return port.device
    return None

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

        qwerty_rows = [['Q','W','E','R','T','Y','U','I','O','P'],
                       ['A','S','D','F','G','H','J','K','L'],
                       ['Z','X','C','V','B','N','M']]
        numpad_keys = [['1','2','3'], ['4','5','6'], ['7','8','9']]

        for r in range(3):
            for c, key in enumerate(qwerty_rows[r]):
                btn = ctk.CTkButton(self, text=key, width=50, height=50, fg_color="#393e46", text_color="#eeeeee", font=("Arial", 18, "bold"), command=lambda k=key: self.press(k))
                btn.grid(row=r, column=c, padx=2, pady=2)
            col_offset = 12
            for nc, nkey in enumerate(numpad_keys[r]):
                btn = ctk.CTkButton(self, text=nkey, width=50, height=50, fg_color="#393e46", text_color="#eeeeee", font=("Arial", 18, "bold"), command=lambda k=nkey: self.press(k))
                btn.grid(row=r, column=col_offset+nc, padx=2, pady=2)

        r = 3
        btn_space = ctk.CTkButton(self, text='Space', width=170, height=50, fg_color="#393e46", text_color="#eeeeee", font=("Arial", 18, "bold"), command=lambda k=' ': self.press(k))
        btn_space.grid(row=r, column=0, columnspan=3, padx=2, pady=2, sticky='ew')
        btn_enter = ctk.CTkButton(self, text='Enter', width=110, height=50, fg_color="#00adb5", text_color="#eeeeee", font=("Arial", 18, "bold"), command=self.press_enter)
        btn_enter.grid(row=r, column=3, columnspan=2, padx=2, pady=2, sticky='ew')
        btn_0 = ctk.CTkButton(self, text='0', width=50, height=50, fg_color="#393e46", text_color="#eeeeee", font=("Arial", 18, "bold"), command=lambda k='0': self.press(k))
        btn_0.grid(row=r, column=12, padx=2, pady=2)
        btn_dot = ctk.CTkButton(self, text='.', width=50, height=50, fg_color="#222831", text_color="#FFD700", font=("Arial", 18, "bold"), command=lambda k='.': self.special_press('.'))
        btn_dot.grid(row=r, column=13, padx=2, pady=2)
        btn_back = ctk.CTkButton(self, text='Back', width=50, height=50, fg_color="#393e46", text_color="#00adb5", font=("Arial", 18, "bold"), command=lambda k='Back': self.press(k))
        btn_back.grid(row=r, column=14, padx=2, pady=2)
        btn_f1 = ctk.CTkButton(self, text='F1', width=50, height=50, fg_color="#222831", text_color="#00adb5", font=("Arial", 18, "bold"), command=lambda k='F1': self.special_press('F1'))
        btn_f1.grid(row=r, column=15, padx=2, pady=2)
        btn_f2 = ctk.CTkButton(self, text='F2', width=50, height=50, fg_color="#222831", text_color="#00adb5", font=("Arial", 18, "bold"), command=lambda k='F2': self.special_press('F2'))
        btn_f2.grid(row=r, column=16, padx=2, pady=2)
        btn_f5 = ctk.CTkButton(self, text='F5', width=50, height=50, fg_color="#222831", text_color="#00adb5", font=("Arial", 18, "bold"), command=lambda k='F5': self.special_press('F5'))
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
            if 'store_name' in data and 'address' in data and 'phone' in data and 'biz_regno' in data:
                return {
                    'store_name': data['store_name'],
                    'address': data['address'],
                    'phone': data['phone'],
                    'biz_regno': data['biz_regno']
                }
            elif isinstance(data, dict) and data.get('status') == 'success' and isinstance(data.get('data'), dict):
                store_data = data['data']
                if 'store_name' in store_data and 'address' in store_data and 'phone' in store_data and 'biz_regno' in store_data:
                    return {
                        'store_name': store_data['store_name'],
                        'address': store_data['address'],
                        'phone': store_data['phone'],
                        'biz_regno': store_data['biz_regno']
                    }
        raise Exception("Gagal dapatkan maklumat kedai")
    except Exception as e:
        messagebox.showerror("Error", f"Gagal dapatkan info kedai: {str(e)}")
        return {
            'store_name': 'NAMA KEDAI TIDAK DITEMUI',
            'address': '-',
            'phone': '-',
            'biz_regno': '-'
        }

def print_receipt(items, total, amount_paid, payment_method, customer_info=None, discount=0, tax=0, receipt_no=None, sale_date=None):
    try:
        store_info = get_store_info()  # Fungsi ini pulangkan dict dengan 'store_name', 'address', 'phone', 'biz_regno'
        if not receipt_no:
            receipt_no = "INV" + datetime.now().strftime("%Y%m%d%H%M%S")
        if not sale_date:
            sale_date = datetime.now()
        elif isinstance(sale_date, str):
            try:
                sale_date = datetime.strptime(sale_date, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                sale_date = datetime.now()

        LEBAR = 32  # Untuk kertas 58mm
        receipt_lines = [
            "\x1B\x40", "\x1B\x21\x30", "\x1B\x21\x10", "\x1B\x61\x01",  # Init printer, double-height/width, bold, center
            "DMMT",
            "\x1B\x21\x10", "\x1B\x61\x01",  # Reset to bold only, center (for store info)
            f"{store_info['store_name']}",
            f"No. Daftar: {store_info['biz_regno']}",
            f"{store_info['address']}",
            f"{store_info['phone']}",
            "\x1B\x21\x00", "\x1B\x61\x00",  # Normal font, align left
            "=" * LEBAR,
            f"Tarikh: {sale_date.strftime('%d/%m/%Y %H:%M:%S')}  No Resit: {receipt_no}",
            "-" * LEBAR,
            f"{'Perkara':<14}{'Qty':>4}{'Harga':>6}{'Jumlah':>8}"
        ]

        for item in items:
            name = item['name'][:14]
            quantity = float(item['quantity'])
            price = float(item['price'])
            item_total = float(item['total'])

            qty_str = f"{int(quantity)}" if quantity == int(quantity) else f"{quantity:.3f}"
            price_str = f"{price:.2f}"
            total_str = f"{item_total:.2f}"

            receipt_lines.append(f"{name:<14}{qty_str:>4}{price_str:>6}{total_str:>8}")

        subtotal = sum(float(item['total']) for item in items)
        total_after_discount = subtotal - discount
        grand_total = total_after_discount + tax
        change = amount_paid - grand_total

        receipt_lines.extend([
            "-" * LEBAR,
            f"{'Subtotal:':<16}{subtotal:>16.2f}",
            f"{'Diskaun:':<16}{discount:>16.2f}",
            f"{'Cukai:':<16}{tax:>16.2f}",
            f"{'Dibayar:':<16}{amount_paid:>16.2f}",
            f"{'Baki:':<16}{change:>16.2f}",
            f"{'Total:':<16}{grand_total:>16.2f}",
            "=" * LEBAR,
            f"Bayar: {payment_method}",
            "=" * LEBAR,
            "\x1B\x61\x01",
            "Terima kasih! Barang tidak boleh ditukar",
            "\x1B\x61\x00",
            "=" * LEBAR,
            "\x1B\x61\x01",
            f"\x1D\x68\x50\x1D\x77\x02\x1D\x6B\x49{chr(len(receipt_no))}{receipt_no}",
            "\x1B\x61\x00",
            "\n\n",
            "\x1D\x56\x41\x03"
        ])

        # Perintah ESC/POS buka cash drawer
        receipt_lines.append("\x1B\x70\x00\x19\xFA")

        receipt_text = "\n".join(receipt_lines)

        port = SELECTED_PRINTER_PORT or detect_thermal_printer_serial()
        printed = False

        if port:
            try:
                with serial.Serial(port, baudrate=9600, timeout=1) as printer:
                    printer.write(receipt_text.encode('utf-8'))
                    time.sleep(0.5)
                printed = True
            except Exception as e:
                messagebox.showerror("Printer Error", f"Gagal cetak ke printer {port}:\n{str(e)}\nMencuba Windows printer...")
        
        if not printed and win32print:
            try:
                printer_name = win32print.GetDefaultPrinter()
                hprinter = win32print.OpenPrinter(printer_name)
                try:
                    hjob = win32print.StartDocPrinter(hprinter, 1, ("MyPOS Receipt", None, "RAW"))
                    win32print.StartPagePrinter(hprinter)
                    win32print.WritePrinter(hprinter, receipt_text.encode('utf-8'))
                    win32print.EndPagePrinter(hprinter)
                    win32print.EndDocPrinter(hprinter)
                    printed = True
                    messagebox.showinfo("Printer", f"Resit dicetak ke: {printer_name}")
                finally:
                    win32print.ClosePrinter(hprinter)
            except Exception as e:
                messagebox.showerror("Printer Error", f"Thermal printer & Windows/USB tidak dijumpai:\n{str(e)}")
                print(receipt_text)
                return False

        return printed

    except Exception as e:
        messagebox.showerror("Error", f"Error semasa cetak:\n{str(e)}")
        return False

def open_cash_drawer():
    global SELECTED_PRINTER_PORT
    if not win32print:
        messagebox.showerror("Printer Error", "pywin32 tidak dipasang. Tidak boleh buka laci wang.")
        return

    try:
        # Gunakan printer default atau yang dipilih
        printer_name = win32print.GetDefaultPrinter() if not SELECTED_PRINTER_PORT else SELECTED_PRINTER_PORT
        hprinter = win32print.OpenPrinter(printer_name)
        try:
            # Mulakan dokumen kosong untuk menghantar perintah cash drawer
            hjob = win32print.StartDocPrinter(hprinter, 1, ("Cash Drawer Command", None, "RAW"))
            win32print.StartPagePrinter(hprinter)

            # Perintah ESC/POS untuk membuka cash drawer
            cash_drawer_command = b'\x1B\x70\x00\x19\xFA'
            win32print.WritePrinter(hprinter, cash_drawer_command)
            win32print.EndPagePrinter(hprinter)
            win32print.EndDocPrinter(hprinter)
            messagebox.showinfo("Berjaya", "Laci wang berjaya dibuka!")
        finally:
            win32print.ClosePrinter(hprinter)
    except Exception as e:
        # Cuba alternatif melalui port serial jika win32print gagal (kurang berkemungkinan)
        port = detect_thermal_printer_serial()
        if port:
            try:
                ser = serial.Serial(port, baudrate=9600, timeout=1)
                time.sleep(2)
                ser.write(b'\x1B\x70\x00\x19\xFA')
                ser.close()
                messagebox.showinfo("Berjaya", "Laci wang berjaya dibuka!")
            except Exception as e2:
                messagebox.showerror("Error", f"Gagal membuka laci wang: {str(e)}\nCuba serial gagal: {str(e2)}")
        else:
            messagebox.showerror("Error", f"Gagal membuka laci wang: {str(e)}\nTiada port serial dikesan.")

shift_popup_open = False
main_root = None

def show_login_window():
    root = tk.Tk()
    root.title("My POS System - Login")
    root.resizable(False, False)

    # Dapatkan resolusi skrin
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()

    # Tetapkan saiz tetingkap login
    window_width = 400
    window_height = 400

    # Kira koordinat untuk berpusat
    x_coordinate = (screen_width - window_width) // 2
    y_coordinate = (screen_height - window_height) // 2

    # Tetapkan geometry untuk berpusat
    root.geometry(f"{window_width}x{window_height}+{x_coordinate}+{y_coordinate}")

    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")

    frame = ctk.CTkFrame(root)
    frame.pack(pady=50, padx=20, fill="both", expand=True)

    # Tajuk tanpa gambar
    ctk.CTkLabel(frame, text="DIN MINI MART TRADING", font=("Arial", 20, "bold")).pack(pady=20)

    # Medan input
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
            response = requests.post(API_URL, json={"action": "login", "username": username, "password": password}, timeout=5)
            result = response.json()
            if result.get("status") == "success":
                user_id = result["user"]["id"]
                root.withdraw()
                check_or_start_shift(user_id, root)
            else:
                messagebox.showerror("Login Gagal", result.get("message", "Login gagal"), parent=root)
        except Exception as e:
            messagebox.showerror("Error", f"Gagal login: {str(e)}", parent=root)

    # Butang log masuk
    ctk.CTkButton(frame, text="Login", command=login, fg_color=PRIMARY_COLOR).pack(pady=20)
    root.bind('<Return>', lambda e: login())
    root.mainloop()

def check_or_start_shift(user_id, root_window):
    global shift_popup_open
    if shift_popup_open:
        print("Shift popup already open, skipping check_or_start_shift")
        return
    try:
        print(f"Memeriksa syif untuk user_id: {user_id}, cashier_id: {CASHIER_ID}")
        resp = requests.get(API_URL, params={"action": "check_shift", "user_id": user_id, "cashier_id": CASHIER_ID}, timeout=10)
        data = resp.json()
        print(f"Respons API check_shift: {data}")
        if data.get("status") == "success" and data.get("has_shift"):
            print(f"Syif aktif dikesan untuk user_id: {user_id}, cashier_id: {CASHIER_ID}")
            root_window.destroy()
            open_cashier_dashboard(user_id, CASHIER_ID)
        else:
            print(f"Tiada syif aktif, memaparkan modal mula syif")
            show_shift_start_modal(user_id, root_window)
    except Exception as e:
        print(f"Ralat semasa memeriksa syif: {e}")
        messagebox.showerror("Ralat", f"Gagal semak shift: {str(e)}", parent=root_window)
        root_window.destroy()


def show_shift_start_modal(user_id, root_window):
    global shift_popup_open
    if shift_popup_open:
        print("Shift popup already open, skipping show_shift_start_modal")
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
        global shift_popup_open
        try:
            cash_awal = float(entry_cash.get())
            print(f"Memulakan syif dengan user_id: {user_id}, cashier_id: {CASHIER_ID}, cash_start: {cash_awal}")
            res = requests.post(API_URL, json={
                "action": "start_shift",
                "user_id": user_id,
                "cash_start": cash_awal,
                "cashier_id": CASHIER_ID
            }, timeout=10)
            data2 = res.json()
            print(f"Respons API start_shift: {data2}")
            if data2.get("status") == "success":
                messagebox.showinfo("Berjaya", "Shift bermula!", parent=win)
                win.destroy()
                shift_popup_open = False
                print(f"Memanggil open_cashier_dashboard dengan user_id: {user_id}, cashier_id: {CASHIER_ID}")
                open_cashier_dashboard(user_id, CASHIER_ID)
                root_window.destroy()
            elif data2.get("message", "").startswith("Syif sudah bermula"):
                print(f"Syif sudah bermula untuk cashier_id: {CASHIER_ID}")
                messagebox.showinfo("Maklumat", "Syif sudah bermula. Memuatkan papan pemuka...", parent=win)
                win.destroy()
                shift_popup_open = False
                open_cashier_dashboard(user_id, CASHIER_ID)
                root_window.destroy()
            else:
                print(f"Ralat API: {data2.get('message', 'Tiada mesej ralat')}")
                raise Exception(data2.get("message", "Gagal mula shift!"))
        except Exception as e:
            print(f"Ralat semasa memulakan syif: {e}")
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

def open_cashier_dashboard(user_id, cashier_id):
    global tree_main, item_counter, entry_barcode, search_popup_open, update_qty_popup_open, label_subtotal, label_total, label_change, discount_var, tax_var
    dashboard = tk.Tk()
    dashboard.title("Sistem Kasir")
    dashboard.geometry("1400x900")
    dashboard.attributes("-fullscreen", True)

    search_popup_open = False
    update_qty_popup_open = False

    # Konfigurasi tema customtkinter
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("green")

    # Header frame
    header_frame = ctk.CTkFrame(dashboard, height=54, fg_color="#205065")
    header_frame.pack(fill="x", side="top")
    ctk.CTkLabel(header_frame, text="MyPOS System v1.0", font=("Arial", 20, "bold"), text_color="white").pack(side="left", padx=20)
    label_shift_info = ctk.CTkLabel(header_frame, text="Shift: - | Cashier: - | Cash Awal: RM 0.00 | Baki Cash: RM 0.00", font=("Arial", 15, "bold"), text_color="#e6e6e6")
    label_shift_info.pack(side="right", padx=20)

    def update_shift_info():
        try:
            resp = requests.get(f"{API_URL}?action=check_shift&user_id={user_id}&cashier_id={cashier_id}", timeout=5)
            data = resp.json()
            print(f"[update_shift_info] Respons API check_shift: {data}")
            if data.get('status') == 'success' and data.get('has_shift'):
                shift = data['shift_data']
                cashier = shift.get('cashier_name', '-')
                shift_start = shift.get('shift_start', '-')
                cash_start = float(shift.get('cash_start', 0))
                cash_end = float(shift.get('cash_end', 0))
                info = f"Shift: {shift_start} | Cashier: {cashier} | Cash Awal: RM {cash_start:.2f} | Baki Cash: RM {cash_end:.2f}"
                print(f"[update_shift_info] Syif aktif dikesan: {info}")
            else:
                info = "Shift: - | Cashier: - | Cash Awal: RM 0.00 | Baki Cash: RM 0.00"
            label_shift_info.configure(text=info)
        except Exception as e:
            print(f"[update_shift_info] Ralat: {e}")
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

    # Konfigurasi gaya Treeview
    style = ttk.Style()
    style.theme_use("clam")
    style.configure("Cart.Treeview", font=("Arial", 18, "bold"), rowheight=38)
    style.configure("Cart.Treeview.Heading", font=("Arial", 18, "bold"))
    print(f"[open_cashier_dashboard] Cart.Treeview style: {style.lookup('Cart.Treeview', 'font')}")
    print(f"[open_cashier_dashboard] Cart.Treeview.Heading style: {style.lookup('Cart.Treeview.Heading', 'font')}")

    columns = ("ID", "Nama Produk", "Harga", "Kuantiti", "Total", "Jenis Barcode")
    tree_main = ttk.Treeview(cart_frame, columns=columns, show="headings", style="Cart.Treeview")
    print(f"[open_cashier_dashboard] tree_main initialized: {tree_main}")
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
    tree_main.heading("Jenis Barcode", text="Jenis Barcode")
    tree_main.column("Jenis Barcode", width=100)
    tree_main.pack(fill="both", expand=True, padx=10, pady=10)

    sync_frame = ctk.CTkFrame(left, height=150, width=510, fg_color="gray20")
    sync_frame.pack(fill="x", padx=10, pady=5)
    canvas = tk.Canvas(sync_frame, height=150, width=510, bg="gray20")
    scrollbar = ttk.Scrollbar(sync_frame, orient="vertical", command=canvas.yview)
    sync_label = ctk.CTkLabel(canvas, text="[Sync] Menunggu penyegerakan...", font=("Arial", 12), wraplength=480, justify="left", text_color="white")
    canvas.configure(yscrollcommand=scrollbar.set)
    canvas.create_window((0, 0), window=sync_label, anchor="nw")

    def configure_scrollregion(event):
        canvas.configure(scrollregion=canvas.bbox("all"))
        print(f"[configure_scrollregion] Scrollregion dikemas kini: {canvas.bbox('all')}")

    sync_label.bind("<Configure>", configure_scrollregion)
    scrollbar.pack(side="right", fill="y")
    canvas.pack(side="left", fill="both", expand=True)

    sync_queue = queue.Queue()
    sync_thread = threading.Thread(target=auto_sync, args=(sync_queue, sync_label, dashboard, cashier_id), daemon=True)
    update_thread = threading.Thread(target=update_sync_label, args=(sync_queue, sync_label, dashboard), daemon=True)
    print(f"[open_cashier_dashboard] Memulakan sync_thread dan update_thread untuk cashier_id: {cashier_id}")
    sync_thread.start()
    update_thread.start()

    sales_frame = tk.Frame(notebook)
    notebook.add(sales_frame, text="Jualan Hari Ini")
    sales_columns = ("No", "Resit", "Tarikh/Masa", "Jumlah", "Diskaun", "Jumlah Bayaran", "Baki Pulangan", "Kaedah Bayaran", "Status")
    sales_tree = ttk.Treeview(sales_frame, columns=sales_columns, show="headings")
    for col in sales_columns:
        sales_tree.heading(col, text=col)
        sales_tree.column(col, width=110)
    sales_tree.pack(fill="both", expand=True, padx=10, pady=10)
    sales_btn_frame = tk.Frame(sales_frame)
    sales_btn_frame.pack(fill="x", padx=10, pady=(6, 2))

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
                        f"RM {float(sale['total']):.2f}",
                        f"RM {float(sale['discount']):.2f}",
                        f"RM {float(sale['amount_paid']):.2f}",
                        f"RM {float(sale['change_given']):.2f}",
                        sale['payment_method'], sale['status']
                    ))
        except Exception as e:
            messagebox.showerror("Error", f"Gagal muat jualan: {e}")

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
            print_receipt(items, total, amount_paid, payment_method, customer_info, discount, tax, receipt_no, sale_date)
        except Exception as e:
            messagebox.showerror("Error", f"Gagal dapatkan/print resit: {e}")

    btn_refresh = tk.Button(sales_btn_frame, text="Refresh", command=load_today_sales, bg="#3498db", fg="white", font=("Arial", 11, "bold"))
    btn_refresh.pack(side="left", padx=2)
    btn_print = tk.Button(sales_btn_frame, text="Print Resit", command=print_selected_receipt, bg="#27ae60", fg="white", font=("Arial", 11, "bold"))
    btn_print.pack(side="left", padx=2)

    from inventory_gui import open_inventory_management
    btn_inventory = tk.Button(sales_btn_frame, text="Inventory", bg="#FF9900", fg="white", font=("Arial", 11, "bold"), command=lambda: open_inventory_management(user_id))
    btn_inventory.pack(side="left", padx=2)

    def tutup_shift(user_id, cashier_id):
        win = tk.Toplevel(dashboard)
        win.title("Tutup Shift")
        win.geometry("350x200")
        tk.Label(win, text="Anda pasti ingin tutup shift?", font=("Arial", 13, "bold")).pack(pady=10)
        tk.Label(win, text="Baki Tunai Akhir (RM):").pack()
        entry_baki = tk.Entry(win, font=("Arial", 15), width=15)
        entry_baki.pack(pady=7)
        entry_baki.focus()

        # Ambil baki tunai akhir dari API check_shift
        try:
            resp = requests.get(f"{API_URL}?action=check_shift&user_id={user_id}&cashier_id={cashier_id}", timeout=5)
            data = resp.json()
            if data.get('status') == 'success' and data.get('has_shift'):
                cash_end = float(data['shift_data'].get('cash_end', 0))
                entry_baki.insert(0, f"{cash_end:.2f}")
            else:
                entry_baki.insert(0, "0.00")
        except Exception as e:
            print(f"[tutup_shift] Ralat semasa mendapatkan baki tunai: {e}")
            entry_baki.insert(0, "0.00")
            messagebox.showwarning("Peringatan", f"Gagal mendapatkan baki tunai: {e}. Sila masukkan secara manual.", parent=win)

        def submit_tutup():
            try:
                baki_akhir = float(entry_baki.get())
                print(f"[tutup_shift] Menamatkan syif untuk user_id: {user_id}, cashier_id: {cashier_id}, cash_end: {baki_akhir}")
                resp = requests.post(API_URL, json={
                    "action": "close_shift",
                    "user_id": user_id,
                    "cash_end": baki_akhir,
                    "cashier_id": cashier_id
                }, timeout=10)
                data = resp.json()
                if data.get("status") == "success":
                    messagebox.showinfo("Sukses", "Shift berjaya ditutup!", parent=win)
                    win.destroy()
                    dashboard.destroy()
                    show_login_window()
                else:
                    print(f"[tutup_shift] Ralat API: {data.get('message', 'Tiada mesej ralat')}")
                    raise Exception(data.get("message", "Gagal tutup shift!"))
            except ValueError:
                messagebox.showerror("Error", "Sila masukkan jumlah baki tunai yang sah!", parent=win)
            except Exception as e:
                print(f"[tutup_shift] Ralat: {e}")
                messagebox.showerror("Error", f"Gagal tutup shift: {e}", parent=win)

        tk.Button(win, text="Tutup Shift", command=submit_tutup, bg="#32CD32", fg="white", font=("Arial", 12, "bold")).pack(pady=10)
        tk.Button(win, text="Batal", command=win.destroy).pack()

        # Ikat kekunci Enter untuk menyerahkan
        entry_baki.bind("<Return>", lambda e: submit_tutup())
        win.bind("<Return>", lambda e: submit_tutup() if dashboard.focus_get() != entry_baki else None)

        win.transient(dashboard)
        win.grab_set()
        win.wait_window()

    btn_tutup_shift = tk.Button(sales_btn_frame, text="Tutup Shift", bg="#FFA500", fg="black", font=("Arial", 11, "bold"), command=lambda: tutup_shift(user_id, cashier_id))
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

    button_grid = ctk.CTkFrame(right)
    button_grid.pack(pady=3, fill="x", padx=26)
    btn_detect = ctk.CTkButton(button_grid, text="Detect \n Printer", fg_color="#9444DD", text_color="white", font=("Arial", 17, "bold"), command=lambda: select_printer_popup(dashboard), width=120, height=50)
    btn_detect.grid(row=0, column=0, padx=5, pady=5, sticky="ew")
    btn_virtual = ctk.CTkButton(button_grid, text="Virtual Keyboard \n [F3]", fg_color="#20B2AA", text_color="white", font=("Arial", 17, "bold"), command=lambda: CTkVirtualKeyboard(dashboard), width=120, height=50)
    btn_virtual.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
    btn_cari = ctk.CTkButton(button_grid, text="Cari Produk \n [F4]", fg_color="#FFD700", text_color="black", font=("Arial", 17, "bold"), command=lambda: open_search_product(), width=120, height=50)
    btn_cari.grid(row=1, column=0, padx=5, pady=5, sticky="ew")
    btn_hapus = ctk.CTkButton(button_grid, text="Hapus \n Produk", fg_color="#FF6347", text_color="white", font=("Arial", 17, "bold"), command=lambda: remove_item(), width=120, height=50)
    btn_hapus.grid(row=1, column=1, padx=5, pady=5, sticky="ew")
    btn_laci = ctk.CTkButton(button_grid, text="Buka Laci \n [F6]", fg_color="#4169E1", text_color="white", font=("Arial", 17, "bold"), command=open_cash_drawer, width=120, height=50)
    btn_laci.grid(row=2, column=0, padx=5, pady=5, sticky="ew")

    def confirm_logout(dashboard, user_id, cashier_id):
        def on_keluar_tanpa_shift():
            result = messagebox.askyesno("Keluar Tanpa Tutup Shift", "Anda pasti mahu keluar tanpa tutup shift?\nShift masih aktif.", parent=dashboard)
            if result:
                dashboard.destroy()
                show_login_window()
        def on_tutup_shift():
            tutup_shift(user_id, cashier_id)
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

    btn_keluar = ctk.CTkButton(button_grid, text="Keluar \n [F10]", fg_color="#B22222", text_color="white", font=("Arial", 17, "bold"), command=lambda: confirm_logout(dashboard, user_id, cashier_id), width=120, height=50)
    btn_keluar.grid(row=2, column=1, padx=5, pady=5, sticky="ew")
    button_grid.columnconfigure(0, weight=1)
    button_grid.columnconfigure(1, weight=1)

    ctk.CTkButton(right, text="Selesaikan Transaksi \n [F2]", font=("Arial", 19, "bold"), width=120, height=80, fg_color="#32CD32", command=lambda: complete_transaction()).pack(fill="x", padx=30, pady=30)

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

    def update_payment_method(*args):
        if payment_var.get() == "Hutang":
            customer_info_popup()
            entry_amount_paid.configure(state="disabled")
            entry_amount_paid.delete(0, tk.END)
            label_change.configure(text="Hutang", text_color="orange")
        else:
            entry_amount_paid.configure(state="normal")
            entry_amount_paid.delete(0, tk.END)
            calculate_change()
    payment_var.trace_add("write", update_payment_method)

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
            label_change.configure(text=f"RM {change:.2f}" if change >= 0 else f"-RM {abs(change):.2f}", text_color="white" if change >= 0 else "red")
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
            tree_main.focus(last_item)
            tree_main.see(last_item)

    def scan_barcode(barcode):
        if not barcode:
            return
        try:
            res = requests.get(f"{API_URL}?barcode={barcode}")
            res.raise_for_status()
            print(f"[scan_barcode] Raw response (product): {res.text}")
            product = res.json()
            if not product or 'data' not in product or 'id' not in product['data']:
                messagebox.showwarning("Peringatan", "Produk tidak ditemukan!")
                return
            product_data = product['data']
            product_name = product_data['name']
            price_float = float(product_data['price'])
            barcode_type = product_data['barcode_type']
            is_weighable = int(product_data.get('is_weighable', 0))

            res_details = requests.get(f"{API_URL}?action=get_product_details&barcode={barcode}")
            res_details.raise_for_status()
            print(f"[scan_barcode] Raw response (details): {res_details.text}")
            details = res_details.json()
            if not details or 'data' not in details or 'unit_per_pack' not in details['data'] or 'pack_per_box' not in details['data']:
                messagebox.showwarning("Peringatan", f"Gagal dapatkan butiran produk! Details: {details}")
                return
            details_data = details['data']
            unit_per_pack = int(details_data.get('unit_per_pack', 1))
            pack_per_box = int(details_data.get('pack_per_box', 1))

            if is_weighable:
                win = tk.Toplevel()
                win.title("Masukkan Berat (KG)")
                win.geometry("320x120")
                tk.Label(win, text=f"Masukkan berat (kg) untuk {product_name} ({barcode_type}):", font=("Arial", 13)).pack()
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
                if barcode_type == 'unit':
                    quantity = 1
                elif barcode_type == 'pack':
                    quantity = 1
                elif barcode_type == 'box':
                    quantity = 1

            for item in tree_main.get_children():
                values = tree_main.item(item, 'values')
                if values[1] == product_name and values[5] == barcode_type:
                    old_qty = float(values[3])
                    new_quantity = int(old_qty + quantity) if not is_weighable else old_qty + quantity
                    new_total = new_quantity * price_float
                    qty_display = f"{new_quantity}" if not is_weighable else f"{new_quantity:.3f}"
                    tree_main.item(item, values=(values[0], values[1], f"RM {price_float:.2f}", qty_display, f"RM {new_total:.2f}", barcode_type))
                    update_totals()
                    entry_barcode.delete(0, tk.END)
                    highlight_last_cart_item()
                    return

            idx = item_counter[0]
            total = quantity * price_float
            qty_display = f"{quantity}" if not is_weighable else f"{quantity:.3f}"
            tree_main.insert("", "end", values=(idx, product_name, f"RM {price_float:.2f}", qty_display, f"RM {total:.2f}", barcode_type))
            item_counter[0] += 1
            update_totals()
            entry_barcode.delete(0, tk.END)
            highlight_last_cart_item()
        except Exception as e:
            messagebox.showerror("Error", f"Gagal scan barcode: {e}")

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

    def do_search(*args):
        global win, results_tree, search_var, products_data
        query = search_var.get().strip()
        print(f"[do_search] Executing search with query: {query}")
        if len(query) < 2:
            results_tree.delete(*results_tree.get_children())
            print("[do_search] Query too short, clearing results")
            return
        try:
            params = {'action': 'search_products', 'query': query, 'limit': 15}
            response = requests.get(API_URL, params=params, timeout=10)
            print(f"[do_search] API URL: {response.url}")
            print(f"[do_search] API response status: {response.status_code}")
            print(f"[do_search] API response: {response.text}")
            data = response.json()
            if not isinstance(data, dict) or 'data' not in data:
                raise ValueError("Format response tidak valid")

            products = data['data']
            print(f"[do_search] Products found: {len(products)}")
            products_data.clear()
            products_data.extend(products)
            results_tree.delete(*results_tree.get_children())

            results_tree.tag_configure("low_stock", background="#FFCCCC")
            results_tree.tag_configure("pack_item", background="#CCE5FF")
            results_tree.tag_configure("box_item", background="#CCFFCC")
            results_tree.tag_configure("weighable_item", background="#FFFFCC")

            for product in products:
                price = float(product.get('price', 0))
                stock = int(product.get('stock', 0))
                name = product.get("name", "")
                barcode = product.get("barcode", "")
                barcode_type = product.get("barcode_type", "unit")
                is_weighable = int(product.get("is_weighable", 0))

                item_id = results_tree.insert("", "end", values=(
                    name,
                    f"RM {price:.2f}",
                    stock,
                    barcode
                ))

                tags = []
                if barcode_type == "pack":
                    tags.append("pack_item")
                elif barcode_type == "box":
                    tags.append("box_item")
                if is_weighable:
                    tags.append("weighable_item")
                if stock < 5:
                    tags = ["low_stock"]
                results_tree.item(item_id, tags=tuple(tags))
                print(f"[do_search] Inserted product: {product}")
        except Exception as e:
            print(f"[do_search] Search error: {e}")
            messagebox.showerror("Error", f"Gagal memuat hasil carian: {e}\nResponse: {response.text[:100]}", parent=win)

    def open_search_product():
        global win, results_tree, search_var, products_data, search_popup_open, tree_main, item_counter, entry_barcode

        if search_popup_open:
            return
        search_popup_open = True
        products_data = []

        win = tk.Toplevel()
        win.title("Cari Produk")
        win.geometry("800x400")

        win.transient()
        win.grab_set()
        win.focus_force()
        win.attributes("-topmost", True)

        def close_popup():
            global search_popup_open
            search_popup_open = False
            win.destroy()
            entry_barcode.focus_set()

        win.protocol("WM_DELETE_WINDOW", close_popup)
        win.bind("<Escape>", lambda e: close_popup())

        search_var = tk.StringVar()
        search_var.trace("w", do_search)
        search_entry = tk.Entry(win, textvariable=search_var, font=("Arial", 15))
        search_entry.pack(fill="x", padx=10, pady=10)
        search_entry.focus()

        cols = ("Nama", "Harga", "Stok", "Barcode")
        results_tree = ttk.Treeview(win, columns=cols, show="headings")
        for col in cols:
            results_tree.heading(col, text=col)
            results_tree.column(col, width=200 if col == "Nama" else 100)
        results_tree.pack(fill="both", expand=True, padx=10, pady=10)

        def on_single_click(event):
            item = results_tree.identify_row(event.y)
            if item:
                results_tree.selection_set(item)
                results_tree.focus(item)

        def on_tree_select(event=None):
            item = results_tree.focus()
            if not item:
                return
            selected = results_tree.item(item, "values")
            if selected:
                add_selected_product()

        search_entry.bind("<Return>", on_tree_select)
        results_tree.bind("<Button-1>", on_single_click)
        results_tree.bind("<Double-1>", on_tree_select)

        do_search()

        items = results_tree.get_children()
        if items:
            results_tree.selection_set(items[0])
            results_tree.focus(items[0])

    def add_selected_product():
        global tree_main, item_counter, products_data, win, search_popup_open
        if not results_tree.focus():
            messagebox.showwarning("Peringatan", "Pilih produk terlebih dahulu!", parent=win)
            return
        try:
            vals = results_tree.item(results_tree.focus(), "values")
            print(f"[add_selected_product] Selected values: {vals}")
            product_name = vals[0]
            price_str = vals[1].replace("RM", "").strip()
            price = float(price_str)
            barcode = vals[3]
            barcode_type = None
            is_weighable = 0
            for product in products_data:
                if product.get('name') == product_name:
                    is_weighable = int(product.get('is_weighable', 0))
                    barcode_type = product.get('barcode_type', 'unit')
                    break
            if not barcode_type:
                messagebox.showerror("Error", "Jenis barcode tidak ditemui untuk produk ini.", parent=win)
                return
            print(f"[add_selected_product] Adding product: {product_name}, Barcode: {barcode}, Type: {barcode_type}, Weighable: {is_weighable}")
            
            res_details = requests.get(f"{API_URL}?action=get_product_details&barcode={barcode}", timeout=5)
            res_details.raise_for_status()
            details = res_details.json()
            if not details or 'data' not in details or 'id' not in details['data']:
                messagebox.showwarning("Peringatan", f"Gagal dapatkan butiran produk! Details: {details}")
                return
            details_data = details['data']
            item_id = details_data.get('id')
            unit_per_pack = int(details_data.get('unit_per_pack', 1))
            pack_per_box = int(details_data.get('pack_per_box', 1))

            if is_weighable:
                berat_win = tk.Toplevel(win)
                berat_win.title("Masukkan Berat (KG)")
                berat_win.geometry("320x120")
                tk.Label(berat_win, text=f"Masukkan berat (kg) untuk {product_name}:", font=("Arial", 13)).pack()
                qty_entry = tk.Entry(berat_win, font=("Arial", 15), width=10)
                qty_entry.pack(pady=7)
                qty_entry.focus()
                qty_entry.bind("<FocusIn>", lambda e: CTkVirtualKeyboard.set_target_entry(qty_entry))
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
                berat_win.transient(win)
                berat_win.grab_set()
                berat_win.wait_window()
                quantity = result['quantity']
                if not quantity:
                    print("[add_selected_product] No quantity entered, cancelling")
                    return
            else:
                if barcode_type == 'unit':
                    quantity = 1
                elif barcode_type == 'pack':
                    quantity = unit_per_pack
                elif barcode_type == 'box':
                    quantity = unit_per_pack * pack_per_box

            for item in tree_main.get_children():
                v = tree_main.item(item, 'values')
                if v[1] == product_name and v[5] == barcode_type:
                    old_qty = float(v[3])
                    new_quantity = int(old_qty + 1) if not is_weighable else old_qty + quantity
                    new_total = new_quantity * price
                    qty_display = f"{new_quantity}" if not is_weighable else f"{new_quantity:.3f}"
                    tree_main.item(item, values=(v[0], v[1], f"RM {price:.2f}", qty_display, f"RM {new_total:.2f}", barcode_type))
                    print(f"[add_selected_product] Updated existing item: {product_name}, New Quantity: {new_quantity}, Total: {new_total}")
                    update_totals()
                    win.destroy()
                    highlight_last_cart_item()
                    search_popup_open = False
                    return
            idx = item_counter[0]
            total = price * (1 if is_weighable or barcode_type == 'unit' else (unit_per_pack if barcode_type == 'pack' else unit_per_pack * pack_per_box))
            qty_display = f"1" if not is_weighable else f"{quantity:.3f}"
            tree_main.insert("", "end", values=(idx, product_name, f"RM {price:.2f}", qty_display, f"RM {total:.2f}", barcode_type))
            print(f"[add_selected_product] Inserted new item: {product_name}, Quantity: {qty_display}, Total: {total}")
            item_counter[0] += 1
            update_totals()
            win.destroy()
            highlight_last_cart_item()
            search_popup_open = False
        except Exception as e:
            print(f"[add_selected_product] Error: {e}")
            messagebox.showerror("Error", f"Gagal menambah produk ke troli: {e}", parent=win)

    def tree_main_double_click(event):
        sel = tree_main.focus()
        if not sel:
            return
        item_id = tree_main.item(sel, 'values')[0]
        update_quantity_modal(item_id, tree_main)

    tree_main.bind("<Double-1>", tree_main_double_click)

    def update_quantity_modal(item_id, tree):
        global update_qty_popup_open
        if update_qty_popup_open:
            return
        update_qty_popup_open = True
        selected_item = None
        for item in tree.get_children():
            if tree.item(item, 'values')[0] == item_id:
                selected_item = item
                break
        if not selected_item:
            messagebox.showwarning("Peringatan", "Item tidak ditemui!")
            update_qty_popup_open = False
            return
        current_values = tree.item(selected_item, 'values')
        product_name = current_values[1]
        current_quantity = current_values[3]
        current_price = float(current_values[2].replace("RM", "").strip())
        try:
            is_weighable = (float(current_quantity) != int(float(current_quantity)))
        except Exception:
            is_weighable = False
        modal = tk.Toplevel(tree.master)
        modal.title(f"Kemaskini Kuantiti & Harga: {product_name}")
        modal.geometry("320x420")
        tk.Label(modal, text=f"Produk: {product_name}", font=("Arial", 13, "bold")).pack(pady=10)
        tk.Label(modal, text="Kuantiti Baru:", font=("Arial", 13)).pack(pady=5)
        quantity_entry = tk.Entry(modal, font=("Arial", 14), width=10)
        quantity_entry.insert(0, str(current_quantity))
        quantity_entry.pack(pady=5)
        quantity_entry.focus()
        tk.Label(modal, text="Harga Baru (RM):", font=("Arial", 13)).pack(pady=5)
        price_entry = tk.Entry(modal, font=("Arial", 14), width=10)
        price_entry.insert(0, f"{current_price:.2f}")
        price_entry.pack(pady=5)
        price_entry.bind("<FocusIn>", lambda e: CTkVirtualKeyboard.set_target_entry(price_entry))

        def submit_quantity():
            try:
                val_quantity = quantity_entry.get().strip()
                if is_weighable:
                    new_quantity = float(val_quantity)
                    if new_quantity < 0.001:
                        raise ValueError("Kuantiti mestilah lebih besar daripada 0")
                else:
                    if '.' in val_quantity:
                        raise ValueError("Kuantiti untuk barang unit mesti nombor bulat")
                    new_quantity = int(val_quantity)
                    if new_quantity < 1:
                        raise ValueError("Kuantiti mestilah lebih besar daripada 0")
                val_price = price_entry.get().strip()
                new_price = float(val_price)
                if new_price <= 0:
                    raise ValueError("Harga mesti lebih besar daripada 0")
                new_total = new_price * new_quantity
                qty_display = f"{new_quantity}" if not is_weighable else f"{new_quantity:.3f}"
                tree.item(selected_item, values=(
                    current_values[0], current_values[1],
                    f"RM {new_price:.2f}", qty_display,
                    f"RM {new_total:.2f}"
                ))
                update_totals()
                modal.destroy()
                global update_qty_popup_open
                update_qty_popup_open = False
                tree.selection_set(selected_item)
                tree.focus(selected_item)
            except ValueError as e:
                messagebox.showerror("Input Tidak Sah", str(e), parent=modal)
                quantity_entry.focus()
            except Exception as e:
                messagebox.showerror("Error", f"Ralat: {e}", parent=modal)
                quantity_entry.focus()

        tk.Button(modal, text="Simpan", command=submit_quantity, width=12, bg="#32CD32", fg="white").pack(pady=10)
        tk.Button(modal, text="Batal", command=lambda: [modal.destroy(), globals().update(update_qty_popup_open=False)], width=12).pack()
        modal.bind('<Return>', lambda e: submit_quantity())
        modal.protocol("WM_DELETE_WINDOW", lambda: [modal.destroy(), globals().update(update_qty_popup_open=False)])
        modal.transient(dashboard)
        modal.grab_set()
        modal.wait_window()

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
            messagebox.showerror("Error", f"Gagal muat stok rendah: {e}")

    def complete_transaction():
        try:
            items = []
            for item in tree_main.get_children():
                values = tree_main.item(item, 'values')
                product_name = values[1]
                qty_display = values[3]
                price = float(values[2].replace("RM", ""))
                total = float(values[4].replace("RM", ""))
                barcode_type = values[5]
                items.append({
                    'name': product_name,
                    'quantity': float(qty_display),
                    'price': price,
                    'total': total,
                    'barcode_type': barcode_type
                })
            if not items:
                messagebox.showwarning("Peringatan", "Tidak ada item dalam troli!")
                return
            subtotal = sum(i["total"] for i in items)
            discount = float(entry_discount.get() or 0)
            tax = float(entry_tax.get() or 0)
            total = subtotal - discount + tax
            payment_method = payment_var.get()
            payment_method_map = {"Tunai": 1, "Hutang": 2, "Kad Kredit/Debit": 3, "Online Transfer": 4, "QR Kod": 5}
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
            sale_id = str(uuid.uuid4())
            transaction_data = {
                "action": "save_transaction",
                "sale_id": sale_id,
                "items": items,
                "total": total,
                "discount": discount,
                "tax": tax,
                "amount_paid": amount_paid,
                "user_id": user_id,
                "cashier_id": cashier_id,
                "payment_method": payment_method,
                "payment_method_id": payment_method_id,
                "customer_info": customer_data if payment_method == "Hutang" else None
            }
            response = requests.post(API_URL, json=transaction_data, timeout=10)
            response.raise_for_status()
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
            messagebox.showerror("Error", f"Gagal proses transaksi: {e}")
            print(f"[complete_transaction] Error: {e}")

    dashboard.after(700, lambda: CTkVirtualKeyboard(dashboard))
    entry_barcode.bind("<Return>", lambda e: scan_barcode(entry_barcode.get()))
    entry_discount.bind("<KeyRelease>", update_totals)
    entry_tax.bind("<KeyRelease>", update_totals)
    entry_amount_paid.bind("<KeyRelease>", calculate_change)

    def keep_focus_barcode():
        focus_widget = dashboard.focus_get()
        allowed_entries = {entry_barcode, entry_discount, entry_tax, entry_amount_paid}
        if not search_popup_open and not update_qty_popup_open and (focus_widget not in allowed_entries):
            try:
                if tree_main.get_children():
                    tree_main.focus_set()
                else:
                    entry_barcode.focus_set()
            except Exception:
                pass
        dashboard.after(20000, keep_focus_barcode)
    keep_focus_barcode()

    dashboard.bind('<F1>', lambda e: entry_amount_paid.focus_set())
    dashboard.bind('<F2>', lambda e: complete_transaction())
    dashboard.bind('<F3>', lambda e: CTkVirtualKeyboard(dashboard))
    dashboard.bind('<F4>', lambda e: open_search_product())
    dashboard.bind('<F5>', lambda e: update_quantity_modal(tree_main.item(tree_main.focus(), 'values')[0], tree_main) if tree_main.focus() else messagebox.showwarning("Peringatan", "Pilih item terlebih dahulu!"))
    dashboard.bind('<F6>', lambda e: open_cash_drawer())
    dashboard.bind('<F10>', lambda e: confirm_logout(dashboard, user_id, cashier_id))

    def select_printer_popup(master):
        global SELECTED_PRINTER_PORT
        selected_port = detect_thermal_printer_serial()
        if selected_port:
            SELECTED_PRINTER_PORT = selected_port
            messagebox.showinfo("Printer", f"Printer thermal dikesan di port: {selected_port}")
        else:
            selected_printer = select_windows_printer(master)
            if selected_printer:
                messagebox.showinfo("Printer", f"Printer Windows dipilih: {selected_printer}")
            else:
                messagebox.showwarning("Peringatan", "Tiada printer dikesan!")

    load_today_sales()
    load_low_stock_products()
    dashboard.mainloop()

if __name__ == "__main__":
    show_login_window()


receipt_lines = [
    "\x1B\x40",        # Initialize printer
    "\x1B\x21\x20",    # Font style
    "\x1B\x61\x01",    # Centered

    # --- LOGO TEKS DMMT ---
    "  ____  __  __ __  __ _______ ",
    " |  _ \\|  \\/  |  \\/  |__   __|",
    " | | | | \\  / | \\  / |  | |   ",
    " | |_| | |\\/| | |\\/| |  | |   ",
    " |____/|_|  |_|_|  |_|  |_|   ",
    "                              ",
    "         D M M T             ",
    "=" * LEBAR,
    "\x1B\x61\x00",    # Kembali kiri

    # --- Seterusnya isi resit biasa akan disambung di sini ---
    f"{'Diskaun:':<16}{discount:>16.2f}",
    f"{'Cukai:':<16}{tax:>16.2f}",
    f"{'Dibayar:':<16}{amount_paid:>16.2f}",
    f"{'Baki:':<16}{change:>16.2f}",
    f"{'Total:':<16}{grand_total:>16.2f}",
    "=" * LEBAR,
    f"Bayar: {payment_method}",
    "=" * LEBAR,
    "\x1B\x61\x01",
    "Terima kasih! Barang tidak boleh ditukar",
    "\x1B\x61\x00",
    "=" * LEBAR,
    "\x1B\x61\x01",
    f"\x1D\x68\x50\x1D\x77\x02\x1D\x6B\x49{chr(len(receipt_no))}{receipt_no}",
    "\x1B\x61\x00",
    "\n\n",
    "\x1D\x56\x41\x03",  # Potong kertas
    "\x1B\x70\x00\x19\xFA"  # Buka cash drawer
]
