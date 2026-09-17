"""Persistent audited learning memory and experiment records."""

from collections import Counter

from core.storage import now_iso, read_json, write_json


MAX_MEMORY_ENTRIES = 500
MAX_EXPERIMENTS = 200


def get_memory():
    return read_json("memory/learning_memory.json", {
        "version": 2,
        "updated_at": None,
        "entries": [],
        "message": "尚无学习记录；自主运行只会写入可追溯的事实、执行结果和实验结论。",
    })


def remember(category, statement, evidence=""):
    category = str(category or "自动学习")[:80]
    statement = str(statement or "").strip()[:500]
    evidence = str(evidence or "").strip()[:800]
    if not statement:
        raise ValueError("learning statement must not be empty")
    memory = get_memory()
    entries = memory.setdefault("entries", [])
    now = now_iso()
    for item in reversed(entries[-100:]):
        if item.get("category") == category and item.get("statement") == statement and item.get("evidence") == evidence:
            item["occurrence_count"] = int(item.get("occurrence_count") or 1) + 1
            item["last_seen_at"] = now
            memory["updated_at"] = now
            memory.pop("message", None)
            return write_json("memory/learning_memory.json", memory)
    entries.append({
        "id": f"memory-{len(entries) + 1}",
        "category": category,
        "statement": statement,
        "evidence": evidence,
        "created_at": now,
        "last_seen_at": now,
        "occurrence_count": 1,
    })
    memory["entries"] = entries[-MAX_MEMORY_ENTRIES:]
    memory["version"] = 2
    memory["updated_at"] = now
    memory.pop("message", None)
    return write_json("memory/learning_memory.json", memory)


def get_experiments():
    return read_json("memory/experiments.json", {"version": 2, "experiments": []})


def record_experiment(name, hypothesis, result, evidence="", status="completed"):
    data = get_experiments()
    items = data.setdefault("experiments", [])
    item = {
        "id": f"experiment-{len(items) + 1}",
        "name": str(name or "自动运营实验")[:120],
        "hypothesis": str(hypothesis or "")[:500],
        "result": str(result or "")[:800],
        "evidence": str(evidence or "")[:800],
        "status": str(status or "completed")[:40],
        "created_at": now_iso(),
    }
    items.append(item)
    data["experiments"] = items[-MAX_EXPERIMENTS:]
    data["version"] = 2
    write_json("memory/experiments.json", data)
    return item


def learning_profile():
    memory = get_memory()
    entries = memory.get("entries", [])
    categories = Counter(item.get("category") or "未分类" for item in entries)
    return {
        "entry_count": len(entries),
        "top_categories": [{"name": name, "count": count} for name, count in categories.most_common(10)],
        "updated_at": memory.get("updated_at"),
        "mode": "audited_memory_and_plan_optimization",
        "code_self_modification": False,
    }
