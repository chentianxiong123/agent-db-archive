"""2. Decrypt Trae CN database and dump all tables as JSON"""
import os, json, sqlcipher3

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.json")

def load_config():
    with open(CONFIG_PATH) as f:
        return json.load(f)

def decrypt_db(output_dir=None):
    cfg = load_config()
    db_path = os.path.expandvars(cfg["db_path"])
    key = cfg.get("key")
    if not key:
        print("[-] No key found. Run 1_find_key first.")
        return

    if output_dir is None:
        output_dir = os.path.join(os.path.dirname(CONFIG_PATH), "tables_json")
    os.makedirs(output_dir, exist_ok=True)

    conn = sqlcipher3.connect(db_path)
    conn.execute(f"PRAGMA key = \"x'{key}'\";")
    conn.execute("PRAGMA cipher_hmac_algorithm = HMAC_SHA512;")
    conn.execute("PRAGMA cipher_kdf_algorithm = PBKDF2_HMAC_SHA512;")
    conn.execute("PRAGMA cipher_page_size = 4096;")
    conn.execute("PRAGMA cipher_kdf_iter = 256000;")

    tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]

    for table in tables:
        cols = [r[1] for r in conn.execute(f"PRAGMA table_info(\"{table}\")").fetchall()]
        rows = conn.execute(f"SELECT * FROM \"{table}\"").fetchall()
        if not rows:
            continue
        data = []
        for row in rows:
            d = dict(zip(cols, row))
            for k, v in d.items():
                if isinstance(v, bytes):
                    d[k] = v.hex()
            data.append(d)
        fp = os.path.join(output_dir, f"{table}.json")
        with open(fp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        print(f"  {table}: {len(rows)} rows -> {fp}")

    conn.close()
    print(f"\n[+] {len(tables)} tables exported to {output_dir}")
    return output_dir

if __name__ == "__main__":
    decrypt_db()