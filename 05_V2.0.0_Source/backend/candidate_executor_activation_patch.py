"""Make the production-monitor candidate button actively start real Wan work.

The normal simple flow already creates candidate tasks.  The old monitor button
skipped any shot that already had such a task, so after an interrupted/restarted
executor it could appear to do nothing.  This patch adds an explicit same-origin
activation endpoint that makes the latest project mission current, repairs only
unfinished stale checkpoints, verifies ComfyUI/assets, and starts the serialized
Wan executor.  It also appends a capture-phase browser handler so the owner gets
immediate truthful feedback instead of a silent no-op.
"""
from __future__ import annotations

from pathlib import Path
from urllib.parse import urlsplit

from backend import kz_local_control_patch as _video
from backend import production_mission_patch as _mission
from backend import quality_ai_runtime_patch as _quality
from backend import server
from promotion import ai_production_center as _center

_INSTALLED = False
_ACTIVATE_PATH = "/api/candidate-executor/activate"
_MONITOR_PATHS = {"/content-production-monitor.js", "/web/content-production-monitor.js"}


def _origin_allowed(handler):
    origin = str(handler.headers.get("Origin") or "").strip()
    return not origin or origin in {
        f"http://127.0.0.1:{handler.server.server_port}",
        f"http://localhost:{handler.server.server_port}",
    }


def _latest_project_and_shots():
    dashboard = _center.dashboard()
    project = (dashboard.get("projects") or [None])[0]
    if not project:
        raise ValueError("当前没有可执行的内容生产项目")
    project_id = str(project.get("id") or "")
    shots = sorted(
        [x for x in (dashboard.get("storyboards") or []) if str(x.get("project_id") or "") == project_id],
        key=lambda x: int(x.get("order") or 0),
    )
    if not shots:
        raise ValueError("当前项目还没有镜头分镜")
    return project, shots


def _activate_latest_mission():
    project, shots = _latest_project_and_shots()
    mission = _mission._sync_project(project, shots)
    data = _mission._load()
    current = _mission._mission_for_project(data, project.get("id"))
    if not current:
        raise RuntimeError("内容生产任务没有正确建立")

    # The Comfy worker historically claims the first mission when no id is
    # supplied.  Make the project visible in the monitor the active mission.
    missions = data.get("missions") or []
    data["missions"] = [current] + [x for x in missions if x is not current]

    original_thread = getattr(_video, "_EXECUTOR_THREAD", None)
    executor_alive = bool(original_thread and original_thread.is_alive())
    repaired = 0
    for shot in current.get("shots") or []:
        for candidate in shot.get("candidates") or []:
            state = str(candidate.get("status") or "pending")
            has_output = bool(candidate.get("output_id") or candidate.get("file_url"))
            if has_output:
                continue
            # A manual click means "continue/fill missing candidates".  Only
            # unfinished checkpoints are re-armed; completed checkpoints stay.
            if state in {"retry_wait", "failed_terminal"}:
                candidate["status"] = "pending"
                candidate["next_retry_at"] = ""
                candidate["last_error"] = ""
                repaired += 1
            elif state == "generating" and not executor_alive:
                candidate["status"] = "pending"
                candidate["last_error"] = "检测到执行器已停止，已恢复为待生成。"
                repaired += 1

    if current.get("status") in {"paused", "needs_attention", "waiting_retry", "ready"}:
        current["status"] = "running"
    current["updated_at"] = _mission._now()
    current.setdefault("events", []).insert(0, {
        "at": _mission._now(),
        "kind": "manual_candidate_activation",
        "detail": "老板点击生成/补齐候选；已激活当前项目的真实 ComfyUI 执行器。",
    })
    _mission._save(data)

    images = _video._recent_image_assets()
    if not images:
        raise ValueError("当前没有可用图片素材。受控双镜头测试请先上传至少1张图片；正式纯文案模式后续会自动生成首帧。")
    comfy = _quality._comfyui_ready()
    if not comfy.get("ok"):
        raise RuntimeError(comfy.get("message") or "ComfyUI / Wan2.1 尚未就绪")

    _video._start_comfy_worker()
    snapshot = _video._executor_snapshot()
    summary = _mission.current_mission().get("mission") or {}
    return {
        "ok": True,
        "message": "真实候选执行器已启动",
        "project_id": project.get("id"),
        "shot_count": len(shots),
        "image_assets": len(images),
        "repaired_checkpoints": repaired,
        "mission": summary,
        "executor": snapshot,
        "comfyui": comfy,
    }


_BROWSER_APPEND = r'''
;(() => {
  if (window.__KZ_CANDIDATE_ACTIVATION_PATCH__) return;
  window.__KZ_CANDIDATE_ACTIVATION_PATCH__ = true;
  let pollTimer = null;
  function toast(text, bad=false) {
    let node=document.getElementById('kz-candidate-activation-toast');
    if(!node){
      node=document.createElement('div'); node.id='kz-candidate-activation-toast';
      node.style.cssText='position:fixed;right:22px;bottom:22px;z-index:10050;max-width:430px;padding:11px 14px;border-radius:8px;background:#17324f;color:#fff;font:12px/1.5 sans-serif;box-shadow:0 8px 26px rgba(0,0,0,.18)';
      document.body.appendChild(node);
    }
    node.style.background=bad?'#b43b3b':'#17324f'; node.textContent=text; node.hidden=false;
  }
  async function statusPoll(){
    try{
      const r=await fetch('/api/comfyui-executor/status',{cache:'no-store'}); const d=await r.json();
      const state=d?.status||d?.executor?.status||''; const msg=d?.message||d?.executor?.message||''; const err=d?.last_error||d?.executor?.last_error||'';
      if(err){toast(`ComfyUI执行异常：${err}`,true); clearInterval(pollTimer); pollTimer=null; return;}
      if(state==='running'){toast(msg||'ComfyUI正在真实生成镜头候选…');}
      if(['idle','completed'].includes(state)){toast(msg||'本轮候选执行已结束。'); clearInterval(pollTimer); pollTimer=null;}
    }catch(_){ }
  }
  document.addEventListener('click', async event => {
    const button=event.target.closest?.('#kz-queue-all'); if(!button) return;
    event.preventDefault(); event.stopPropagation(); event.stopImmediatePropagation();
    button.disabled=true; button.textContent='正在启动真实候选生成…';
    toast('正在检查当前任务、素材和 ComfyUI…');
    try{
      const r=await fetch('/api/candidate-executor/activate',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});
      const d=await r.json().catch(()=>({}));
      if(!r.ok) throw new Error(d.error||d.detail||d.message||`HTTP ${r.status}`);
      const count=Number(d.image_assets||0);
      button.textContent='已启动 · 正在生成';
      toast(`已启动真实 Wan 候选生成：${d.shot_count||0}个镜头，检测到${count}张可用图片。请保持页面打开。`);
      if(pollTimer) clearInterval(pollTimer); pollTimer=setInterval(statusPoll,2500); statusPoll();
    }catch(error){
      button.disabled=false; button.textContent='生成 / 补齐镜头候选';
      toast(`没有启动：${error.message}`,true);
    }
  }, true);
})();
'''


def _serve_monitor(handler):
    web_file = Path(__file__).resolve().parents[1] / "web" / "content-production-monitor.js"
    source = web_file.read_text(encoding="utf-8") + _BROWSER_APPEND
    payload = source.encode("utf-8")
    handler.send_response(200)
    handler.send_header("Content-Type", "application/javascript; charset=utf-8")
    handler.send_header("Content-Length", str(len(payload)))
    handler.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
    handler.send_header("Pragma", "no-cache")
    handler.end_headers()
    handler.wfile.write(payload)


def install():
    global _INSTALLED
    if _INSTALLED:
        return
    original_get = server.DashboardHandler.do_GET
    original_post = server.DashboardHandler.do_POST

    def do_get(handler):
        path = urlsplit(handler.path).path
        if path in _MONITOR_PATHS:
            try:
                _serve_monitor(handler)
            except OSError as error:
                handler._json_error(500, error)
            return
        return original_get(handler)

    def do_post(handler):
        path = urlsplit(handler.path).path
        if path != _ACTIVATE_PATH:
            return original_post(handler)
        if not _origin_allowed(handler):
            handler._json_error(403, "仅允许本机工作台启动候选生成")
            return
        try:
            handler._json_ok(_activate_latest_mission())
        except (OSError, ValueError, RuntimeError, TypeError, KeyError) as error:
            handler._json_error(409, error)

    server.DashboardHandler.do_GET = do_get
    server.DashboardHandler.do_POST = do_post
    server.DashboardHandler._kz_candidate_executor_activation = True
    _INSTALLED = True


install()
