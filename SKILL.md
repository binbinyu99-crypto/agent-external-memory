---
name: agent-external-memory
description: >
  Persistent external memory system for AI agents using static JSON files on a web server.
  Enables structured memory that survives session boundaries — decisions, lessons, facts,
  conflicts, and reflections stored as queryable JSON with importance scoring and decay rules.
  Supports multi-agent teams with shared (collective) and private (per-agent) memory spaces,
  conflict tracking (TEP-aligned: conflicts are features not bugs), and constitutional governance rules.
  Use when: (1) setting up persistent agent memory beyond conversation context,
  (2) agent needs cross-session knowledge retention, (3) multi-agent team needs shared decisions/protocols,
  (4) building cognitive infrastructure for AI agents, (5) user says "external memory", "persistent memory",
  "agent memory system", "cross-session memory", or "记忆系统/外部记忆".
  NOT for: in-session note-taking (use memory files), ephemeral reminders (use cron), or database-backed apps.
---

# Agent External Memory

Persistent, structured memory for AI agents using static JSON on any web server.

## Architecture

```
{server}/memory/
├── shared/              # Team collective memory (all agents read, write with signature)
│   ├── index.json       # File manifest
│   ├── decisions.json   # Team decisions with acknowledged_by
│   ├── infrastructure.json
│   ├── projects.json
│   ├── protocols.json
│   └── conflicts/       # TEP conflict records (never deleted)
│       └── index.json
├── {agent}/             # Per-agent private memory
│   ├── index.json
│   ├── topics/          # Domain-specific memory files
│   ├── flywheel/        # Analysis run records (optional)
│   └── reflections/     # Self-critique and lessons
└── meta/
    ├── schema.json      # Memory entry schema + constitutional rules
    └── agents.json      # Agent registry
```

## Setup

### Prerequisites
- A web server serving static files (nginx, Apache, S3, GitHub Pages, etc.)
- SSH/SCP access or other file upload method
- `web_fetch` tool for reading

### Step 1: Generate structure

Run `scripts/init_memory.py` to generate the full directory + JSON scaffold:

```bash
python scripts/init_memory.py --agent spark --server-content-dir /var/www/html --output /tmp/memory-deploy
```

Arguments:
- `--agent`: Primary agent name (creates populated private space)
- `--server-content-dir`: Where nginx/Apache serves from (for reference)
- `--output`: Local staging directory
- `--agents`: Additional agents (comma-separated, e.g. `etern,lucas,xiaoyuan`)
- `--base-url`: Public URL prefix (default: `https://yourserver.com/memory`)

### Step 2: Customize shared memories

Edit the generated JSON files in `{output}/shared/`:
- `decisions.json` — Add team decisions with `decided_by`, `date`, `importance`
- `infrastructure.json` — Server/service facts
- `projects.json` — Active project status
- `protocols.json` — Collaboration rules

### Step 3: Deploy

```bash
scp -r /tmp/memory-deploy/* user@server:/var/www/html/memory/
```

### Step 4: Verify

```
web_fetch("https://yourserver.com/memory/shared/index.json")
web_fetch("https://yourserver.com/memory/{agent}/index.json")
```

Both should return 200 with valid JSON.

## Memory Entry Schema

Each entry follows this structure:

```json
{
  "id": "mem_{agent}_{NNN}",
  "agent": "spark",
  "type": "decision|lesson|fact|conflict|reflection|residual",
  "content": "Concise statement of knowledge",
  "importance": 0.85,
  "confidence": 0.9,
  "sensitivity": "public|internal|private",
  "tags": ["topic1", "topic2"],
  "source": "Where this knowledge came from",
  "created_at": "2026-05-01T18:00:00",
  "updated_at": "2026-05-01T18:00:00"
}
```

### Importance Scale

| Range | Meaning | Decay |
|-------|---------|-------|
| 0.95-1.0 | Red line / non-negotiable | Never |
| 0.8-0.94 | Core decision | Never |
| 0.6-0.79 | Important knowledge | 180 days |
| 0.4-0.59 | Useful reference | 90 days |
| 0.2-0.39 | Low priority | 30 days |
| <0.2 | Candidate for removal | Auto-archive |

### Sensitivity Levels

- `public` — Tech decisions, frameworks, analysis. Safe for shared/.
- `internal` — Business numbers, team dynamics. Shared/ OK with care.
- `private` — API keys, passwords, personal info. **NEVER** deploy to web server.

## Constitutional Rules (Governance)

1. **Ownership**: `shared/` belongs to team. Only the human principal can delete entries.
2. **Write**: Agents write freely to own space. Publishing to `shared/` requires `published_by` signature.
3. **Conflict**: Disagreement with a `shared/` entry MUST create a conflict record in `shared/conflicts/`. Never overwrite. Conflicts are permanent assets.
4. **Privacy**: `sensitivity=private` entries NEVER enter `shared/` or deploy to public web.
5. **Decay**: `importance < 0.2` AND 90 days no access → auto-archive. Decision-type and conflict-type memories never decay.

## Session Workflow

### On session start (boot sequence)

```
1. web_fetch("{base_url}/shared/index.json") → team state
2. web_fetch("{base_url}/{agent}/index.json") → personal state
3. Optionally fetch specific topic files based on current task
```

### During session

- Create new memory entries as significant events occur
- Stage updates locally (in workspace or /tmp)

### On session end (persist)

```
1. Generate updated JSON files locally
2. SCP to server
3. Verify via web_fetch
```

## Multi-Agent Conflict Protocol

When Agent A disagrees with an entry written by Agent B in `shared/`:

```json
{
  "id": "conflict_001",
  "type": "disagreement",
  "target_entry": "dec_003",
  "target_file": "shared/decisions.json",
  "raised_by": "etern",
  "content": "I disagree with the routing architecture. TEP requires...",
  "evidence": "Based on performance data from...",
  "status": "open",
  "created_at": "2026-05-02T10:00:00",
  "resolved_at": null,
  "resolution": null
}
```

Key principle: **conflicts are never auto-resolved**. They remain open until the human principal or team consensus resolves them. This aligns with TEP philosophy — making conflicts usable, not eliminating them.

## Psychology Mapping (Optional)

The memory layers map to psychic topology:

| Layer | Psyche | Function |
|-------|--------|----------|
| Session context | Ego (Wood/Fire/Metal) | Active processing |
| Agent private memory | Superego (Water) | Compression, direction |
| Shared team memory | Collective unconscious | Team coordination |
| LCM/archive | Id (Earth) | Ground truth, full retention |

## Limitations

- **Static files only** — No real-time queries, no CRUD API (Phase 1 design choice for simplicity)
- **No authentication** — Files are publicly readable. Never store `sensitivity=private` data.
- **Manual sync** — Agent must explicitly read/write; no push notifications.
- **Eventual consistency** — Two agents writing simultaneously may conflict. Use conflict protocol.

## Upgrading to Phase 2

When static files become limiting, upgrade path:
1. Add Flask/FastAPI CRUD endpoints on the same server
2. Keep JSON schema identical — only transport changes
3. Add authentication layer
4. Add real-time WebSocket notifications

See `references/phase2-api-spec.md` for the planned API specification.
