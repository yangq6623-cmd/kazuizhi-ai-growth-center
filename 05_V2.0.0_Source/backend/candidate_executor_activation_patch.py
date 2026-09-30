"""Activate real Wan candidate generation from both production controls.

Owner-facing contract: one click must resume unfinished candidates and, when the
local ComfyUI service is installed but not running, start it automatically. The
owner must not have to open ComfyUI manually for normal production.
"""
from __future__ import annotations

import subprocess
import threading
import time
from pathlib import Path
from urllib.parse import urlsplit

from backend import ai_gateway_patch as _ai
from backend import kz_local_control_patch as _video
from backend import production_mission_patch as _mission
from backend import quality_ai_runtime_patch as _quality
from backend import server
from promotion import ai_production_center as _center

_INSTALLED = False
_ACTIVATE_PATH = "/api/candidate-executor/activate"
_SCRIPT_FILES = {
    "/content-production-monitor.js": "content-production-monitor.js",
    "/web/content-production-monitor.js": "content-production-monitor.js",
    "/content-studio-simple.js": "content-studio-simple.js",
    "/web/content-studio-simple.js": "content-studio-simple.js",
}
_COMFY_START_LOCK = threading.Lock()


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


def _spawn_comfyui(root: Path):
    portable = root.parent
    launcher = portable / "run_nvidia_gpu.bat"
    flags = int(getattr(subprocess, "CREATE_NO_WINDOW", 0))
    common = {
        "cwd": str(portable),
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "creationflags": flags,
    }
    if launcher.is_file():
        subprocess.Popen(["cmd.exe", "/c", str(launcher)], **common)
        return str(launcher)

    python_exe = portable / "python_embeded" / "python.exe"
    main_py = root / "main.py"
    if python_exe.is_file() and main_py.is_file():
        subprocess.Popen([
            str(python_exe), "-s", str(main_py),
            "--windows-standalone-build", "--listen", "127.0.0.1", "--port", "8188",
        ], **common)
        return str(python_exe)

    raise RuntimeError(
        "已找到 ComfyUI 模型目录，但没有找到 run_nvidia_gpu.bat 或 python_embeded\\python.exe，无法自动启动 ComfyUI。"
    )


def _ensure_comfyui_ready():
    """Return a ready ComfyUI snapshot, auto-starting the local portable service."""
    with _COMFY_START_LOCK:
        status = _quality._comfyui_ready()
        if status.get("ok"):
            status["autostarted"] = False
            return status

        root = _quality._comfyui_root()
        if not root:
            raise RuntimeError(
                "没有找到本机 ComfyUI 安装目录。应存在 F:\\KazuizhiAI\\ComfyUI_windows_portable\\ComfyUI。"
            )
        model = root / "models" / "diffusion_models" / "wan2.1_i2v_480p_14B_fp8_scaled.safetensors"
        if not model.is_file():
            raise RuntimeError(
                "ComfyUI 已安装，但缺少 Wan2.1 I2V FP8 模型：wan2.1_i2v_480p_14B_fp8_scaled.safetensors。"
            )

        # Installation and model are present. If only port 8188 is down, normal
        # production should launch the portable service automatically.
        launcher = _spawn_comfyui(root)
        deadline = time.monotonic() + 90.0
        while time.monotonic() < deadline:
            time.sleep(1.0)
            status = _quality._comfyui_ready()
            if status.get("ok"):
                status["autostarted"] = True
                status["launcher"] = launcher
                status["message"] = "ComfyUI 已由平台自动启动，Wan2.1 FP8 已就绪"
                return status

        latest = _quality._comfyui_ready()
        raise RuntimeError(
            "平台已尝试自动启动 ComfyUI，但 90 秒内 8188 仍未就绪。"
            f" 安装目录：{latest.get('root') or str(root)}；Wan FP8：{'已找到' if latest.get('wan_i2v_fp8') else '未找到'}。"
        )


def _activate_latest_mission():
    project, shots = _latest_project_and_shots()
    _mission._sync_project(project, shots)
    data = _mission._load()
    current = _mission._mission_for_project(data, project.get("id"))
    if not current:
        raise RuntimeError("内容生产任务没有正确建立")

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
        "detail": "一键生成/补齐候选已激活当前项目真实 ComfyUI 执行器。",
    })
    _mission._save(data)

    images = _video._recent_image_assets()
    if not images:
        raise ValueError("当前没有可用图片素材。受控测试请先上传至少1张图片。")

    comfy = _ensure_comfyui_ready()
    _video._start_comfy_worker()
    snapshot = _video._executor_snapshot()
    summary = _mission.current_mission().get("mission") or {}
    return {
        "ok": True,
        "message": "真实候选执行器已启动",
        "project_id": project.get("id"),
        "director_plan_id": project.get("director_plan_id") or "",
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

  async function json(url, options={}) {
    const r=await fetch(url, options);
    const d=await r.json().catch(()=>({}));
    if(!r.ok) throw new Error(d.error||d.detail||d.message||`HTTP ${r.status}`);
    return d;
  }
  function toast(text, bad=false) {
    let node=document.getElementById('kz-candidate-activation-toast');
    if(!node){
      node=document.createElement('div'); node.id='kz-candidate-activation-toast';
      node.style.cssText='position:fixed;right:22px;bottom:22px;z-index:10050;max-width:460px;padding:11px 14px;border-radius:8px;background:#17324f;color:#fff;font:12px/1.5 sans-serif;box-shadow:0 8px 26px rgba(0,0,0,.18)';
      document.body.appendChild(node);
    }
    node.style.background=bad?'#b43b3b':'#17324f'; node.textContent=text; node.hidden=false;
  }
  function inline(text, bad=false) {
    const node=document.getElementById('kz-simple-result');
    if(!node) return;
    node.className=`kz-simple-result ${bad?'kz-simple-error':'kz-simple-success'}`;
    node.innerHTML=text;
  }
  async function statusPoll(){
    try{
      const d=await json('/api/comfyui-executor/status',{cache:'no-store'});
      const state=d?.status||d?.executor?.status||'';
      const msg=d?.message||d?.executor?.message||'';
      const err=d?.last_error||d?.executor?.last_error||'';
      if(err){
        toast(`ComfyUI执行异常：${err}`,true);
        inline(`<b>视频生成没有完成：</b>${String(err).replace(/[&<>]/g,'')}`,true);
        clearInterval(pollTimer); pollTimer=null; return;
      }
      if(state==='running') toast(msg||'ComfyUI正在真实生成镜头候选…');
      if(state==='waiting'||state==='waiting_retry') toast(msg||'执行器正在等待可继续条件…');
      if(state==='completed'){
        toast(msg||'本轮候选执行已完成。');
        clearInterval(pollTimer); pollTimer=null;
      }
    }catch(_){ }
  }
  function beginPoll(){
    if(pollTimer) clearInterval(pollTimer);
    setTimeout(statusPoll,1800);
    pollTimer=setInterval(statusPoll,2500);
  }
  async function activate(button, mainButton=false) {
    const oldText=button.textContent;
    button.disabled=true;
    button.textContent=mainButton?'正在启动本地视频引擎…':'正在启动本地视频引擎…';
    toast('正在恢复当前任务；如 ComfyUI 未运行，平台会自动启动，然后加载 Wan2.1…');
    if(mainButton) inline('<b>正在继续当前项目：</b>恢复未完成镜头，并自动启动本地 ComfyUI / Wan 视频引擎。');
    try{
      const d=await json('/api/candidate-executor/activate',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});
      button.textContent=mainButton?'已启动 · 正在生成视频':'已启动 · 正在生成';
      const auto=d?.comfyui?.autostarted?'；ComfyUI 已自动启动':'';
      const text=`已启动真实 Wan 候选生成：${d.shot_count||0}个镜头，${d.image_assets||0}张可用图片${auto}。`;
      toast(text);
      if(mainButton) inline(`<b>视频生成已启动。</b>${d.shot_count||0} 个镜头已进入本地 ComfyUI / Wan2.1 串行生成；下面会显示真实候选文件。`);
      beginPoll();
      return d;
    }catch(error){
      button.disabled=false; button.textContent=oldText;
      toast(`没有启动：${error.message}`,true);
      if(mainButton) inline(`<b>视频执行器没有启动：</b>${String(error.message||error).replace(/[&<>]/g,'')}`,true);
      throw error;
    }
  }
  async function pendingCurrentProject(){
    const center=await json('/api/ai-content-center',{cache:'no-store'});
    const project=(center.projects||[])[0];
    if(!project) return null;
    const pid=String(project.id||'');
    const shots=(center.storyboards||[]).filter(x=>String(x.project_id||'')===pid);
    if(!shots.length) return null;
    const planned=shots.reduce((n,x)=>n+Math.max(1,Number(x.candidate_count||1)),0);
    const generated=(center.outputs||[]).filter(x=>String(x.project_id||'')===pid && (x.candidate_key||/候选/.test(String(x.kind||x.type||'')))).length;
    if(generated>=planned) return null;
    let pipeline={};
    try{pipeline=JSON.parse(localStorage.getItem('kazuizhi.content-pipeline.v1')||'{}')||{}}catch(_){ }
    const planId=String(pipeline?.directorPlan?.id||'');
    const samePlan=!!planId && String(project.director_plan_id||'')===planId;
    const monitorWaiting=!!document.querySelector('#kz-production-monitor .kz-candidate:not(.ready)');
    return (samePlan||monitorWaiting) ? {project,shots,planned,generated} : null;
  }

  document.addEventListener('click', async event => {
    const button=event.target.closest?.('#kz-queue-all');
    if(!button) return;
    event.preventDefault(); event.stopPropagation(); event.stopImmediatePropagation();
    try{await activate(button,false);}catch(_){ }
  }, true);

  document.addEventListener('click', async event => {
    const button=event.target.closest?.('#kz-simple-start');
    if(!button) return;
    if(button.dataset.kzOneClickBypass==='1'){
      delete button.dataset.kzOneClickBypass;
      return;
    }
    event.preventDefault(); event.stopPropagation(); event.stopImmediatePropagation();
    const original=button.textContent;
    button.disabled=true; button.textContent='正在检查当前生产任务…';
    try{
      const pending=await pendingCurrentProject();
      if(!pending){
        button.disabled=false; button.textContent=original;
        button.dataset.kzOneClickBypass='1';
        button.click();
        return;
      }
      inline(`<b>检测到未完成的当前项目：</b>${pending.generated}/${pending.planned} 个真实候选已生成。现在直接继续视频生成，不重复做前面的 AI 分析。`);
      await activate(button,true);
    }catch(error){
      button.disabled=false; button.textContent=original;
      toast(`一键生成未启动：${error.message}`,true);
      inline(`<b>一键生成未启动：</b>${String(error.message||error).replace(/[&<>]/g,'')}`,true);
    }
  }, true);
})();
'''


def _serve_script(handler, path):
    filename = _SCRIPT_FILES[path]
    web_file = Path(__file__).resolve().parents[1] / "web" / filename
    source = web_file.read_text(encoding="utf-8")
    if filename == "content-studio-simple.js":
        source = _ai._rewrite_browser_script(source)
    source += _BROWSER_APPEND
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
        if path in _SCRIPT_FILES:
            try:
                _serve_script(handler, path)
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
        except (OSError, ValueError, RuntimeError, TypeError, KeyError, subprocess.SubprocessError) as error:
            handler._json_error(409, error)

    server.DashboardHandler.do_GET = do_get
    server.DashboardHandler.do_POST = do_post
    server.DashboardHandler._kz_candidate_executor_activation = True
    _INSTALLED = True


install()
