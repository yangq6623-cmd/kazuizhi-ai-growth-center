"""Persistent learning memory and experiment records."""

from core.storage import now_iso, read_json, write_json


def get_memory():
    return read_json("memory/learning_memory.json", {
        "version": 1,
        "updated_at": None,
        "entries": [],
        "message": "尚无学习记录；后续复盘只会写入可追溯的事实和实验结论。",
    })


def remember(category, statement, evidence=""):
    memory = get_memory()
    memory["entries"].append({
        "id": f"memory-{len(memory['entries']) + 1}",
        "category": category,
        "statement": statement,
        "evidence": evidence,
        "created_at": now_iso(),
    })
    memory["updated_at"] = now_iso()
    memory.pop("message", None)
    return write_json("memory/learning_memory.json", memory)


def get_experiments():
    return read_json("memory/experiments.json", {"version": 1, "experiments": []})

