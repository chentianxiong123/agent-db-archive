# Hermes Chat Export

从 Hermes（AI Agent 工具）的本地数据库导出聊天记录为 JSONL 格式。

## 数据库位置

```
~/.hermes/state.db
```

## 数据库结构

Hermes 使用明文 SQLite，无加密。核心表：

| 表 | 说明 |
|----|------|
| `sessions` | 会话元数据（id, title, source, started_at, message_count） |
| `messages` | 消息内容（session_id, role, content, timestamp, tool_calls, tool_name） |

消息角色：
- `user` — 用户输入
- `assistant` — 模型回复
- `tool` — 工具调用结果（导出时过滤）
- `session_meta` — 会话元信息（导出时过滤）

## 噪声过滤

导出时自动过滤以下噪声消息：

- `[IMPORTANT: Background process...` — 系统后台通知
- `You just executed tool calls...` — 工具回调提示
- `[CONTEXT COMPACTION...` — 上下文压缩摘要
- `WARNING` / `ERROR` — 日志输出
- `Process exited with code...` — 错误堆栈
- `Traceback (most recent call last)...` — Python 异常

## 使用方法

### 1. 准备数据库

```bash
# 如果数据库被锁定，先复制到临时目录
cp ~/.hermes/state.db /tmp/hermes_state.db
```

### 2. 运行导出

```bash
python export_hermes.py
```

### 3. 输出位置

```
./hermes_chat_jsonl/
├── 会话标题_20260525_105020.jsonl
├── 会话标题_20260617_173918.jsonl
└── ...
```

每行格式：
```jsonl
{"role": "user", "content": "帮我安装一个opencode-cli下来"}
{"role": "assistant", "content": "好的，opencode 安装命令是..."}
```

## 统计信息

- 导出会话数：111
- 过滤噪声消息：5258 条
- 输出文件数：105
- 总大小：3.3M

## 依赖

- Python 3.8+（标准库即可，无需额外安装）

## 注意事项

- 数据库可能被 Hermes 进程锁定，需要复制到临时位置再读取
- 导出只包含 user 和 assistant 消息，工具调用和系统消息已过滤
- 上下文压缩摘要（CONTEXT COMPACTION）也被过滤，如需保留请修改 `NOISE_PATTERNS`