"""Export the latest R7/R8 decision context for the ChatGPT strategy layer."""

import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from core.storage import now_iso


MAX_QC_VIDEO_BYTES = 25 * 1024 * 1024


def _atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent,
            prefix=f".{path.name}.", suffix=".tmp", delete=False,
        ) as handle:
            temporary = Path(handle.name)
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            try:
                temporary.unlink()
            except OSError:
                pass


def _safe(value):
    return re.sub(r"[^0-9A-Za-z_.-]", "_", str(value or ""))[:80] or "item"


def _build_qc_preview(source, target):
    """Create a short low-resolution review copy when FINAL.MP4 is too large.

    Failure is intentionally non-fatal: the bridge will still export the
    technical/source evidence and mark the video preview as unavailable.
    """
    try:
        from promotion.video_worker import find_ffmpeg
        ffmpeg = find_ffmpeg()
    except (ImportError, OSError):
        ffmpeg = None
    if not ffmpeg:
        return False, "ffmpeg unavailable"
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.stem + ".tmp.mp4")
    command = [
        str(ffmpeg), "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(source), "-t", "12", "-vf", "scale=540:-2",
        "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "31",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(temporary),
    ]
    try:
        result = subprocess.run(
            command, capture_output=True, timeout=180, check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if result.returncode == 0 and temporary.is_file() and 1024 < temporary.stat().st_size <= MAX_QC_VIDEO_BYTES:
            os.replace(temporary, target)
            return True, None
        message = result.stderr.decode("utf-8", "replace")[-400:] if result.stderr else "preview invalid"
        return False, message
    except (OSError, subprocess.SubprocessError) as error:
        return False, str(error)[:400]
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass


def _stage_qc_evidence(root, qc_requests):
    """Copy FINAL.MP4 or a compact preview into the synced bridge for ChatGPT QC."""
    copied = 0
    previewed = 0
    skipped = 0
    items = []
    for request in qc_requests.get("items", []):
        value = dict(request)
        source_text = str(value.pop("local_candidate_path", "") or "")
        source = Path(source_text) if source_text else None
        if source and source.is_file():
            try:
                size = source.stat().st_size
            except OSError:
                size = 0
            directory = root / "outbox" / "content_qc" / _safe(value.get("video_id"))
            directory.mkdir(parents=True, exist_ok=True)
            if 0 < size <= MAX_QC_VIDEO_BYTES:
                target = directory / "FINAL.mp4"
                try:
                    if not target.is_file() or target.stat().st_size != size:
                        shutil.copy2(source, target)
                    value["bridge_video_path"] = str(target.relative_to(root)).replace("\\", "/")
                    value["evidence_status"] = "video_copied"
                    copied += 1
                except OSError as error:
                    value["evidence_status"] = "copy_failed"
                    value["evidence_error"] = str(error)[:240]
                    skipped += 1
            elif size > MAX_QC_VIDEO_BYTES:
                preview = directory / "PREVIEW.mp4"
                valid_existing = False
                try:
                    valid_existing = preview.is_file() and 1024 < preview.stat().st_size <= MAX_QC_VIDEO_BYTES
                except OSError:
                    valid_existing = False
                if valid_existing:
                    ok, error = True, None
                else:
                    ok, error = _build_qc_preview(source, preview)
                if ok:
                    value["bridge_video_path"] = str(preview.relative_to(root)).replace("\\", "/")
                    value["evidence_status"] = "preview_generated"
                    value["original_file_bytes"] = size
                    previewed += 1
                else:
                    value["evidence_status"] = "video_too_large_preview_failed"
                    value["evidence_error"] = str(error or "")[:240]
                    skipped += 1
            else:
                value["evidence_status"] = "video_empty"
                skipped += 1
        else:
            value["evidence_status"] = "candidate_missing"
            skipped += 1
        items.append(value)
    return {
        "schema": qc_requests.get("schema") or "kazuizhi-content-qc-requests/v1",
        "items": items,
        "count": len(items),
        "evidence": {
            "copied": copied, "previewed": previewed, "skipped": skipped,
            "max_video_bytes": MAX_QC_VIDEO_BYTES,
        },
    }


def export_decision_handoff(report):
    """Write R7 decision context plus pending production and post-render QC work.

    Keep the original v1 envelope for older R7 consumers. New content-factory
    fields are additive and explicitly versioned by ``extensions_schema``.
    """
    from integrations.bridge import bridge_status
    from promotion import content_factory
    from promotion.platform_rules import snapshot as platform_rule_snapshot

    status = bridge_status()
    if status.get("status") != "connected" or not status.get("bridge_root"):
        return {"exported": False, "status": status.get("status"), "reason": status.get("message")}
    root = Path(status["bridge_root"])
    content_requests = content_factory.pending_chatgpt_handoff()
    qc_builder = getattr(content_factory, "pending_chatgpt_qc_handoff", None)
    qc_requests = qc_builder() if callable(qc_builder) else {"items": [], "count": 0}
    qc_requests = _stage_qc_evidence(root, qc_requests)
    payload = {
        "schema": "kazuizhi-chatgpt-strategy-handoff/v1",
        "extensions_schema": "kazuizhi-chatgpt-content-extensions/v2",
        "exported_at": now_iso(),
        "source": "R7 autonomous decision center + R8 content factory",
        "decision_center": report,
        "content_production_requests": content_requests,
        "content_qc_requests": qc_requests,
        "platform_rule_center": platform_rule_snapshot(),
        "instruction": (
            "ChatGPT是唯一总控制。对content_production_requests负责经营判断、选题、痛点、标题、文案、"
            "深层脚本、分镜、素材决策、平台适配与质检标准，并按kazuizhi-content-production/v1以"
            "kind=content_production写回bridge inbox。对content_qc_requests检查FINAL.MP4或PREVIEW.MP4与"
            "技术/素材证据，以kind=content_qc返回pass或rework及原因。R7/R8负责状态、硬规则、审计、"
            "发布与数据回流；RTX3060和本地程序只执行。资金事项不得自动执行。"
        ),
    }
    target = root / "outbox" / "latest_decision.json"
    _atomic_json(target, payload)
    return {
        "exported": True,
        "path": str(target),
        "exported_at": payload["exported_at"],
        "content_requests": content_requests.get("count", 0),
        "content_qc_requests": qc_requests.get("count", 0),
        "qc_evidence": qc_requests.get("evidence"),
    }
