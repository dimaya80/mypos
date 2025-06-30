# Optional: Model/data class
# NOT MANDATORY - just structure to help with OOP and type hints

from dataclasses import dataclass

@dataclass
class Product:
    id: int
    name: str
    price: float
    stock: int
    barcode: str

@dataclass
class User:
    id: int
    username: str
    nama: str

@dataclass
class Supplier:
    id: int
    supplier_name: str

# Tambah lain jika mahu
