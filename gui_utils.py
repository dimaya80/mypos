import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox

def show_virtual_keyboard(entry_widget, title=""):
    """
    Papar papan kekunci maya untuk input nombor pada entry_widget.
    Boleh digunakan untuk entry tkinter atau customtkinter.
    """
    # Elak buka lebih dari satu keyboard
    if hasattr(show_virtual_keyboard, "keyboard_window") and \
            show_virtual_keyboard.keyboard_window.winfo_exists():
        show_virtual_keyboard.keyboard_window.lift()
        show_virtual_keyboard.keyboard_window.focus_force()
        return

    def on_key_press(key):
        if key == '⌫':  # Backspace
            current = entry_widget.get()
            if len(current) > 0:
                entry_widget.delete(len(current)-1, tk.END)
        elif key == 'OK':
            show_virtual_keyboard.keyboard_window.destroy()
        else:
            entry_widget.insert(tk.END, key)

    show_virtual_keyboard.keyboard_window = ctk.CTkToplevel()
    show_virtual_keyboard.keyboard_window.title(f"Keyboard Nombor - {title}" if title else "Keyboard Nombor")
    show_virtual_keyboard.keyboard_window.geometry("300x400")
    show_virtual_keyboard.keyboard_window.resizable(False, False)
    show_virtual_keyboard.keyboard_window.grab_set()

    btn_style = {'font': ('Arial', 14), 'width': 60, 'height': 60}

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

def show_popup_info(msg, title="Maklumat"):
    """
    Papar popup maklumat/info ringkas.
    """
    messagebox.showinfo(title, msg)

def show_popup_warning(msg, title="Peringatan"):
    """
    Papar popup amaran.
    """
    messagebox.showwarning(title, msg)

def show_popup_error(msg, title="Ralat"):
    """
    Papar popup ralat/kesalahan.
    """
    messagebox.showerror(title, msg)

def show_popup_question(msg, title="Sahkan"):
    """
    Popup Yes/No, return True/False
    """
    return messagebox.askyesno(title, msg)

def show_popup_custom(title, message, buttons):
    """
    Papar custom popup dengan pilihan butang.
    buttons: List of (label, callback)
    Return index butang yang dipilih.
    """
    popup = ctk.CTkToplevel()
    popup.title(title)
    popup.geometry("400x200")
    popup.resizable(False, False)
    ctk.CTkLabel(popup, text=message, font=("Arial", 14), wraplength=360).pack(pady=30, padx=20)
    btn_frame = ctk.CTkFrame(popup)
    btn_frame.pack(pady=10)
    results = {'btn_pressed': None}
    def make_callback(idx, cb):
        def _cb():
            results['btn_pressed'] = idx
            if cb:
                cb()
            popup.destroy()
        return _cb
    for idx, (label, cb) in enumerate(buttons):
        ctk.CTkButton(btn_frame, text=label, command=make_callback(idx, cb), width=120, font=("Arial", 12)).pack(side="left", padx=10)
    popup.wait_window()
    return results['btn_pressed']
