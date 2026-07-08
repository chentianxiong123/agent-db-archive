"""One-shot pipeline"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from scripts.config import init_config
import importlib
find_key = importlib.import_module("1_find_key.find_key").find_key
decrypt_db = importlib.import_module("2_decrypt_db.decrypt").decrypt_db
export_chats = importlib.import_module("3_export_chats.export_jsonl").export_chats

def run_all():
    init_config()
    key = find_key()
    if not key:
        return
    decrypt_db()
    export_chats()
    print("\n[DONE] All steps complete.")