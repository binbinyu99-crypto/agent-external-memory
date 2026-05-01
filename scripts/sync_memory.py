#!/usr/bin/env python3
"""
sync_memory.py v2 — Local-first agent memory with reinforcement and smart decay.

Commands:
  learn   — Write a memory entry (local, instant)
  recall  — Read/search memories (reinforces accessed entries)
  push    — Backup to server (private entries auto-filtered)
  pull    — Restore from server
  digest  — Smart compaction with merge + decay
  status  — Quick health check
"""

import argparse
import json
import os
import sys
import subprocess
import re
from datetime import datetime, timezone, timedelta
from collections import defaultdict

# Fix Windows GBK stdout
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# ── Config ──────────────────────────────────────────────────
AGENT = os.environ.get("MEMORY_AGENT", "spark")
LOCAL_DIR = os.environ.get("MEMORY_LOCAL_DIR",
    os.path.join(os.path.expanduser("~"), ".qclaw", "workspace", "spark-memory"))
SERVER = os.environ.get("MEMORY_SERVER", "Administrator@8.134.132.211")
REMOTE_DIR = os.environ.get("MEMORY_REMOTE_DIR", "C:/SkyCetus-2.0/content/memory")
BASE_URL = os.environ.get("MEMORY_BASE_URL", "https://skycetus.cn/memory")
TZ = timezone(timedelta(hours=8))

def now_iso():
    return datetime.now(TZ).strftime("%Y-%m-%dT%H:%M:%S+08:00")

def now_dt():
    return datetime.now(TZ)

def parse_iso(s):
    """Parse ISO timestamp, tolerant of various formats."""
    if not s:
        return None
    try:
        # Strip timezone for simple parsing
        clean = re.sub(r'[+-]\d{2}:\d{2}$', '', s)
        return datetime.strptime(clean, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=TZ)
    except:
        return None

def ensure_dirs():
    os.makedirs(os.path.join(LOCAL_DIR, AGENT, "topics"), exist_ok=True)

def load_json(path, default=None):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return default if default is not None else []

def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def topic_path(topic):
    return os.path.join(LOCAL_DIR, AGENT, "topics", f"{topic}.json")

def index_path():
    return os.path.join(LOCAL_DIR, AGENT, "index.json")

def effective_importance(entry):
    """Compute effective importance: base + reinforcement - decay."""
    base = entry.get("importance", 0.5)
    access = entry.get("access_count", 0)
    reinforcement = min(access * 0.02, 0.2)  # Cap at +0.2

    # Decay: non-decision/non-lesson types lose 0.01 per 7 days without access
    decay = 0.0
    etype = entry.get("type", "fact")
    if etype not in ("decision", "lesson"):
        last = parse_iso(entry.get("last_accessed") or entry.get("created_at"))
        if last:
            days_stale = (now_dt() - last).days
            decay = (days_stale // 7) * 0.01

    return max(0.0, min(1.0, base + reinforcement - decay))

# ── Commands ────────────────────────────────────────────────

def cmd_learn(args):
    """Write a memory entry."""
    ensure_dirs()
    tp = topic_path(args.topic)
    entries = load_json(tp, [])

    # Generate sequential ID
    max_id = 0
    for e in entries:
        m = re.search(r'_(\d+)$', e.get("id", ""))
        if m:
            max_id = max(max_id, int(m.group(1)))
    next_id = max_id + 1

    entry = {
        "id": f"mem_{AGENT}_{args.topic}_{next_id:03d}",
        "agent": AGENT,
        "type": args.type,
        "content": args.content,
        "importance": args.importance,
        "confidence": args.confidence,
        "sensitivity": args.sensitivity,
        "tags": args.tags.split(",") if args.tags else [args.topic],
        "source": args.source or "session",
        "access_count": 0,
        "last_accessed": None,
        "created_at": now_iso(),
        "updated_at": now_iso()
    }
    entries.append(entry)
    save_json(tp, entries)

    # Update index
    idx = load_json(index_path(), {"agent": AGENT, "topics": {}, "last_push": None})
    idx["topics"][args.topic] = {
        "file": f"topics/{args.topic}.json",
        "count": len(entries),
        "last_updated": now_iso()
    }
    idx["last_sync"] = now_iso()
    save_json(index_path(), idx)

    print(f"OK {entry['id']} [{args.type}] imp={args.importance} -> {args.topic} ({len(entries)} total)")


def cmd_recall(args):
    """Read/search memories. Reinforces accessed entries."""
    ensure_dirs()

    if args.query:
        # Search across all topics
        _search(args.query)
        return

    if args.topic:
        # Show one topic, reinforce access
        tp = topic_path(args.topic)
        entries = load_json(tp, [])
        if not entries:
            print(f"Empty: {args.topic}")
            return

        # Reinforce: bump access_count
        for e in entries:
            e["access_count"] = e.get("access_count", 0) + 1
            e["last_accessed"] = now_iso()
        save_json(tp, entries)

        # Sort by effective importance
        entries.sort(key=effective_importance, reverse=True)
        for e in entries:
            eff = effective_importance(e)
            ac = e.get("access_count", 0)
            print(f"  [{eff:.2f}|x{ac}] {e['id']}: {e['content'][:140]}")
    else:
        # Overview
        idx = load_json(index_path(), {})
        topics = idx.get("topics", {})
        if not topics:
            print("Memory is empty.")
            return
        lp = idx.get("last_push", "never")
        print(f"Agent: {AGENT} | Topics: {len(topics)} | Last push: {lp}")
        for name, meta in sorted(topics.items()):
            print(f"  [{meta.get('count', '?'):>3}] {name} (updated: {meta.get('last_updated', '?')[:10]})")


def _search(query):
    """Keyword search across all topic files."""
    topics_dir = os.path.join(LOCAL_DIR, AGENT, "topics")
    if not os.path.exists(topics_dir):
        print("No topics.")
        return

    q = query.lower()
    results = []
    for fname in os.listdir(topics_dir):
        if not fname.endswith(".json"):
            continue
        entries = load_json(os.path.join(topics_dir, fname), [])
        for e in entries:
            text = (e.get("content", "") + " " + " ".join(e.get("tags", []))).lower()
            if q in text:
                results.append((effective_importance(e), e))

    results.sort(key=lambda x: x[0], reverse=True)
    if not results:
        print(f"No results for '{query}'")
        return
    print(f"Found {len(results)} matches for '{query}':")
    for eff, e in results[:20]:
        print(f"  [{eff:.2f}] {e['id']}: {e['content'][:140]}")


def cmd_push(args):
    """Push to server. Private entries auto-filtered."""
    import tempfile, shutil

    server = args.server or SERVER
    remote = args.remote_dir or REMOTE_DIR
    agent_local = os.path.join(LOCAL_DIR, AGENT)

    if not os.path.exists(agent_local):
        print("Nothing to push.")
        return

    # Stage sanitized copy
    staging = os.path.join(tempfile.gettempdir(), f"memory_push_{AGENT}")
    if os.path.exists(staging):
        shutil.rmtree(staging)
    shutil.copytree(agent_local, staging)

    # Filter private entries
    priv = 0
    for root, _, files in os.walk(staging):
        for fname in files:
            if not fname.endswith(".json"):
                continue
            fpath = os.path.join(root, fname)
            data = load_json(fpath)
            if isinstance(data, list):
                filtered = [e for e in data if e.get("sensitivity") != "private"]
                removed = len(data) - len(filtered)
                if removed:
                    priv += removed
                    save_json(fpath, filtered)

    if priv:
        print(f"Filtered {priv} private entries")

    cmd = f'scp -r "{staging}" "{server}:{remote}/{AGENT}"'
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    shutil.rmtree(staging, ignore_errors=True)

    if r.returncode == 0:
        # Record push time
        idx = load_json(index_path(), {"agent": AGENT, "topics": {}})
        idx["last_push"] = now_iso()
        save_json(index_path(), idx)
        print(f"OK pushed to {server}")
    else:
        print(f"FAIL: {r.stderr[:200]}")
        sys.exit(1)


def cmd_pull(args):
    """Pull from server."""
    import urllib.request
    base = args.base_url or BASE_URL
    ensure_dirs()

    try:
        url = f"{base}/{AGENT}/index.json"
        with urllib.request.urlopen(url, timeout=10) as resp:
            idx = json.loads(resp.read().decode("utf-8"))
        save_json(index_path(), idx)

        count = 0
        for name, meta in idx.get("topics", {}).items():
            topic_url = f"{base}/{AGENT}/{meta['file']}"
            with urllib.request.urlopen(topic_url, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            save_json(topic_path(name), data)
            count += 1

        print(f"OK pulled {count} topics")
    except Exception as e:
        print(f"FAIL: {e}")
        sys.exit(1)


def cmd_digest(args):
    """Smart compaction: merge similar entries, decay stale ones, preserve lessons/decisions."""
    tp = topic_path(args.topic)
    entries = load_json(tp, [])
    if not entries:
        print("Empty topic.")
        return

    max_entries = args.max or 20
    original_count = len(entries)

    if len(entries) <= max_entries:
        print(f"Only {len(entries)} entries (limit {max_entries}). No digest needed.")
        return

    # Step 1: Never touch decisions and lessons
    protected = [e for e in entries if e.get("type") in ("decision", "lesson")]
    candidates = [e for e in entries if e.get("type") not in ("decision", "lesson")]

    # Step 2: Decay stale candidates
    for e in candidates:
        last = parse_iso(e.get("last_accessed") or e.get("created_at"))
        if last:
            days = (now_dt() - last).days
            if days > 30 and e.get("access_count", 0) == 0:
                e["importance"] = max(0.0, e.get("importance", 0.5) - 0.2)

    # Step 3: Sort candidates by effective importance, keep top N
    slots = max(0, max_entries - len(protected))
    candidates.sort(key=effective_importance, reverse=True)
    kept_candidates = candidates[:slots]
    removed = len(candidates) - slots

    final = protected + kept_candidates
    # Re-sort by creation time
    final.sort(key=lambda e: e.get("created_at", ""), reverse=False)

    save_json(tp, final)

    # Update index
    idx = load_json(index_path(), {"agent": AGENT, "topics": {}})
    if args.topic in idx.get("topics", {}):
        idx["topics"][args.topic]["count"] = len(final)
        idx["topics"][args.topic]["last_updated"] = now_iso()
        save_json(index_path(), idx)

    print(f"Digested {args.topic}: {original_count} -> {len(final)} ({removed} removed, {len(protected)} protected)")


def cmd_status(args):
    """Quick health check."""
    ensure_dirs()
    idx = load_json(index_path(), {})
    topics = idx.get("topics", {})

    total_entries = 0
    stale_topics = 0
    for name, meta in topics.items():
        total_entries += meta.get("count", 0)
        last = parse_iso(meta.get("last_updated"))
        if last and (now_dt() - last).days > 7:
            stale_topics += 1

    last_push = idx.get("last_push", "never")
    last_sync = idx.get("last_sync", "never")

    # Check staleness
    push_stale = True
    if last_push and last_push != "never":
        lp = parse_iso(last_push)
        if lp:
            push_stale = (now_dt() - lp).total_seconds() > 86400

    print(f"Agent: {AGENT}")
    print(f"Topics: {len(topics)} | Entries: {total_entries} | Stale topics: {stale_topics}")
    print(f"Last sync: {last_sync}")
    print(f"Last push: {last_push} {'(STALE - push recommended)' if push_stale else '(fresh)'}")

    if total_entries == 0:
        print("Memory is empty. Start with: learn --topic <topic> --content <what you know>")


# ── Main ────────────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser(description="Agent memory v2")
    sub = p.add_subparsers(dest="cmd")

    # learn
    l = sub.add_parser("learn", help="Write a memory entry")
    l.add_argument("--topic", required=True)
    l.add_argument("--content", required=True)
    l.add_argument("--importance", type=float, default=0.7)
    l.add_argument("--confidence", type=float, default=0.8)
    l.add_argument("--type", default="fact", choices=["fact", "lesson", "decision", "reflection"])
    l.add_argument("--sensitivity", default="internal", choices=["internal", "private"])
    l.add_argument("--tags", default=None)
    l.add_argument("--source", default=None)

    # recall
    r = sub.add_parser("recall", help="Read/search memories")
    r.add_argument("--topic", default=None)
    r.add_argument("--query", default=None)

    # push
    pu = sub.add_parser("push", help="Backup to server")
    pu.add_argument("--server", default=None)
    pu.add_argument("--remote-dir", default=None)

    # pull
    pl = sub.add_parser("pull", help="Restore from server")
    pl.add_argument("--base-url", default=None)

    # digest
    d = sub.add_parser("digest", help="Smart compaction")
    d.add_argument("--topic", required=True)
    d.add_argument("--max", type=int, default=20)

    # status
    sub.add_parser("status", help="Health check")

    # Backward compat aliases
    sub.add_parser("write")  # -> learn
    sub.add_parser("read")   # -> recall
    sub.add_parser("search") # -> recall --query
    sub.add_parser("compact") # -> digest

    args = p.parse_args()
    cmd = args.cmd

    if cmd == "learn":
        cmd_learn(args)
    elif cmd == "recall":
        cmd_recall(args)
    elif cmd == "push":
        cmd_push(args)
    elif cmd == "pull":
        cmd_pull(args)
    elif cmd == "digest":
        cmd_digest(args)
    elif cmd == "status":
        cmd_status(args)
    # Backward compat
    elif cmd == "write":
        print("'write' is deprecated. Use 'learn' instead.")
        args.type = getattr(args, 'type', 'fact')
        args.sensitivity = 'internal'
        cmd_learn(args)
    elif cmd == "read":
        cmd_recall(args)
    elif cmd == "search":
        cmd_recall(args)
    elif cmd == "compact":
        cmd_digest(args)
    else:
        p.print_help()

if __name__ == "__main__":
    main()
