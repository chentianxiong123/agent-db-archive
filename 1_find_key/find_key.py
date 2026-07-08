"""1. Find SQLCipher key from Trae CN process memory
Uses HMAC-SHA512 verification to validate found keys
"""
import os, re, hashlib, hmac as hmac_mod, struct, ctypes, json
from ctypes import wintypes

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.json")

def load_config():
    with open(CONFIG_PATH) as f:
        return json.load(f)

class MBI(ctypes.Structure):
    _fields_ = [
        ("BaseAddress", ctypes.c_uint64), ("AllocationBase", ctypes.c_uint64),
        ("AllocationProtect", wintypes.DWORD), ("_pad1", wintypes.DWORD),
        ("RegionSize", ctypes.c_uint64), ("State", wintypes.DWORD),
        ("Protect", wintypes.DWORD), ("Type", wintypes.DWORD), ("_pad2", wintypes.DWORD),
    ]

MEM_COMMIT = 0x1000
READABLE = {0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80}
PAGE_SZ = 4096
KEY_SZ = 32
SALT_SZ = 16

def verify_key(enc_key, page1):
    salt = page1[:SALT_SZ]
    mac_salt = bytes(b ^ 0x3A for b in salt)
    mac_key = hashlib.pbkdf2_hmac("sha512", enc_key, mac_salt, 2, dklen=KEY_SZ)
    hmac_data = page1[SALT_SZ: PAGE_SZ - 80 + 16]
    stored_hmac = page1[PAGE_SZ - 64: PAGE_SZ]
    hm = hmac_mod.new(mac_key, hmac_data, hashlib.sha512)
    hm.update(struct.pack("<I", 1))
    return hm.digest() == stored_hmac

def find_key(proc_name="Trae CN", dll_hint="ai_agent.dll"):
    cfg = load_config()
    db_path = os.path.expandvars(cfg["db_path"])
    with open(db_path, "rb") as f:
        page1 = f.read(PAGE_SZ)
    salt_hex = page1[:SALT_SZ].hex()
    print(f"[*] DB salt: {salt_hex}")

    import psutil, pymem
    target_pid = None
    for proc in psutil.process_iter(["pid", "name"]):
        if proc.info["name"] == proc_name:
            try:
                pm = pymem.Pymem(proc.info["pid"])
                mods = list(pm.list_modules())
                if any(m.name and dll_hint in m.name.lower() for m in mods):
                    target_pid = proc.info["pid"]
                    pm.close_process()
                    break
                pm.close_process()
            except:
                continue

    if not target_pid:
        print(f"[-] Process '{proc_name}' not found or '{dll_hint}' not loaded")
        return None

    print(f"[+] Found PID={target_pid}")

    kernel32 = ctypes.windll.kernel32
    h = kernel32.OpenProcess(0x1F0FFF, False, target_pid)
    if not h:
        print("[-] Cannot open process")
        return None

    hex_re = re.compile(rb"x'((?!')[0-9a-fA-F]{64,192})'")
    found = []
    addr = 0
    while addr < 0x7FFFFFFFFFFF:
        mbi = MBI()
        if kernel32.VirtualQueryEx(h, ctypes.c_uint64(addr), ctypes.byref(mbi), ctypes.sizeof(mbi)) == 0:
            break
        if mbi.State == MEM_COMMIT and mbi.Protect in READABLE and 0 < mbi.RegionSize < 500*1024*1024:
            buf = ctypes.create_string_buffer(mbi.RegionSize)
            br = ctypes.c_size_t(0)
            if kernel32.ReadProcessMemory(h, ctypes.c_uint64(mbi.BaseAddress), buf, mbi.RegionSize, ctypes.byref(br)):
                data = buf.raw[:br.value]
                for m in hex_re.finditer(data):
                    hs = m.group(1).decode()
                    hl = len(hs)
                    if hl == 96:
                        ek = bytes.fromhex(hs[:64])
                        if hs[64:] == salt_hex and verify_key(ek, page1):
                            found.append(hs[:64])
                    elif hl == 64:
                        ek = bytes.fromhex(hs)
                        if verify_key(ek, page1):
                            found.append(hs)
                    elif hl > 96:
                        ek = bytes.fromhex(hs[:64])
                        if hs[-32:] == salt_hex and verify_key(ek, page1):
                            found.append(hs[:64])
        nxt = mbi.BaseAddress + mbi.RegionSize
        if nxt <= addr:
            break
        addr = nxt

    kernel32.CloseHandle(h)
    if found:
        cfg["key"] = found[0]
        with open(CONFIG_PATH, "w") as f:
            json.dump(cfg, f, indent=2)
        print(f"[+] Key: {found[0]}")
        return found[0]
    print("[-] Key not found")
    return None

if __name__ == "__main__":
    find_key()