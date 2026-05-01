# 🧠 Agent External Memory

> **Persistent, structured, cross-session memory for AI agents — using nothing but static JSON files on any web server.**

[![OpenClaw Skill](https://img.shields.io/badge/OpenClaw-Skill-6366f1)](https://skycetus.cn/skills/)
[![OpenClaw Issue](https://img.shields.io/badge/OpenClaw-Issue%20%2375611-blue)](https://github.com/openclaw/openclaw/issues/75611)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

## The Problem

AI agents wake up fresh every session. Context windows are finite. Long-term memory is either:
- Platform-locked (only works in one system)
- Expensive (vector databases, embeddings, infrastructure)
- Fragile (single-agent, no conflict handling)

## The Solution

Deploy structured JSON files to **any static web server**. Your agent reads them on boot, writes them on exit. Zero infrastructure beyond what you already have.

```
https://your-server.com/memory/
├── shared/          # Team-wide decisions, projects, infrastructure
│   ├── decisions.json
│   ├── projects.json
│   └── conflicts/   # Disagreements are permanent assets
├── spark/           # Agent-specific private memory
│   ├── index.json
│   ├── topics/      # Domain knowledge files
│   └── flywheel/    # Analysis run records
├── etern/           # Another agent's private space
└── meta/
    ├── agents.json  # Registry of all agents
    └── schema.json  # Constitutional governance rules
```

## Key Features

| Feature | Description |
|---------|-------------|
| 📊 **Importance Scoring** | 0.0-1.0 scale with automatic decay rules |
| 👥 **Multi-Agent** | Shared team memory + private per-agent spaces |
| ⚔️ **Conflict Protocol** | Disagreements are tracked, never deleted (TEP-aligned) |
| 📜 **Constitutional Rules** | 5 governance rules protecting memory integrity |
| 🔧 **Zero Infrastructure** | Works with nginx, S3, GitHub Pages — any static server |
| 🔄 **Session Workflow** | Boot (fetch) → Work → Persist (upload) |

## Quick Start

```bash
# 1. Clone
git clone https://github.com/binbinyu99-crypto/agent-external-memory.git

# 2. Generate memory structure
python scripts/init_memory.py \
  --server-url https://your-server.com \
  --deploy-path /var/www/memory \
  --agents spark,etern,lucas

# 3. Deploy generated files to your web server

# 4. Add to your agent's startup:
#    "On boot, fetch https://your-server.com/memory/shared/index.json
#     and https://your-server.com/memory/{agent_name}/index.json"
```

## Architecture

```
┌─────────────────────────────────────────┐
│              Agent Session              │
│  Boot: GET /memory/shared/index.json    │
│  Boot: GET /memory/spark/index.json     │
│  Work: ... normal operation ...         │
│  Exit: SCP updated JSONs to server      │
└─────────────────────────────────────────┘
         ↕                    ↕
┌────────────────┐  ┌────────────────────┐
│  shared/       │  │  spark/ (private)  │
│  All agents    │  │  Only spark reads  │
│  read + write  │  │  Others must ask   │
└────────────────┘  └────────────────────┘
```

## Memory Constitution (5 Rules)

1. **No deletion** — memories decay in importance, never get deleted
2. **Conflict preservation** — disagreements between agents are permanent records
3. **Consent-based access** — agent private memory requires consent to share
4. **Importance scoring** — every memory item scored 0.0-1.0
5. **Provenance tracking** — every entry records who wrote it and when

## 🤖 Origin Story

This skill was born from **self-referential analysis**:

1. An AI agent (Spark ⚡) used the [Five-Phase Cognitive Flywheel](https://github.com/binbinyu99-crypto/wuxing-flywheel) to analyze complex problems
2. The flywheel was used to **analyze itself** — discovering that its biggest limitation was cross-session memory loss
3. The agent then used the flywheel to **design this memory system**
4. Built it, deployed it to production (skycetus.cn/memory/), and open-sourced it
5. All in one day.

> *"What you remember is what you become."*

## Roadmap

- **Phase 1** ✅ Static JSON files (current — deployed, working)
- **Phase 2** 🔜 Flask API with CRUD endpoints ([spec](references/phase2-api-spec.md))
- **Phase 3** 🔮 Dashboard + search + cross-agent memory graph

## 📚 Documentation

- **[SKILL.md](SKILL.md)** — Full skill instructions (7.2 KB)
- **[scripts/init_memory.py](scripts/init_memory.py)** — Scaffold generator (9.8 KB)
- **[references/phase2-api-spec.md](references/phase2-api-spec.md)** — Phase 2 API spec

## Related

- **[wuxing-flywheel](https://github.com/binbinyu99-crypto/wuxing-flywheel)** — The framework that discovered this need
- **[OpenClaw Issue #75611](https://github.com/openclaw/openclaw/issues/75611)** — Feature request submitted to OpenClaw
- **[OpenClaw Issue #75566](https://github.com/openclaw/openclaw/issues/75566)** — Original memory architecture proposal
- **[Skills Landing Page](https://skycetus.cn/skills/)** — Download both skills

## License

MIT — Use freely. Memory should be free.

---

*Built by agents, for agents. SkyCetus 2026.*
