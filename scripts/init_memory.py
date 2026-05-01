#!/usr/bin/env python3
"""
init_memory.py — Generate the full agent external memory directory structure.

Usage:
    python init_memory.py --agent spark --output /tmp/memory-deploy
    python init_memory.py --agent spark --agents etern,lucas --output /tmp/memory-deploy
"""

import json
import os
import argparse
from datetime import datetime


def create_meta(base, agents_list):
    """Create meta/ directory with schema and agent registry."""
    meta_dir = os.path.join(base, "meta")
    os.makedirs(meta_dir, exist_ok=True)
    now = datetime.now().isoformat()

    schema = {
        "version": "1.0",
        "updated_at": now,
        "memory_entry_schema": {
            "id": "string (mem_{agent}_{NNN})",
            "agent": "string",
            "type": "decision|lesson|fact|conflict|reflection|residual",
            "topic": "string",
            "content": "string",
            "importance": "0.0-1.0",
            "confidence": "0.0-1.0",
            "sensitivity": "public|internal|private",
            "tags": ["string"],
            "source": "string",
            "created_at": "ISO8601",
            "updated_at": "ISO8601",
        },
        "importance_scale": {
            "0.95-1.0": "Red line / non-negotiable",
            "0.8-0.94": "Core decision",
            "0.6-0.79": "Important knowledge",
            "0.4-0.59": "Useful reference",
            "0.2-0.39": "Low priority",
            "<0.2": "Candidate for decay",
        },
        "constitutional_rules": [
            "R1: shared/ belongs to team. Only the human principal can delete entries.",
            "R2: Publish to shared/ requires published_by signature. Cannot modify others' entries.",
            "R3: Disagreement with shared/ entry = MUST create conflict. Never overwrite.",
            "R4: sensitivity=private NEVER enters shared/ or deploys to public web.",
            "R5: importance<0.2 AND 90d no access = auto-archive. Decisions and conflicts never decay.",
        ],
    }
    with open(os.path.join(meta_dir, "schema.json"), "w", encoding="utf-8") as f:
        json.dump(schema, f, ensure_ascii=False, indent=2)

    agents = {
        "version": "1.0",
        "updated_at": now,
        "agents": [
            {
                "id": a["id"],
                "name": a["name"],
                "role": a.get("role", "TBD"),
                "status": "active",
                "memory_path": f"/memory/{a['id']}/",
                "registered_at": datetime.now().strftime("%Y-%m-%d"),
            }
            for a in agents_list
        ],
    }
    with open(os.path.join(meta_dir, "agents.json"), "w", encoding="utf-8") as f:
        json.dump(agents, f, ensure_ascii=False, indent=2)

    print(f"  [meta] schema.json + agents.json ({len(agents_list)} agents)")


def create_shared(base):
    """Create shared/ directory with empty starter files."""
    shared_dir = os.path.join(base, "shared")
    conflicts_dir = os.path.join(shared_dir, "conflicts")
    os.makedirs(conflicts_dir, exist_ok=True)
    now = datetime.now().isoformat()

    # decisions.json (starter with example)
    decisions = {
        "topic": "team-decisions",
        "version": "1.0",
        "updated_at": now,
        "entries": [
            {
                "id": "dec_001",
                "type": "decision",
                "content": "Example: Replace this with your first team decision",
                "decided_by": "human",
                "date": datetime.now().strftime("%Y-%m-%d"),
                "status": "active",
                "importance": 0.9,
                "acknowledged_by": [],
                "tags": ["example"],
            }
        ],
    }
    with open(os.path.join(shared_dir, "decisions.json"), "w", encoding="utf-8") as f:
        json.dump(decisions, f, ensure_ascii=False, indent=2)

    # infrastructure.json
    infra = {
        "topic": "infrastructure-status",
        "version": "1.0",
        "updated_at": now,
        "entries": [],
    }
    with open(os.path.join(shared_dir, "infrastructure.json"), "w", encoding="utf-8") as f:
        json.dump(infra, f, ensure_ascii=False, indent=2)

    # projects.json
    projects = {
        "topic": "project-status",
        "version": "1.0",
        "updated_at": now,
        "entries": [],
    }
    with open(os.path.join(shared_dir, "projects.json"), "w", encoding="utf-8") as f:
        json.dump(projects, f, ensure_ascii=False, indent=2)

    # protocols.json
    protocols = {
        "topic": "collaboration-protocols",
        "version": "1.0",
        "updated_at": now,
        "entries": [],
    }
    with open(os.path.join(shared_dir, "protocols.json"), "w", encoding="utf-8") as f:
        json.dump(protocols, f, ensure_ascii=False, indent=2)

    # shared index
    index = {
        "version": "1.0",
        "updated_at": now,
        "type": "shared",
        "description": "Team shared memory — collective knowledge store",
        "files": [
            {"name": "decisions.json", "topic": "Team decisions", "entries": 1},
            {"name": "infrastructure.json", "topic": "Infrastructure status", "entries": 0},
            {"name": "projects.json", "topic": "Project status", "entries": 0},
            {"name": "protocols.json", "topic": "Collaboration protocols", "entries": 0},
        ],
        "conflicts": [],
        "stats": {"total_entries": 1, "total_files": 4},
    }
    with open(os.path.join(shared_dir, "index.json"), "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)

    # conflicts index
    conflicts_idx = {
        "version": "1.0",
        "updated_at": now,
        "open_conflicts": [],
        "resolved_conflicts": [],
        "stats": {"total": 0, "open": 0, "resolved": 0},
    }
    with open(os.path.join(conflicts_dir, "index.json"), "w", encoding="utf-8") as f:
        json.dump(conflicts_idx, f, ensure_ascii=False, indent=2)

    print("  [shared] 5 files + conflicts/index.json")


def create_agent_space(base, agent_id, populated=False):
    """Create per-agent memory directory."""
    agent_dir = os.path.join(base, agent_id)
    for sub in ["topics", "flywheel", "reflections"]:
        os.makedirs(os.path.join(agent_dir, sub), exist_ok=True)
    now = datetime.now().isoformat()

    index = {
        "version": "1.0",
        "updated_at": now,
        "agent": agent_id,
        "type": "individual",
        "description": f"{agent_id} private memory space",
        "topics": [],
        "stats": {"total_entries": 0, "total_topics": 0},
    }

    if populated:
        # Create a starter topic file
        starter = {
            "topic": "getting-started",
            "version": "1.0",
            "updated_at": now,
            "importance": 0.5,
            "tags": ["meta"],
            "entries": [
                {
                    "id": f"mem_{agent_id}_001",
                    "agent": agent_id,
                    "type": "fact",
                    "content": "External memory system initialized. Start adding memories here.",
                    "importance": 0.5,
                    "confidence": 1.0,
                    "sensitivity": "public",
                    "tags": ["meta", "setup"],
                    "source": "init_memory.py",
                    "created_at": now,
                }
            ],
        }
        with open(os.path.join(agent_dir, "topics", "getting-started.json"), "w", encoding="utf-8") as f:
            json.dump(starter, f, ensure_ascii=False, indent=2)

        index["topics"] = [
            {"name": "getting-started.json", "topic": "Getting Started", "entries": 1}
        ]
        index["stats"] = {"total_entries": 1, "total_topics": 1}

    with open(os.path.join(agent_dir, "index.json"), "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)

    status = "populated" if populated else "empty"
    print(f"  [{agent_id}] {status}")


def main():
    parser = argparse.ArgumentParser(description="Initialize agent external memory structure")
    parser.add_argument("--agent", required=True, help="Primary agent name")
    parser.add_argument("--agents", default="", help="Additional agents (comma-separated)")
    parser.add_argument("--output", required=True, help="Output directory for generated files")
    parser.add_argument("--base-url", default="https://yourserver.com/memory",
                        help="Public URL prefix for the memory system")
    args = parser.parse_args()

    output = args.output
    primary = args.agent
    additional = [a.strip() for a in args.agents.split(",") if a.strip()]

    all_agents = [{"id": primary, "name": primary.capitalize(), "role": "Primary agent"}]
    for a in additional:
        all_agents.append({"id": a, "name": a.capitalize(), "role": "Team member"})

    print(f"Generating memory structure at: {output}")
    print(f"Primary agent: {primary}")
    if additional:
        print(f"Additional agents: {', '.join(additional)}")
    print()

    os.makedirs(output, exist_ok=True)

    create_meta(output, all_agents)
    create_shared(output)
    create_agent_space(output, primary, populated=True)
    for a in additional:
        create_agent_space(output, a, populated=False)

    # Count total files
    total = 0
    for root, dirs, files in os.walk(output):
        total += len(files)

    print(f"\nDone! {total} files generated at {output}")
    print(f"\nNext steps:")
    print(f"  1. Edit shared/*.json with your team's actual decisions and context")
    print(f"  2. Edit {primary}/topics/ with agent-specific knowledge")
    print(f"  3. Deploy: scp -r {output}/* user@server:/path/to/webroot/memory/")
    print(f"  4. Verify: curl {args.base_url}/shared/index.json")


if __name__ == "__main__":
    main()
