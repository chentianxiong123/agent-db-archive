#!/usr/bin/env python3
"""QQ聊天记录V2导出 - 精简可读格式"""
import sqlite3, json, os, re, glob
from datetime import datetime, timezone, timedelta
from collections import defaultdict

KC = b'864499037161840'

def dec_str(s):
    if not s: return ''
    try:
        return bytes(x ^ KC[i % len(KC)] for i, x in enumerate(s.encode('latin1'))).decode('latin1').rstrip(chr(0))
    except: return ''

def dec_name(s):
    if not s: return ''
    b = s.encode('utf-8')
    result = bytearray(b)
    cycle = [0x38, 0x36, 0x34]
    for i in range(2, len(result), 3):
        char_pos = (i - 2) // 3
        result[i] ^= cycle[char_pos % 3]
    return result.decode('utf-8', errors='replace')

def safe_fn(name):
    if not name: return ''
    cleaned = ''
    for c in name:
        o = ord(c)
        if o < 32 or 0x7f <= o < 0xa0: continue
        if 0x200b <= o <= 0x200f: continue
        if 0x2028 <= o <= 0x202e: continue
        if 0xfe00 <= o <= 0xfe0f: continue
        if o == 0x200c or o == 0x200d: continue
        if (0x4e00 <= o <= 0x9fff or 0x3000 <= o <= 0x303f or
            0xff00 <= o <= 0xffef or 0x3040 <= o <= 0x309f or
            0x30a0 <= o <= 0x30ff or 0x1100 <= o <= 0x11ff or
            0xac00 <= o <= 0xd7af or 32 <= o <= 0x7e):
            cleaned += c
    for c in '<>:"/\\|?*': cleaned = cleaned.replace(c, '_')
    return cleaned[:100]

tz8 = timezone(timedelta(hours=8))

def parse_msg(msgtype, ds):
    if not ds: return {'type': 'unknown'}
    mt = int(msgtype)
    # KC XOR解密
    if isinstance(ds, bytes):
        ds = bytes(x ^ KC[i % len(KC)] for i, x in enumerate(ds))
    elif isinstance(ds, str):
        ds = bytes(x ^ KC[i % len(KC)] for i, x in enumerate(ds.encode('latin1')))
    if mt == -1000:
        try:
            text = ds.decode('utf-8', errors='replace')
            cleaned = ''.join(c for c in text if ord(c) >= 32 or c in '\n\r')
            return {'type': 'text', 'text': cleaned}
        except: return {'type': 'text', 'text': '[解码失败]'}
    elif mt == -2000:
        uuids = re.findall(b'[A-Fa-f0-9]{32}', ds)
        return {'type': 'image', 'uuid': uuids[0].decode() if uuids else ''}
    elif mt == -1035:
        uuids = re.findall(b'[A-Fa-f0-9]{32}', ds)
        try:
            text_part = ds.decode('utf-8', errors='replace')
            readable = ''
            for line in text_part.split('\n'):
                if all(ord(c) >= 32 for c in line):
                    readable += line + ' '
            return {'type': 'image+text', 'uuid': uuids[0].decode() if uuids else '', 'text': readable.strip()}
        except:
            return {'type': 'image', 'uuid': uuids[0].decode() if uuids else ''}
    elif mt in (-2022, -2055, -5021):
        return {'type': 'file'}
    elif mt == -1051:
        return {'type': 'voice'}
    elif mt == -5040:
        try:
            text = ds.decode('utf-8', errors='replace')
            readable = ''.join(c for c in text if ord(c) >= 32)
            return {'type': 'recall', 'text': readable[:200]}
        except: return {'type': 'recall'}
    elif mt == -2011:
        urls = re.findall(b'https?://[^\x00]+', ds)
        return {'type': 'link', 'urls': [u.decode(errors='replace') for u in urls]}
    elif mt in (-5008, -5017):
        return {'type': 'app'}
    elif mt == -2017:
        return {'type': 'system'}
    elif mt in (-2024, -2026):
        return {'type': 'group_notice'}
    else:
        return {'type': 'other'}

def build_nicks(dbs):
    nicks = {}
    for db_path in dbs:
        base = os.path.basename(db_path)
        if not base.endswith('.db'): continue
        if 'slowtable' in base or 'qqfav' in base: continue
        parts = base[:-3].split('_')
        account = parts[0] if parts[0].isdigit() else None
        if not account: continue
        try:
            conn = sqlite3.connect(db_path)
            conn.text_factory = str
            cur = conn.cursor()
        except: continue
        try:
            cur.execute("SELECT uin, name, remark FROM Friends WHERE uin IS NOT NULL")
            for uin_enc, name_enc, remark_enc in cur.fetchall():
                qq = dec_str(uin_enc)
                if not qq: continue
                entry = nicks.setdefault(qq, {})
                if name_enc:
                    n = dec_name(name_enc)
                    if n: entry['name'] = n
                if remark_enc:
                    r = dec_name(remark_enc)
                    if r: entry['remark'] = r
        except: pass
        try:
            cur.execute("SELECT uin, strNick FROM CardProfilev4 WHERE uin IS NOT NULL")
            for uin_enc, nick_enc in cur.fetchall():
                qq = dec_str(uin_enc)
                if not qq or not nick_enc: continue
                nick = dec_name(nick_enc)
                entry = nicks.setdefault(qq, {})
                if nick: entry.setdefault('name_history', []).append(nick)
        except: pass
        conn.close()
    return nicks

def resolve(qq, nicks):
    e = nicks.get(qq, {})
    if e.get('remark'): return e['remark'], e.get('name', '')
    if e.get('name'): return e['name'], ''
    if e.get('name_history'): return e['name_history'][-1], ''
    return qq, ''

def ts_to_str(ts):
    try:
        return datetime.fromtimestamp(int(ts), tz=tz8).strftime('%Y-%m-%d %H:%M:%S')
    except: return ''

def process(db_path, nicks, export_dir):
    base = os.path.basename(db_path)
    parts = base[:-3].split('_')
    account = parts[0] if parts[0].isdigit() else None
    if not account: return None

    try:
        conn = sqlite3.connect(db_path)
        conn.text_factory = str
        cur = conn.cursor()
    except Exception as e:
        print(f"  无法打开 {db_path}: {e}")
        return None

    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND (name LIKE 'mr_friend_%_New' OR name LIKE 'mr_troop_%_New')")
    tables = [r[0] for r in cur.fetchall()]

    priv_map = defaultdict(list)
    grp_map = defaultdict(list)

    for tbl in tables:
        is_grp = tbl.startswith('mr_troop_')
        cur.execute(f'SELECT frienduin, COUNT(*) FROM "{tbl}"')
        row = cur.fetchone()
        if not row or row[1] == 0: continue
        fu = dec_str(row[0])
        if not fu: continue

        cur.execute(f'SELECT msgData, msgtype, senderuin, time FROM "{tbl}" WHERE msgData IS NOT NULL AND length(msgData) > 0')
        for msg_data, msgtype, senderuin_enc, ts in cur.fetchall():
            if not msg_data: continue
            sqq = dec_str(senderuin_enc)
            parsed = parse_msg(msgtype, msg_data)
            is_self = sqq == account
            dt_str = ts_to_str(ts)
            nickname, _ = resolve(sqq, nicks)
            from_name = "你" if is_self else nickname

            entry = {"t": dt_str, "from": from_name, "qq": sqq, "self": is_self}
            if is_grp: entry["group"] = fu
            entry["type"] = parsed["type"]
            if "text" in parsed: entry["text"] = parsed["text"]
            if "uuid" in parsed: entry["uuid"] = parsed["uuid"]
            if "urls" in parsed: entry["urls"] = parsed["urls"]

            if is_grp:
                grp_map[fu].append(entry)
            else:
                priv_map[fu].append(entry)

    conn.close()

    # 慢表
    slow_path = os.path.join(os.path.dirname(db_path), f'slowtable_{account}.db')
    if os.path.exists(slow_path):
        try:
            conn2 = sqlite3.connect(slow_path)
            conn2.text_factory = str
            cur2 = conn2.cursor()
            cur2.execute("SELECT name FROM sqlite_master WHERE type='table' AND (name LIKE 'mr_friend_%_New' OR name LIKE 'mr_troop_%_New')")
            for (tbl,) in cur2.fetchall():
                is_grp = tbl.startswith('mr_troop_')
                cur2.execute(f'SELECT frienduin, COUNT(*) FROM "{tbl}"')
                row = cur2.fetchone()
                if not row or row[1] == 0: continue
                fu = dec_str(row[0])
                if not fu: continue
                cur2.execute(f'SELECT msgData, msgtype, senderuin, time FROM "{tbl}" WHERE msgData IS NOT NULL AND length(msgData) > 0')
                for msg_data, msgtype, senderuin_enc, ts in cur2.fetchall():
                    if not msg_data: continue
                    sqq = dec_str(senderuin_enc)
                    parsed = parse_msg(msgtype, msg_data)
                    is_self = sqq == account
                    dt_str = ts_to_str(ts)
                    nickname, _ = resolve(sqq, nicks)
                    from_name = "你" if is_self else nickname
                    entry = {"t": dt_str, "from": from_name, "qq": sqq, "self": is_self}
                    if is_grp: entry["group"] = fu
                    entry["type"] = parsed["type"]
                    if "text" in parsed: entry["text"] = parsed["text"]
                    if "uuid" in parsed: entry["uuid"] = parsed["uuid"]
                    if "urls" in parsed: entry["urls"] = parsed["urls"]
                    if is_grp: grp_map[fu].append(entry)
                    else: priv_map[fu].append(entry)
            conn2.close()
        except: pass

    # 写文件
    acc_dir = os.path.join(export_dir, f'account_{account}')
    priv_dir = os.path.join(acc_dir, 'private')
    grp_dir = os.path.join(acc_dir, 'group')
    os.makedirs(priv_dir, exist_ok=True)
    os.makedirs(grp_dir, exist_ok=True)

    total_priv = 0
    for fu, msgs in priv_map.items():
        msgs.sort(key=lambda m: m['t'])
        remark, name = resolve(fu, nicks)
        rc = safe_fn(remark)
        nc = safe_fn(name)
        if rc:
            fname = f"{rc}({nc})-{fu}" if nc and nc != rc else f"{rc}-{fu}"
        elif nc:
            fname = f"{nc}-{fu}"
        else:
            fname = fu
        with open(os.path.join(priv_dir, f"{fname}.jsonl"), 'w', encoding='utf-8') as f:
            for m in msgs:
                f.write(json.dumps(m, ensure_ascii=False) + '\n')
        total_priv += len(msgs)

    total_grp = 0
    for gu, msgs in grp_map.items():
        msgs.sort(key=lambda m: m['t'])
        with open(os.path.join(grp_dir, f"{gu}.jsonl"), 'w', encoding='utf-8') as f:
            for m in msgs:
                f.write(json.dumps(m, ensure_ascii=False) + '\n')
        total_grp += len(msgs)

    return account, total_priv, total_grp

# ===== 主流程 =====
DB_DIR = '/tmp/db_scan/databases'
EXPORT_DIR = '/mnt/shared/QQ_备份_20260802/exports_v2'
os.makedirs(EXPORT_DIR, exist_ok=True)

dbs = sorted(glob.glob(os.path.join(DB_DIR, '*.db')))
print(f"数据库: {len(dbs)}个")

nicks = build_nicks(dbs)
print(f"昵称表: {len(nicks)}人\n")

for db_path in dbs:
    result = process(db_path, nicks, EXPORT_DIR)
    if result:
        account, priv, grp = result
        print(f"  {account}: 私聊{priv}条 群聊{grp}条")

print("\n✅ 导出完成!")
print(f"输出目录: {EXPORT_DIR}")