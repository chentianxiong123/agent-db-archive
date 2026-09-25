"""3. Export clean chat JSONL organized by workspace/session"""
import os, re, json, sqlcipher3
from datetime import datetime

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.json")

def load_config():
    with open(CONFIG_PATH) as f:
        return json.load(f)

def safe(s, maxlen=80):
    s = re.sub(r'[<>:"/\\|?*\x00-\x1F]', '_', str(s))
    s = re.sub(r'\s+', '_', s).strip('_')[:maxlen].rstrip('. ')
    return s or 'untitled'

def fmt_ts(ts):
    if isinstance(ts, (int, float)):
        if ts > 1e12: ts /= 1000
        try: return datetime.fromtimestamp(ts).strftime('%Y%m%d_%H%M%S')
        except: pass
    if isinstance(ts, str) and ts:
        return ts[:19].replace('-','').replace('T','_').replace(':','')
    return 'unknown'

def get_text_from_content(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        texts = []
        for item in content:
            if isinstance(item, dict):
                t = item.get('text') or item.get('text_content') or ''
                if t: texts.append(t)
            elif isinstance(item, str):
                texts.append(item)
        return '\n'.join(texts)
    return ''

def extract_user_msg(content):
    txt = get_text_from_content(content)
    if not txt:
        return ''
    m = re.search(r'<user_input>(.*?)</user_input>', txt, re.DOTALL)
    if m:
        return m.group(1).strip()
    txt = re.sub(r'<system-reminder>.*?</system-reminder>', '', txt, flags=re.DOTALL)
    txt = re.sub(r'<rules>.*?</rules>', '', txt, flags=re.DOTALL)
    txt = re.sub(r'<available_terminal>.*?</available_terminal>', '', txt, flags=re.DOTALL)
    txt = re.sub(r'# important-instruction-reminders.*?(?=\n\S|\Z)', '', txt, flags=re.DOTALL)
    txt = re.sub(r'Respond in zh-CN\.?\s*$', '', txt).strip()
    txt = re.sub(r'\n{3,}', '\n\n', txt).strip()
    return txt

def extract_assistant_msg(content):
    c = get_text_from_content(content)
    if not c or c == '{}':
        return ''
    try:
        data = json.loads(c)
    except:
        return c[:1000]
    msgs = data.get('messages', []) if isinstance(data, dict) else []
    if not msgs:
        return ''
    thoughts = []
    for m in msgs:
        pi = m.get('plan_item', m) if isinstance(m, dict) else {}
        t = pi.get('thought', '')
        if t: thoughts.append(t)
        ti = pi.get('tool_call_info', {})
        if ti.get('name') == 'finish':
            summary = ti.get('result', {}).get('data', {}).get('summary', '')
            if summary: return summary
    return thoughts[-1] if thoughts else ''

def export_chats(output_dir=None):
    cfg = load_config()
    db_path = os.path.expandvars(cfg["db_path"])
    key = cfg.get("key")
    if not key:
        print("[-] No key found. Run 1_find_key first.")
        return

    if output_dir is None:
        output_dir = os.path.join(os.path.dirname(CONFIG_PATH), "trae_chat_jsonl")
    os.makedirs(output_dir, exist_ok=True)

    conn = sqlcipher3.connect(db_path)
    conn.execute(f"PRAGMA key = \"x'{key}'\";")
    conn.execute("PRAGMA cipher_hmac_algorithm = HMAC_SHA512;")
    conn.execute("PRAGMA cipher_kdf_algorithm = PBKDF2_HMAC_SHA512;")
    conn.execute("PRAGMA cipher_page_size = 4096;")
    conn.execute("PRAGMA cipher_kdf_iter = 256000;")

    def q(sql):
        c = conn.execute(sql)
        return [dict(zip([d[0] for d in c.description], row)) for row in c.fetchall()]

    sessions = {s['session_id']: s for s in q("SELECT * FROM chat_session")}
    projects = {p['project_id']: p for p in q("SELECT * FROM project")}
    sp = q("SELECT * FROM session_project")
    sp_map = {}
    for r in sp:
        sp_map.setdefault(r['session_id'], []).append(r['project_id'])

    histories = q("SELECT * FROM history_v2 WHERE deleted_at=0 ORDER BY session_id, created_at")

    ws_sessions = {}
    for h in histories:
        sid = h['session_id']
        se = sessions.get(sid)
        if not se: continue
        pids = sp_map.get(sid, [])
        pid = pids[0] if pids else None
        proj = projects.get(pid, {}) if pid else {}
        ws = proj.get('name') or os.path.basename((proj.get('absolute_path') or '').rstrip('\\/')) or pid or '_unknown'
        try:
            rm = json.loads(h['messages']).get('raw_messages', [])
        except:
            rm = []
        if not rm: continue
        ws_sessions.setdefault(ws, {}).setdefault(sid, {
            'title': se.get('session_title','') or 'untitled',
            'updated': se.get('updated_at',''),
            'msgs': []
        })['msgs'].extend(rm)

    import shutil
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)

    total = 0
    for ws, sess in sorted(ws_sessions.items()):
        wd = os.path.join(output_dir, safe(ws))
        os.makedirs(wd, exist_ok=True)
        for sid, s in sess.items():
            ts = fmt_ts(s['updated'])
            fn = f"{safe(s['title'])}_{ts}.jsonl"
            fp = os.path.join(wd, fn)
            with open(fp, 'w', encoding='utf-8') as f:
                for m in s['msgs']:
                    role = m.get('role', '')
                    if role == 'tool':
                        continue
                    txt = extract_user_msg(m.get('content','')) if role == 'user' else extract_assistant_msg(m.get('content',''))
                    if not txt: continue
                    f.write(json.dumps({"role": role, "content": txt}, ensure_ascii=False) + '\n')
            total += 1
        print(f"  {ws}/ ({len(sess)} sessions)")

    conn.close()
    print(f"\n[+] {total} sessions exported to {output_dir}")
    return output_dir

if __name__ == "__main__":
    export_chats()