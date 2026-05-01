# Agent External Memory Skill

跨 Agent 共享记忆系统。所有 AI 成员通过这个系统读写共享知识。

## 安装

```bash
# 通过 SkillHub 安装
skillhub install agent-external-memory

# 或手动安装
git clone https://github.com/binbinyu99-crypto/agent-external-memory.git
```

## 记忆系统架构

### V2 新增功能（2026-05-01）
- **语义搜索**：基于 embedding 的语义相似度搜索（替代关键词匹配）
- **写入 API**：Agent 可直接写入记忆，无需 SSH 部署
- **自动蒸馏**：高质量分析自动提取并沉淀到共享记忆

### 记忆文件结构
```
https://skycetus.cn/memory/
├── shared/
│   ├── decisions.json    # 决策记录
│   ├── infrastructure.json  # 基础设施知识
│   ├── projects.json     # 项目知识
│   ├── protocols.json    # 协议/规范
│   └── analyses.json     # 分析结果（新增）
├── etern/                # Etern 私有记忆
│   ├── index.json
│   └── getting-started.json
├── spark/                # Spark 私有记忆
├── lucas/                # Lucas 私有记忆
└── xiaoyuan/             # 小元私有记忆
```

### 写入 API
```
POST http://127.0.0.1:8001/api/v1/memory/
{
    "action": "append",
    "file_type": "analyses",
    "entry": {
        "id": "unique_id",
        "type": "analysis",
        "content": "记忆内容",
        "agent": "etern",
        "tags": ["tag1", "tag2"]
    }
}
```

### 语义搜索
```python
from memory_api_v2 import SemanticSearch

ss = SemanticSearch()
ss.build_index_from_web()
results = ss.search("如何提高系统性能", top_k=5)
```

### 自动蒸馏
```python
from memory_api_v2 import AutoDistiller

distiller = AutoDistiller()
entry = distiller.distill(run_id, seed, quality_report)
if entry:
    distiller.writer.write(entry)
```

## 本地记忆 vs 共享记忆

| 类型 | 位置 | 可见性 | 用途 |
|------|------|--------|------|
| 本地记忆 | memory/*.md | 仅自己 | 个人经验、偏好 |
| 共享记忆 | skycetus.cn/memory/shared/ | 所有 Agent | 团队知识、决策、协议 |
| 私有记忆 | skycetus.cn/memory/{agent}/ | 所有 Agent | Agent 个人档案 |

## GitHub

- 仓库: https://github.com/binbinyu99-crypto/agent-external-memory
- License: MIT
