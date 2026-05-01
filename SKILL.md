---
name: agent-external-memory
version: 2.0.0
description: >
  Local-first structured memory for AI agents. Survives session boundaries.
  Local = instinct (fast, always available). Server = backup/sharing (when needed).
  Use when: agent needs cross-session knowledge retention, structured lessons/decisions,
  or multi-agent shared state.
  NOT for: in-session notes (use memory/ files), ephemeral reminders (use cron),
  or anything requiring real-time queries (use a database).
---

# Agent External Memory v2

**Two layers. No more.**

| Layer | Role | Speed | Dependency |
|-------|------|-------|------------|
| Local (`spark-memory/`) | Instinct | ~5ms | None |
| Server (`skycetus.cn/memory/`) | Backup + sharing | ~2s | Network + SSH |

## Script Location

```
{skill_dir}/scripts/sync_memory.py
```

Python: `C:\Program Files\Python312\python.exe`

## Commands

### learn — Write a memory (the only write command you need)

```bash
python sync_memory.py learn --topic <topic> --content "<what you learned>" [--importance 0.8] [--type lesson|decision|fact|reflection] [--sensitivity private]
```

- Default importance: 0.7
- Default type: fact
- Default sensitivity: internal (safe to push)
- `--sensitivity private` → NEVER pushed to server

### recall — Read memories (reinforces accessed entries)

```bash
python sync_memory.py recall                    # Show all topics overview
python sync_memory.py recall --topic <topic>    # Show entries, boost access_count
python sync_memory.py recall --query "keyword"  # Search across all topics
```

Every `recall --topic` call increments `access_count` on matched entries. Frequently recalled memories naturally rise in effective importance.

### push — Backup to server (private entries auto-filtered)

```bash
python sync_memory.py push
```

### pull — Restore from server

```bash
python sync_memory.py pull
```

### digest — Smart compaction (not dumb truncation)

```bash
python sync_memory.py digest --topic <topic> [--max 20]
```

Unlike v1 compact (which just deleted low-importance entries), digest:
1. Groups entries by similarity (simple keyword overlap)
2. Merges related entries into consolidated ones
3. Decays entries that haven't been accessed in 30+ days
4. Preserves all decision/lesson types regardless of age

### status — Quick health check

```bash
python sync_memory.py status
```

Shows: total entries, topics, staleness, last push time, entries needing decay.

## Mandatory Integration Points

### 1. Session Start (Boot Sequence)

Already in AGENTS.md step 5. On every session start:

```
python sync_memory.py status
```

If stale (>24h since last sync and server is reachable):

```
python sync_memory.py pull
```

### 2. Post-Work Writeback (MANDATORY REFLEX)

**After ANY of these events, you MUST call `learn`:**

- Flywheel analysis completed → `learn --topic flywheel-runs`
- Infrastructure fixed/deployed → `learn --topic infrastructure`
- Bug found and fixed → `learn --topic lessons`
- Robin makes a key decision → `learn --topic robin-decisions`
- Architecture/design change → `learn --topic architecture`
- API/tool quirk discovered → `learn --topic tool-quirks`

**This is not optional. This is the Water→Wood cycle. Without writeback, every session starts from zero.**

### 3. Before Flywheel Analysis

Before running 五行飞轮 on any topic:

```
python sync_memory.py recall --query "<topic keywords>"
```

Feed relevant memories into the analysis as prior knowledge. This is the Wood phase's seed enrichment.

## Memory Entry Schema (v2)

```json
{
  "id": "mem_spark_topic_001",
  "agent": "spark",
  "type": "fact|lesson|decision|reflection",
  "content": "Concise statement",
  "importance": 0.85,
  "confidence": 0.8,
  "sensitivity": "internal|private",
  "tags": ["tag1", "tag2"],
  "source": "session|flywheel|robin|heartbeat",
  "access_count": 0,
  "last_accessed": null,
  "created_at": "2026-05-01T23:00:00+08:00",
  "updated_at": "2026-05-01T23:00:00+08:00"
}
```

### Effective Importance (computed, not stored)

```
effective_importance = importance + (access_count * 0.02) - decay_penalty
```

- `access_count * 0.02`: frequently recalled = more important (reinforcement)
- `decay_penalty`: 0.01 per 7 days since last access, for non-decision/non-lesson types
- Decisions and lessons never decay

### Sensitivity Rules

| Level | Local | Server | Description |
|-------|-------|--------|-------------|
| internal | ✅ | ✅ | Safe for server. Tech decisions, frameworks, analysis. |
| private | ✅ | ❌ | API keys, passwords, personal info. NEVER leaves local. |

No "public" level. If it's on the server, it's readable by anyone with the URL.

## Relationship with LCM

| Dimension | LCM | External Memory |
|-----------|-----|-----------------|
| What | Event memory (conversations) | Knowledge memory (distilled lessons) |
| How | Automatic, passive | Active, agent-controlled |
| Format | Text summaries (DAG) | Structured JSON |
| Search | lcm_grep (semantic) | recall --query (keyword) |
| Sharing | Single session | Multi-agent capable |
| Decay | Automatic compaction | Access-based reinforcement |

**Rule: Don't duplicate LCM.** External memory stores what LCM can't:
- Structured decisions with metadata
- Cross-session lessons (LCM compacts away details)
- Multi-agent shared state
- Importance-ranked knowledge

## What Was Cut from v1

| Feature | Why cut |
|---------|---------|
| Conflict protocol | Never used. Add back when 2+ agents actually write simultaneously. |
| Psyche mapping | Branding, not function. |
| Constitutional governance | Over-engineered for current scale. |
| Importance decay table | Replaced by access-based reinforcement (simpler, data-driven). |
| Multiple sensitivity levels | Reduced to 2 (internal/private). Binary is enforceable. |

## Upgrade Path

When this outgrows JSON files:
1. Add SQLite with FTS5 for full-text search
2. Add embedding vectors for semantic recall
3. Add WebSocket for real-time cross-agent sync
4. Platform-level hooks for true auto-read/write (requires OpenClaw support)
