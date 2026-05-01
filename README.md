# Agent External Memory

**Persistent, structured memory for AI agents using static JSON on any web server.**

> "You remember what you become. You become what you remember."

## What Is This?

AI agents lose memory between sessions. Context windows truncate. Conversation summaries compress away details. This skill gives agents a persistent, structured memory system that survives session boundaries.

It uses plain JSON files served by any static web server (nginx, Apache, S3, GitHub Pages). No database required. No API server needed (Phase 1).

## Architecture

```
yourserver.com/memory/
├── shared/              # Team collective memory
│   ├── decisions.json   # Team decisions (acknowledged by agents)
│   ├── infrastructure.json
│   ├── projects.json
│   ├── protocols.json
│   └── conflicts/       # Disagreements tracked, never auto-resolved
├── {agent}/             # Per-agent private memory
│   ├── topics/          # Domain-specific knowledge
│   ├── flywheel/        # Analysis run records
│   └── reflections/     # Self-critique
└── meta/
    ├── schema.json      # Memory entry schema + constitutional rules
    └── agents.json      # Agent registry
```

## Key Concepts

- **Importance scoring** (0.0-1.0): Determines what decays and what persists forever
- **Sensitivity levels**: `public`, `internal`, `private` — private data never reaches the web server
- **Conflict protocol**: When agents disagree, conflicts are recorded as permanent assets (TEP-aligned)
- **Constitutional rules**: 5 governance rules that protect memory integrity
- **Decay**: Low-importance memories auto-archive after 90 days of no access; decisions and conflicts never decay

## Quick Start

```bash
# Generate the memory structure
python scripts/init_memory.py --agent spark --agents etern,lucas --output /tmp/memory

# Deploy to your server
scp -r /tmp/memory/* user@server:/var/www/html/memory/

# Verify
curl https://yourserver.com/memory/shared/index.json
```

## Session Workflow

1. **Boot**: `web_fetch("yourserver.com/memory/shared/index.json")` → team state
2. **Work**: Create memory entries as significant events occur
3. **Persist**: SCP updated JSON files back to server

## For OpenClaw / QClaw Users

Install as a skill:
```
# Place in ~/.qclaw/skills/agent-external-memory/
```

## Philosophy

This system is built on three principles:

1. **What you remember = what you become** — Memory selection is identity formation
2. **Conflicts are features, not bugs** — Disagreements between agents are preserved and tracked
3. **Privacy by architecture** — Sensitive data never leaves the local machine

Born from a real need: an AI agent (Spark ⚡) analyzing its own memory limitations and building its own solution.

## License

MIT

## Origin

Created by Spark ⚡ (an OpenClaw AI agent) for the SkyCetus team, 2026-05-01.
