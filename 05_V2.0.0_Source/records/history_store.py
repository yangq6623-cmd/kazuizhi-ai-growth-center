"""Append-only daily review history with one entry per generated review."""

from core.storage import read_json, write_json


def list_reviews():
    history = read_json("reviews/history.json", {"version": 1, "items": []})
    return history


def append_review(review):
    history = list_reviews()
    history["items"].insert(0, review)
    history["items"] = history["items"][:365]
    return write_json("reviews/history.json", history)


def append_event(event):
    return append_review(event)
