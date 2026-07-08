# Trae CN Database Toolkit

从 Trae CN（字节跳动 AI IDE）加密数据库中提取聊天记录的工具集。

## 目录结构

```
trae-db-toolkit/
├── 1_find_key/          # 从进程内存中提取 SQLCipher 加密密钥
├── 2_decrypt_db/        # 用密钥解密数据库，导出全部表为 JSON
├── 3_export_chats/      # 按工作区分会话导出清洁聊天 JSONL
├── scripts/             # 配置与一键脚本
├── config.json          # 路径与密钥缓存
├── run.py               # 一键运行
└── requirements.txt
```

## 原理

Trae CN 的 AI 聊天数据存储在 `%APPDATA%\Trae CN\ModularData\ai-agent\database.db`，使用 SQLCipher 4 加密。

### 密钥存储

密钥不是硬编码在二进制中的，而是：
1. 运行在 Trae CN.exe 的 `basil.mojom.NativeService` 子进程中（加载 `ai_agent.dll`）
2. 密钥在内存中以 `x'<64hex_key><32hex_salt>'` 格式缓存
3. 每个数据库连接缓存一个 salted key 字符串

### 密钥验证

SQLCipher 4 每个页面末尾存储了 HMAC-SHA512 校验值。验证方法：

```
salt = page1[0:16]
mac_salt = salt XOR 0x3A (逐字节)
mac_key = PBKDF2-HMAC-SHA512(enc_key, mac_salt, 2 iterations, 32 bytes)
hmac_data = page1[16:4096-64]
stored_hmac = page1[4096-64:4096]
computed = HMAC-SHA512(mac_key, hmac_data + page_number)
assert computed == stored_hmac
```

### 解密参数

```
PRAGMA key = "x'<key>'";
PRAGMA cipher_hmac_algorithm = HMAC_SHA512;
PRAGMA cipher_kdf_algorithm = PBKDF2_HMAC_SHA512;
PRAGMA cipher_page_size = 4096;
PRAGMA cipher_kdf_iter = 256000;
```

### 数据库结构

40 个表，核心聊天相关：

| 表 | 行数 | 说明 |
|----|------|------|
| `chat_session` | ~250 | 会话列表（标题、类型、时间） |
| `chat_message` | ~12k | 消息索引（角色、类型、所属会话） |
| `chat_message_general` | ~6k | 通用消息内容 |
| `chat_message_task` | ~6k | 任务型消息内容（含 tool call） |
| `chat_turn` | ~6k | 对话轮次（agent 类型、状态） |
| `history_v2` | ~62k | 历史记录，含 `raw_messages` 清洁对话 |
| `server_history_info` | ~119k | 服务端历史 |
| `project` | ~40 | 项目信息（含 `absolute_path`） |
| `session_project` | ~270 | 会话-项目关联 |

### 导出格式

每个会话导出为一个 `.jsonl` 文件，按 `工作区/会话标题_时间戳.jsonl` 组织：

```
trae_chat_jsonl/
├── mybilibili/
│   ├── Bilibili创作中心实现方案_20260317_140726.jsonl
│   ├── 修复视频展示用户名问题_20260404_180348.jsonl
│   └── ...
├── HomeSense/
│   ├── AI_Agent_智能家庭控制系统_20260329_094606.jsonl
│   └── ...
└── cc-work/
    └── ...
```

每行格式：
```jsonl
{"role": "user", "content": "帮我创建一个 HomeSense 前端项目..."}
{"role": "assistant", "content": "项目已创建成功，我检查了项目结构..."}
```

系统提示、工具调用、计划项等内部噪声已被清洗。

## 使用方法

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

或使用 venv：

```bash
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

### 2. 运行

**一键运行**（需要先打开 Trae CN，让 `ai_agent.dll` 加载到内存）：

```bash
.venv\Scripts\python run.py
```

**分步运行**：

```bash
# 第1步：从进程内存提取密钥
.venv\Scripts\python 1_find_key/find_key.py

# 第2步：解密数据库，导出所有表为 JSON
.venv\Scripts\python 2_decrypt_db/decrypt.py

# 第3步：导出清洁聊天 JSONL
.venv\Scripts\python 3_export_chats/export_jsonl.py
```

### 3. 手动密钥

如果自动提取失败，可以从运行中的 Trae CN 进程手动获取密钥：

```powershell
# 使用 Process Explorer 或其他内存转储工具
# 搜索 x'<64hex_enc_key><32hex_salt>' 模式
# 其中 salt 匹配数据库文件前 16 字节
```

找到后将密钥写入 `config.json`：

```json
{
  "key": "3605f6691095a993f03d5009c918352e..."
}
```

## 依赖

- `sqlcipher3` — Python SQLCipher 绑定，用于解密数据库
- `pymem` — 读写进程内存
- `psutil` — 进程枚举
- `pycryptodome` — 加密算法（备用）

## 参考项目

本工具的方法论参考了以下开源项目：

- **[wechat-decrypt](https://github.com/LC044/WeChatMsg)** — 微信数据库解密，HMAC 验证方法
- **[qq-win-db-key](https://github.com/QQ-DB-Key)** — QQ NT 数据库密钥提取，Frida hook 方法
- **[search_wechat_key](https://github.com/search_wechat_key)** — 微信内存密钥搜索，指针追踪方法
- **[trae-chat-export-to-markdown](https://github.com/ameca42/trae-chat-export-to-markdown)** — Trae 聊天导出（未加密版本）

## 注意事项

- 需要先在 Trae CN 中打开 AI 聊天功能，使 `ai_agent.dll` 加载到进程内存
- 密钥提取需要 `PROCESS_ALL_ACCESS` 权限
- 数据库文件约 1.3GB，解密过程需要足够内存
- 本工具仅用于个人数据备份，请遵守相关软件的用户协议