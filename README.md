# agent-db-archive

AI Agent 数据库归档工具集。从各种 AI 编程助手中提取聊天记录，导出为干净的 JSONL 格式，供后续分析、备份或迁移使用。

## 项目结构

```
agent-db-archive/
├── trae/        # Trae CN（字节跳动 AI IDE）— SQLCipher 加密数据库
├── hermes/      # Hermes — 明文 SQLite 数据库
├── opencode/    # OpenCode CLI — 明文 SQLite 数据库（待开发）
├── README.md
└── .gitignore
```

## 支持的 AI 工具

| 工具 | 数据库类型 | 加密 | 状态 |
|------|-----------|------|------|
| Trae CN | SQLCipher 4 | 需要内存扫描提取密钥 | ✅ 完成 |
| Hermes | 明文 SQLite | 无加密 | ✅ 完成 |
| OpenCode CLI | 明文 SQLite | 无加密 | 🚧 待开发 |

## 导出格式

所有工具统一导出为 JSONL 格式，每行一条消息：

```jsonl
{"role": "user", "content": "帮我创建一个项目"}
{"role": "assistant", "content": "好的，项目已创建..."}
```

按会话组织，文件名格式：`{会话标题}_{时间戳}.jsonl`

## 用途

- **数据备份** — 从本地提取聊天历史，避免数据丢失
- **迁移分析** — 将不同 AI 工具的对话格式统一化，便于跨工具分析
- **训练数据** — 干净的对话数据可用于微调或评估

## 使用方式

每个子目录都是独立的工具，有各自的 README 说明：

```bash
# Trae CN
cd trae && python run.py

# Hermes
cd hermes && python export_hermes.py

# OpenCode（待开发）
cd opencode
```

## 技术栈

- Python 3.8+
- sqlite3 / sqlcipher3
- pymem（内存扫描，仅 Trae）

## 注意事项

- 各工具提取的是本地存储的聊天数据，请遵守相关软件的用户协议
- Trae 工具需要 Windows 环境（进程内存扫描）
- Hermes / OpenCode 工具跨平台

---

*维护者：chentianxiong123*