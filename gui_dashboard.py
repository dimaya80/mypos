import customtkinter as ctk
from tkinter import ttk, messagebox
from db import get_products, save_transaction

class Dashboard(ctk.CTk):
    def __init__(self, user):
        super().__init__()
        self.user = user
        self.title("MyPOS Dashboard")
        self.geometry("1200x800")
        self.cart = []
        self.build_ui()

    def build_ui(self):
        ctk.CTkLabel(self, text=f"Selamat Datang {self.user['nama']}", font=("Arial", 16)).pack(pady=10)
        self.search_var = ctk.StringVar()
        ctk.CTkEntry(self, textvariable=self.search_var).pack()
        ctk.CTkButton(self, text="Cari Produk", command=self.load_products).pack()
        self.product_tree = ttk.Treeview(self, columns=("ID", "Nama", "Harga", "Stok"), show="headings")
        for col in ("ID", "Nama", "Harga", "Stok"):
            self.product_tree.heading(col, text=col)
        self.product_tree.pack(fill="x", pady=5)
        self.product_tree.bind("<Double-1>", self.add_to_cart)
        # Table cart
        self.cart_tree = ttk.Treeview(self, columns=("Nama", "Harga", "Qty", "Total"), show="headings")
        for col in ("Nama", "Harga", "Qty", "Total"):
            self.cart_tree.heading(col, text=col)
        self.cart_tree.pack(fill="x", pady=5)
        ctk.CTkButton(self, text="Checkout", command=self.checkout).pack(pady=5)
        self.load_products()

    def load_products(self):
        for row in self.product_tree.get_children():
            self.product_tree.delete(row)
        for p in get_products(self.search_var.get()):
            self.product_tree.insert("", "end", values=(p["id"], p["name"], p["price"], p["stock"]))

    def add_to_cart(self, event):
        selected = self.product_tree.focus()
        if not selected: return
        prod = self.product_tree.item(selected, "values")
        qty = 1  # boleh tambah popup qty
        total = float(prod[2]) * qty
        self.cart.append({"product_id": prod[0], "name": prod[1], "price": float(prod[2]), "quantity": qty, "total": total})
        self.refresh_cart()

    def refresh_cart(self):
        for row in self.cart_tree.get_children():
            self.cart_tree.delete(row)
        for item in self.cart:
            self.cart_tree.insert("", "end", values=(item["name"], item["price"], item["quantity"], item["total"]))

    def checkout(self):
        if not self.cart:
            messagebox.showwarning("Kosong", "Tiada item dalam troli.")
            return
        total = sum(item["total"] for item in self.cart)
        trx_data = {
            "user_id": self.user["id"],
            "total": total,
            "discount": 0,
            "tax": 0,
            "payment_method": "Tunai",
            "amount_paid": total
        }
        save_transaction(trx_data, self.cart)
        messagebox.showinfo("Berjaya", "Transaksi berjaya!")
        self.cart = []
        self.refresh_cart()
        self.load_products()
