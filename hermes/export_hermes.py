#!/usr/bin/env python3
"""Export Hermes state.db to JSONL with noise filtering.
Filters out tool callbacks, system notifications, logs, and context compaction.
"""
import os, re, json, sqlite3, shutil

DB = "/tmp/hermes_state.db"
OUT = "/tmp/hermes_chat_jsonl"

# Patterns that indicate noise (not real user/assistant content)
NOISE_PATTERNS = [
    r'^\[IMPORTANT:',           # Background process notifications
    r'^You just executed tool',  # Tool callback prompts
    r'^\[CONTEXT COMPACTION',    # Context compaction summaries
    r'^\[Note: model was just switched',  # Model switching notifications
    r'^(WARNING|ERROR)\s',      # Log output
    r'^Process exited with code', # Process error output
    r'^\s*Traceback \(most recent', # Python tracebacks
    r'^\s*File \"<frozen runpy>',   # Runpy errors
    r'^\s*\[gateway\]',        # Gateway logs
]

def is_noise(text):
    """Check if message is noise (system/log/tool output, not real conversation)."""
    if not text:
        return True
    text = text.strip()
    # Short messages that are just error codes or empty
    if len(text) < 10:
        return True
    for pattern in NOISE_PATTERNS:
        if re.match(pattern, text, re.IGNORECASE):
            return True
    return False

def clean_text(text):
    """Remove noise patterns from content while keeping real conversation."""
    if not text:
        return ''
    # Remove context compaction blocks
    text = re.sub(r'\[CONTEXT COMPACTION[^\]]*\]\s*.*?(?=\n\n|$)', '', text, flags=re.DOTALL)
    # Remove model switching notifications (can appear at start or middle)
    text = re.sub(r'\[Note: model was just switched[^"]*?\]\s*', '', text)
    # Remove system reminders
    text = re.sub(r'<system-reminder>.*?</system-reminder>', '', text, flags=re.DOTALL)
    text = re.sub(r'<rules>.*?</rules>', '', text, flags=re.DOTALL)
    # Clean up multiple newlines
    text = re.sub(r'\n{3,}', '\n\n', text).strip()
    return text

def safe(s, maxlen=80):
    s = re.sub(r'[<>:"/\\|?*\x00-\x1F]', '_', str(s or ''))
    s = re.sub(r'\s+', '_', s).strip('_')[:maxlen].rstrip('. ')
    return s or 'untitled'

from datetime import datetime

def fmt_ts(ts):
    if isinstance(ts, (int, float)):
        try: return datetime.fromtimestamp(ts).strftime('%Y%m%d_%H%M%S')
        except: pass
    return 'unknown'

conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
sessions = conn.execute("SELECT id, title, started_at, message_count FROM sessions ORDER BY started_at DESC").fetchall()

if os.path.exists(OUT):
    shutil.rmtree(OUT)
os.makedirs(OUT)

total = 0
skipped = 0
for sid, title, started, mc in sessions:
    msgs = conn.execute(
        "SELECT role, content FROM messages WHERE session_id=? AND role IN ('user','assistant') ORDER BY timestamp",
        (sid,)
    ).fetchall()
    
    cleaned = []
    for role, content in msgs:
        if is_noise(content):
            skipped += 1
            continue
        text = clean_text(content)
        if not text:
            skipped += 1
            continue
        cleaned.append({"role": role, "content": text})
    
    if not cleaned:
        continue
    
    ts = fmt_ts(started)
    fn = f"{safe(title)}_{ts}.jsonl"
    fp = os.path.join(OUT, fn)
    with open(fp, 'w', encoding='utf-8') as f:
        for msg in cleaned:
            f.write(json.dumps(msg, ensure_ascii=False) + '\n')
    total += 1

conn.close()
print(f"[+] {total} sessions exported to {OUT}")
print(f"    {skipped} noise messages filtered")
print(f"    {len(os.listdir(OUT))} files")