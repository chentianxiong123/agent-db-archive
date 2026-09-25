# QQ Android Database Toolkit

从 QQ Android 加密数据库中提取聊天记录的工具集。

## 目录结构

```
qq/
├── export_chats.py      # 主导出脚本，完整解密并导出 JSONL
├── README.md            # 本文档
└── requirements.txt     # 依赖（无额外依赖，仅需 Python 标准库）
```

## 原理

QQ Android 的聊天数据存储在 `/data/data/com.tencent.mobileqq/databases/`，所有数据库为 SQLite 格式。

### 加密方案

QQ Android 使用两套 XOR 加密方案，分别处理不同类型的数据：

#### 密钥一：数字/消息类字段

**密钥**：`864499037161840`（17 字节，循环使用）

**适用字段**：
- QQ 号码（uin, senderuin, frienduin, selfuin）
- 消息正文（msgData）
- 时间戳（time）

**加密公式**：
```
密文[i] = 明文[i] XOR Key[i % 17]
```

**特点**：加密后为纯 ASCII 可打印字符，易识别。

#### 密钥二：昵称/备注类字段

**密钥**：`[0x38, 0x36, 0x34]`（3 字节，按字符位置循环）

**适用字段**：
- 昵称（Friends.name, CardProfilev4.strNick）
- 备注（Friends.remark）
- 群名（Groups.group_name）

**加密公式**：
```
字符 C 的 UTF-8 编码：B1 B2 B3
加密后：B1 B2 (B3 XOR K[i % 3])
其中 K = [0x38, 0x36, 0x34]，i 为字符在字符串中的位置
```

**特点**：加密后仍是合法 UTF-8 中文，但字符偏移。ASCII 字符不受影响（只有 1 字节）。

### 密钥发现过程

1. **密钥一**：从 HTML 导出文件找到已知明文消息，对比加密密文推导 XOR 密钥
2. **密钥二**：发现昵称加密后仍是合法 UTF-8，对比密文与明文字节差异，发现只有第 3 字节被修改

### 安全性评估

这是一个非常弱的加密方案：
- 密钥固定，无随机化
- 无完整性校验
- 本质上是单表替换密码的变体
- 设计目标可能是防君子不防小人

## 数据库结构

每个 QQ 账号对应一个数据库文件 `{QQ号}.db`，另有 `slowtable_{QQ号}.db` 存储延迟消息。

### 核心表

| 表 | 说明 |
|----|------|
| `Friends` | 好友列表（uin, name, remark） |
| `Groups` | 群组列表（group_id, group_name） |
| `CardProfilev4` | 名片信息（含历史昵称） |
| `mr_friend_*_New` | 私聊消息表（每好友一个表） |
| `mr_troop_*_New` | 群聊消息表（每群一个表） |

### 消息表结构

```sql
CREATE TABLE mr_friend_xxx_New (
    msgData BLOB,      -- 消息内容（密钥一加密）
    msgtype INTEGER,   -- 消息类型
    senderuin TEXT,    -- 发送者 QQ（密钥一加密）
    frienduin TEXT,    -- 对方/群号（密钥一加密）
    time INTEGER,      -- 时间戳（毫秒）
    ...
);
```

### 消息类型

| msgtype | 类型 | 说明 |
|---------|------|------|
| -1000 | 文字 | XOR 解密后 UTF-8 解码 |
| -2000 | 图片 | 提取 UUID |
| -1035 | 图片+文字 | 含图片和文字描述 |
| -2022/-2055/-5021 | 文件 | QQ 文件传输 |
| -1051 | 语音 | 语音消息 |
| -5040 | 撤回 | 撤回消息（含原文） |
| -2011 | 链接 | 提取 URL |
| -5008/-5017 | APP | 小程序、应用卡片 |
| -2017 | 系统消息 | 入群、退群等 |
| -2024/-2026 | 群公告 | 群公告更新 |

## 导出格式

按账号分会话导出 JSONL：

```
exports/
└── account_{QQ号}/
    ├── private/
    │   ├── 备注(昵称)-{对方QQ}.jsonl
    │   └── ...
    └── group/
        ├── {群号}.jsonl
        └── ...
```

每行格式：
```jsonl
{"t": "2022-10-04 11:48:00", "from": "你", "qq": "1026044893", "self": true, "type": "text", "text": "帮我创建一个项目"}
{"t": "2022-10-04 11:48:05", "from": "刘剑戈", "qq": "1026044894", "self": false, "type": "text", "text": "好的"}
```

## 使用方法

### 前置条件

1. **Root 手机**：需要 root 权限访问 `/data/data/com.tencent.mobileqq/`
2. **提取数据库**：复制数据库文件到本地

```bash
# 通过 adb 提取（需要 root）
adb root
adb pull /data/data/com.tencent.mobileqq/databases/ ./databases/
```

3. **配置路径**：修改脚本中的 `DB_DIR` 和 `EXPORT_DIR`

### 运行

```bash
python3 export_chats.py
```

### 输出

脚本会输出处理进度和统计信息：
```
数据库: 6个
昵称表: 3500人

  1026044893: 私聊1234条 群聊5678条
  2036680567: 私聊2345条 群聊9876条
  ...

✅ 导出完成!
输出目录: ./exports/
```

## 注意事项

- 本工具仅用于个人数据备份，请遵守 QQ 用户协议
- 群聊成员昵称存储在独立表中，需交叉关联
- 约 27% 的昵称含 emoji/特殊符号，这是用户真实昵称
- 同一用户在不同表的昵称可能不一致（更新时机不同）
- 图片消息只提取 UUID，实际图片文件在媒体目录

## 参考项目

- **[wechat-decrypt](https://github.com/LC044/WeChatMsg)** — 微信数据库解密方法论
- **[qq-win-db-key](https://github.com/QQ-DB-Key)** — QQ NT 数据库密钥提取

---

*基于魅族 M5 Note (Android 7) 实机分析*