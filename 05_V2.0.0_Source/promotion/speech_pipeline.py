"""Optional local speech/subtitle execution for R8 video output.

This module is execution-only.  ChatGPT supplies narration and subtitle text in
the production contract.  Windows SAPI is used when available; otherwise the
video remains valid and the adapter reports a truthful degraded state.  Whisper
verification is only enabled when a local model path is explicitly provided,
so the runtime never downloads a model unexpectedly.
"""

from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import tempfile
from pathlib import Path



def status():
    powershell = shutil.which("powershell.exe") or shutil.which("powershell") or shutil.which("pwsh")
    whisper_model = os.environ.get("KAZUIZHI_WHISPER_MODEL_PATH", "").strip()
    faster = importlib.util.find_spec("faster_whisper") is not None
    return {
        "tts": {
            "available": bool(os.name == "nt" and powershell),
            "engine": "Windows SAPI" if os.name == "nt" and powershell else "not_available",
        },
        "subtitles": {"available": True, "format": "srt"},
        "whisper_qc": {
            "available": bool(faster and whisper_model and Path(whisper_model).exists()),
            "model_path_configured": bool(whisper_model),
            "engine": "faster-whisper-local" if faster else "not_installed",
        },
    }


def _stamp(seconds):
    milliseconds = max(0, int(round(float(seconds) * 1000)))
    hours, rest = divmod(milliseconds, 3600000)
    minutes, rest = divmod(rest, 60000)
    secs, ms = divmod(rest, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}"


def build_srt(plan, path):
    current = 2.0  # intro segment
    blocks = []
    index = 1
    for shot in (plan or {}).get("storyboard") or []:
        if not isinstance(shot, dict):
            continue
        duration = max(1.0, min(float(shot.get("duration_seconds") or 3), 15.0))
        text = str(shot.get("subtitle") or shot.get("narration") or "").strip()
        if text:
            blocks.append(f"{index}\n{_stamp(current)} --> {_stamp(current + duration)}\n{text}\n")
            index += 1
        current += duration
    path = Path(path)
    path.write_text("\n".join(blocks), encoding="utf-8")
    return str(path)


def _narration(plan):
    pieces = []
    for shot in (plan or {}).get("storyboard") or []:
        if isinstance(shot, dict):
            text = str(shot.get("narration") or shot.get("subtitle") or "").strip()
            if text:
                pieces.append(text)
    return "。".join(pieces)


def _sapi_tts(text, output):
    engine = shutil.which("powershell.exe") or shutil.which("powershell") or shutil.which("pwsh")
    if os.name != "nt" or not engine:
        return {"status": "not_available", "path": None, "message": "当前系统未提供Windows SAPI执行环境"}
    if not text:
        return {"status": "skipped", "path": None, "message": "生产合同没有可配音文本"}
    output = Path(output)
    script = None
    text_file = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", encoding="utf-8", delete=False) as handle:
            text_file = Path(handle.name)
            handle.write(text)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".ps1", encoding="utf-8", delete=False) as handle:
            script = Path(handle.name)
            handle.write(
                "param([string]$TextPath,[string]$OutPath)\n"
                "Add-Type -AssemblyName System.Speech\n"
                "$s=New-Object System.Speech.Synthesis.SpeechSynthesizer\n"
                "$t=[System.IO.File]::ReadAllText($TextPath,[System.Text.Encoding]::UTF8)\n"
                "$s.SetOutputToWaveFile($OutPath)\n"
                "$s.Speak($t)\n"
                "$s.Dispose()\n"
            )
        result = subprocess.run(
            [engine, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script), str(text_file), str(output)],
            capture_output=True, timeout=180, check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if result.returncode == 0 and output.is_file() and output.stat().st_size > 1024:
            return {"status": "ready", "path": str(output), "message": "Windows SAPI本地配音已生成"}
        message = (result.stderr or result.stdout).decode("utf-8", "replace")[-500:]
        return {"status": "failed", "path": None, "message": message or "本地配音生成失败"}
    except (OSError, subprocess.SubprocessError) as error:
        return {"status": "failed", "path": None, "message": str(error)[:500]}
    finally:
        for temporary in (script, text_file):
            if temporary:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:
                    pass


def _mux_audio(ffmpeg, video, audio):
    video = Path(video)
    audio = Path(audio)
    temporary = video.with_name(video.stem + ".audio.tmp.mp4")
    command = [
        str(ffmpeg), "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(video), "-i", str(audio),
        "-filter_complex", "[1:a]apad=pad_dur=10[a]",
        "-map", "0:v:0", "-map", "[a]", "-c:v", "copy", "-c:a", "aac",
        "-b:a", "128k", "-shortest", "-movflags", "+faststart", str(temporary),
    ]
    result = subprocess.run(
        command, capture_output=True, timeout=300, check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if result.returncode != 0 or not temporary.is_file() or temporary.stat().st_size < 10 * 1024:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        message = result.stderr.decode("utf-8", "replace")[-500:]
        return {"status": "failed", "message": message or "配音封装失败"}
    os.replace(temporary, video)
    return {"status": "ready", "message": "本地配音已封装进FINAL.MP4"}


def _whisper_qc(audio, expected_text):
    model_path = os.environ.get("KAZUIZHI_WHISPER_MODEL_PATH", "").strip()
    if not model_path or not Path(model_path).exists() or importlib.util.find_spec("faster_whisper") is None:
        return {"status": "not_configured", "passed": None, "message": "未配置本地Whisper模型，跳过语音转写质检"}
    try:
        from faster_whisper import WhisperModel
        model = WhisperModel(model_path, device="cpu", compute_type="int8", local_files_only=True)
        segments, _ = model.transcribe(str(audio), language="zh", beam_size=1)
        transcript = "".join(segment.text for segment in segments).strip()
        expected = "".join(str(expected_text or "").split())
        actual = "".join(transcript.split())
        common = sum(1 for char in expected if char in actual)
        ratio = common / max(1, len(expected))
        return {
            "status": "checked", "passed": ratio >= 0.55, "similarity": round(ratio, 3),
            "transcript": transcript[:1000],
        }
    except Exception as error:
        return {"status": "failed", "passed": None, "message": str(error)[:500]}


def enhance_final(video_id, plan, final_path, ffmpeg):
    """Create subtitle sidecar, optionally add local TTS, and report speech QC."""
    final_path = Path(final_path)
    output_root = final_path.parent
    subtitle_path = output_root / "FINAL.srt"
    build_srt(plan, subtitle_path)
    voice_enabled = bool(((plan or {}).get("voice") or {}).get("enabled", True))
    narration = _narration(plan)
    result = {
        "video_id": str(video_id or ""),
        "subtitle": {"status": "ready", "path": str(subtitle_path)},
        "tts": {"status": "skipped", "path": None, "message": "生产合同未启用配音"},
        "whisper_qc": {"status": "not_run", "passed": None},
    }
    if not voice_enabled:
        return result
    wav = output_root / "narration.wav"
    tts = _sapi_tts(narration, wav)
    result["tts"] = tts
    if tts.get("status") == "ready":
        mux = _mux_audio(ffmpeg, final_path, wav)
        result["tts"]["mux"] = mux
        if mux.get("status") == "ready":
            result["whisper_qc"] = _whisper_qc(wav, narration)
    return result
