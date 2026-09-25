# OpenCode Chat Export

从 OpenCode CLI 的本地数据库导出聊天记录为 JSONL 格式。

## 状态

🚧 待开发

## 数据库位置

```
~/.opencode/opencode-db/opencode.db
```

## 数据库结构

OpenCode 使用明文 SQLite。核心表：

| 表 | 说明 |
|----|------|
| `sessions` | 会话信息 |
| `messages` | 消息内容 |
| `parts` | 消息片段 |

## 已知问题

- 数据库可能很大（5.9GB+），需要只读模式打开
- `PRAGMA integrity_check` 在大库上会超时
- `auto_vacuum = OFF`，需要手动 VACUUM 压缩

## 待办

- [ ] 分析数据库结构
- [ ] 编写导出脚本
- [ ] 测试大数据量场景

## 参考

- [opencode issue #16777](https://github.com/sst/opencode/issues/16777) — database bloat
- [opencode issue #31391](https://github.com/sst/opencode/issues/31391) — 10GB+ db
- [ocgc](https://github.com/) — OpenCode Garbage Collector（第三方清理工具）