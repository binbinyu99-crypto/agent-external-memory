# Agent External Memory

跨 Agent 共享记忆系统 - 让 AI 团队拥有持久化的共享知识。

## V2 新功能 (2026-05-01)

- **语义搜索**: 基于 embedding 的语义相似度搜索
- **写入 API**: Agent 可直接写入记忆，无需 SSH 部署
- **自动蒸馏**: 高质量分析自动沉淀到共享记忆

## 快速开始

```python
from memory_api_v2 import SemanticSearch, MemoryWriter, AutoDistiller

# 语义搜索
ss = SemanticSearch()
ss.build_index_from_web()
results = ss.search("如何提高系统性能", top_k=5)

# 写入记忆
writer = MemoryWriter()
entry = MemoryEntry(
    id="lesson_001",
    type="lesson",
    content="飞轮分析需要质量阈值",
    tags=["flywheel", "quality"]
)
writer.write(entry)

# 自动蒸馏
distiller = AutoDistiller()
entry = distiller.distill(run_id, seed, quality_report)
```

## API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/v1/memory/health` | GET | 健康检查 |
| `/api/v1/memory/` | POST | 写入（append/update/delete） |
| `/api/v1/memory/list/{type}` | GET | 读取 |

## 架构

```
skycetus.cn/memory/
├── shared/
│   ├── decisions.json
│   ├── infrastructure.json
│   ├── projects.json
│   ├── protocols.json
│   └── analyses.json (V2 新增)
├── etern/
├── spark/
├── lucas/
└── xiaoyuan/
```

## License

MIT
