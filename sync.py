# Fungsi auto-sync ke server pusat
# RANGKA - belum implement penuh

import threading
import time

def sync_to_server():
    while True:
        try:
            # Ambil data belum sync & hantar ke server pusat
            pass
        except Exception as e:
            print("Sync error:", e)
        time.sleep(10)

def start_sync_thread():
    t = threading.Thread(target=sync_to_server, daemon=True)
    t.start()
