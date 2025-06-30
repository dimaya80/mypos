import os
import tempfile
import platform

def print_receipt(items, total, payment_method, amount_paid, change=0.0, cashier_name="", receipt_no="", date_time="", shop_name="MyPOS", shop_address="", shop_phone="", footer_note="Terima kasih!"):
    """
    Fungsi cetak resit ringkas ke printer default.
    Boleh diubah untuk thermal printer (ESC/POS) jika perlu.
    """
    # Format barangan
    lines = []
    lines.append(f"{shop_name}".center(40))
    if shop_address:
        lines.append(shop_address.center(40))
    if shop_phone:
        lines.append(shop_phone.center(40))
    lines.append("-" * 40)
    if receipt_no:
        lines.append(f"No Resit : {receipt_no}")
    if date_time:
        lines.append(f"Tarikh   : {date_time}")
    if cashier_name:
        lines.append(f"Juruwang : {cashier_name}")
    lines.append("-" * 40)
    lines.append(f"{'Item':<20}{'Qty':>4}{'RM':>8}{'Tot':>8}")
    lines.append("-" * 40)
    for item in items:
        name = str(item.get("name", ""))[:20]
        qty = str(item.get("quantity", ""))
        price = "{:.2f}".format(float(item.get("price", 0)))
        total_item = "{:.2f}".format(float(item.get("total", 0)))
        lines.append(f"{name:<20}{qty:>4}{price:>8}{total_item:>8}")
    lines.append("-" * 40)
    lines.append(f"{'Jumlah':<27}{'RM':>3}{total:>9.2f}")
    lines.append(f"{'Bayar':<27}{'RM':>3}{amount_paid:>9.2f}")
    lines.append(f"{'Baki':<27}{'RM':>3}{change:>9.2f}")
    lines.append(f"{'Bayaran':<10}: {payment_method}")
    lines.append("-" * 40)
    if footer_note:
        lines.append(footer_note.center(40))
    lines.append("\n\n")

    receipt_text = "\n".join(lines)

    # CETAK PRINTER DEFAULT (Windows/Linux/MacOS)
    if platform.system() == "Windows":
        with tempfile.NamedTemporaryFile(delete=False, mode='w', encoding='utf-8', suffix='.txt') as f:
            f.write(receipt_text)
            temp_filename = f.name
        # Print to default printer
        os.startfile(temp_filename, "print")
    elif platform.system() == "Linux":
        with tempfile.NamedTemporaryFile(delete=False, mode='w', encoding='utf-8', suffix='.txt') as f:
            f.write(receipt_text)
            temp_filename = f.name
        # Requires 'lpr' installed
        os.system(f"lpr {temp_filename}")
    elif platform.system() == "Darwin":  # MacOS
        with tempfile.NamedTemporaryFile(delete=False, mode='w', encoding='utf-8', suffix='.txt') as f:
            f.write(receipt_text)
            temp_filename = f.name
        os.system(f"lp {temp_filename}")
    else:
        print("Platform tidak disokong untuk cetak automatik.")
        print(receipt_text)

def open_cash_drawer(printer_name=None):
    """
    Fungsi untuk buka laci wang melalui printer (ESC/POS).
    Hantar kod ESC/POS ke printer -- hanya berfungsi untuk thermal printer yang sokong ESC/POS!
    """
    # ESC/POS command untuk buka laci wang: '\x1b\x70\x00\x19\xfa'
    # Cara ini hanya berfungsi jika printer thermal anda diset sebagai default printer dan sambungan USB/Serial.
    # Untuk Windows/Linux/Mac, gunakan raw printing method jika perlu.
    import io

    kick_drawer_cmd = b'\x1b\x70\x00\x19\xfa'

    if platform.system() == "Windows":
        try:
            # pywin32 diperlukan untuk raw printing (pip install pywin32)
            import win32print, win32ui
            printer = printer_name or win32print.GetDefaultPrinter()
            hprinter = win32print.OpenPrinter(printer)
            hjob = win32print.StartDocPrinter(hprinter, 1, ("Open Drawer", None, "RAW"))
            win32print.StartPagePrinter(hprinter)
            win32print.WritePrinter(hprinter, kick_drawer_cmd)
            win32print.EndPagePrinter(hprinter)
            win32print.EndDocPrinter(hprinter)
            win32print.ClosePrinter(hprinter)
        except Exception as e:
            print("Gagal buka laci wang:", e)
    elif platform.system() == "Linux":
        try:
            # Pastikan user boleh echo ke /dev/usb/lp0 atau /dev/usb/lp1
            with open('/dev/usb/lp0', 'wb') as f:
                f.write(kick_drawer_cmd)
        except Exception as e:
            print("Gagal buka laci wang:", e)
    elif platform.system() == "Darwin":
        # MacOS: Cuba lpraw jika ada, atau gunakan pyusb/pyserial jika printer di Serial/USB
        print("Buka laci wang pada MacOS perlu implementasi khusus (pyserial/pyusb).")
    else:
        print("Fungsi buka laci wang tidak disokong pada platform ini.")

# Contoh penggunaan:
# print_receipt(items, total, "Tunai", amount_paid, change, cashier_name, receipt_no, date_time)
# open_cash_drawer()
