"""Quality-first runtime policy for long local AI work on RTX 3060 12 GB.

This layer prefers completion quality and stability over latency. Browser model
traffic stays on the 8876 same-origin bridge, while the GPT director is free to
choose a dynamic shot count and dynamic per-shot candidate budget.

R8-18 #69 adds a simple platform-side local media intake. Images/videos are
uploaded from the owner UI, persisted outside the installation directory,
registered as real production assets, and image inputs are mirrored into the
local ComfyUI input directory when available. This establishes the correct
platform -> production -> ComfyUI handoff boundary without asking the owner to
manually copy normal production files into ComfyUI.
"""
from __future__ import annotations

import hashlib
import mimetypes
import re
import shutil
import socket
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

from backend import ai_gateway_patch as _ai
from core.storage import data_root
from promotion import ai_production_center as _center

# One local text step may legitimately run for many minutes on a 12 GB card.
# A complete Mission can contain many serialized steps and may run for hours.
_ai._LOCAL_AI_TIMEOUT_SECONDS = 30 * 60

# Structured director/reference JSON can exceed the old 1200-token ceiling and
# get cut in the middle of an object. Quality-first mode therefore gives local
# structured work more output room. Calls are still serialized and the model is
# released after each step, so video generation can reclaim the 12 GB card.
_ai._LOCAL_AI_MAX_TOKENS = 2600

# The native director pipeline is another browser-side model caller. Serve it
# through the same rewrite path so it never calls :17777 directly.
_ai._LOCAL_AI_BROWSER_SCRIPTS["/content-pipeline-native.js"] = "content-pipeline-native.js"

_original_rewrite_browser_script = _ai._rewrite_browser_script

_MEDIA_MAX_BYTES = 512 * 1024 * 1024
_MEDIA_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".mp4", ".webm", ".mov", ".m4v"}
_MEDIA_MIMES = {
    ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp",
    ".mp4": "video/mp4", ".webm": "video/webm", ".mov": "video/quicktime", ".m4v": "video/x-m4v",
}
_MEDIA_RIGHTS = {"本人或公司自有", "已取得授权", "虚拟资产"}


def _safe_filename(value: str) -> str:
    name = Path(unquote(str(value or "media"))).name
    stem = re.sub(r"[^0-9A-Za-z._\-\u4e00-\u9fff]+", "_", Path(name).stem).strip("._") or "media"
    ext = Path(name).suffix.lower()
    if ext not in _MEDIA_EXTS:
        raise ValueError("仅支持 JPG/PNG/WEBP 图片和 MP4/WEBM/MOV 视频")
    return f"{stem[:80]}{ext}"


def _comfyui_root():
    candidates = [
        Path(r"F:\KazuizhiAI\ComfyUI_windows_portable\ComfyUI"),
        Path(r"F:\ComfyUI_windows_portable\ComfyUI"), Path(r"F:\ComfyUI"),
        Path(r"E:\ComfyUI_windows_portable\ComfyUI"), Path(r"D:\ComfyUI_windows_portable\ComfyUI"),
    ]
    for path in candidates:
        if (path / "input").is_dir() and (path / "models").is_dir():
            return path
    return None


def _comfyui_ready():
    port = False
    try:
        with socket.create_connection(("127.0.0.1", 8188), timeout=0.5):
            port = True
    except OSError:
        pass
    root = _comfyui_root()
    model = None
    if root:
        candidate = root / "models" / "diffusion_models" / "wan2.1_i2v_480p_14B_fp8_scaled.safetensors"
        model = candidate if candidate.exists() else None
    return {
        "ok": bool(port and root and model), "port_8188": port,
        "root": str(root) if root else "", "wan_i2v_fp8": bool(model),
        "message": "ComfyUI 与 Wan2.1 FP8 已就绪" if port and root and model else "等待 ComfyUI / Wan2.1 FP8 就绪",
    }


def _asset_by_id(asset_id):
    data = _center._load()
    for asset in data.get("assets") or []:
        if asset.get("id") == asset_id:
            return asset
    return None


def _register_uploaded_asset(filename, saved_path, mime_type, size_bytes, sha256, rights):
    media_kind = "图片" if mime_type.startswith("image/") else "视频"
    asset = _center.add_asset({
        "name": filename, "asset_type": "真实素材", "rights": rights,
        "tags": f"本地上传,{media_kind},内容生产",
        "note": "通过简单模式素材投递入口上传；真实文件已保存在本机。",
    })
    data = _center._load()
    for item in data.get("assets") or []:
        if item.get("id") != asset.get("id"):
            continue
        item.update({
            "original_name": filename, "file_path": str(saved_path), "mime_type": mime_type,
            "size_bytes": int(size_bytes), "sha256": sha256,
            "uploaded_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "source_kind": "owner_local_upload", "media_kind": media_kind,
            "file_url": f"/api/local-media/file?id={asset.get('id')}",
        })
        comfy = _comfyui_root()
        if comfy and mime_type.startswith("image/"):
            target_name = f"kazuizhi_{asset.get('id')}{saved_path.suffix.lower()}"
            target = comfy / "input" / target_name
            try:
                shutil.copy2(saved_path, target)
                item["comfyui_filename"] = target_name
                item["comfyui_input_path"] = str(target)
                item["comfyui_synced"] = True
            except OSError as error:
                item["comfyui_synced"] = False
                item["comfyui_error"] = str(error)[:300]
        break
    _center._save(data)
    return _asset_by_id(asset.get("id")) or asset


def _handle_media_upload(handler):
    if not _ai._origin_allowed(handler):
        handler._json_error(403, "仅允许本机平台上传素材"); return
    try:
        length = int(handler.headers.get("Content-Length", "0") or 0)
    except ValueError:
        length = 0
    if length <= 0 or length > _MEDIA_MAX_BYTES:
        handler._json_error(413, "素材不能为空，单文件最大 512MB"); return
    tmp = None
    try:
        filename = _safe_filename(handler.headers.get("X-KZ-Filename") or "media")
        rights = unquote(handler.headers.get("X-KZ-Rights") or "本人或公司自有")
        if rights not in _MEDIA_RIGHTS:
            raise ValueError("素材授权状态不正确")
        ext = Path(filename).suffix.lower()
        expected = _MEDIA_MIMES.get(ext)
        incoming = str(handler.headers.get("Content-Type") or expected or "application/octet-stream").split(";", 1)[0]
        if not expected or not (incoming.startswith("image/") or incoming.startswith("video/")):
            raise ValueError("素材类型不支持")
        folder = data_root() / "r8" / "media_intake" / datetime.now().strftime("%Y%m")
        folder.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256()
        tmp = folder / f".upload-{datetime.now().strftime('%Y%m%d%H%M%S%f')}{ext}.part"
        remaining = length
        with tmp.open("wb") as stream:
            while remaining:
                chunk = handler.rfile.read(min(1024 * 1024, remaining))
                if not chunk:
                    raise ValueError("素材上传中断，请重新选择文件")
                stream.write(chunk); digest.update(chunk); remaining -= len(chunk)
        final = folder / f"{digest.hexdigest()[:16]}_{filename}"
        if final.exists():
            tmp.unlink(missing_ok=True)
        else:
            tmp.replace(final)
        asset = _register_uploaded_asset(filename, final, expected, length, digest.hexdigest(), rights)
        handler._json_ok({"ok": True, "asset": asset, "comfyui": _comfyui_ready()}, code=201)
    except (OSError, ValueError) as error:
        if tmp and tmp.exists():
            try: tmp.unlink()
            except OSError: pass
        handler._json_error(400, error)


def _serve_media_file(handler):
    query = parse_qs(urlsplit(handler.path).query)
    asset_id = (query.get("id") or [""])[0]
    asset = _asset_by_id(asset_id)
    path = Path(str((asset or {}).get("file_path") or ""))
    if not asset or not path.is_file():
        handler._json_error(404, "没有找到该本地素材"); return
    try:
        root = (data_root() / "r8" / "media_intake").resolve()
        resolved = path.resolve()
        if root not in resolved.parents:
            raise ValueError("素材路径不允许访问")
        data = resolved.read_bytes()
        mime_type = asset.get("mime_type") or mimetypes.guess_type(resolved.name)[0] or "application/octet-stream"
        handler.send_response(200); handler.send_header("Content-Type", mime_type)
        handler.send_header("Content-Length", str(len(data))); handler.end_headers(); handler.wfile.write(data)
    except (OSError, ValueError) as error:
        handler._json_error(400, error)


def _install_media_http_surface():
    handler_cls = _ai.server.DashboardHandler
    if getattr(handler_cls, "_kz_local_media_intake_patched", False): return
    original_get, original_post = handler_cls.do_GET, handler_cls.do_POST
    def do_get(self):
        path = urlsplit(self.path).path
        if path == "/api/local-media/status": self._json_ok({"ok": True, "comfyui": _comfyui_ready()}); return
        if path == "/api/local-media/file": _serve_media_file(self); return
        return original_get(self)
    def do_post(self):
        if urlsplit(self.path).path == "/api/local-media/upload": _handle_media_upload(self); return
        return original_post(self)
    handler_cls.do_GET, handler_cls.do_POST = do_get, do_post
    handler_cls._kz_local_media_intake_patched = True


def _media_intake_browser_patch() -> str:
    return r'''
;(() => {
  const STORE='kazuizhi.local-media-intake.v1';
  const read=()=>{try{return JSON.parse(localStorage.getItem(STORE)||'[]')}catch(_){return[]}};
  let items=read(); window.__KZ_LOCAL_MEDIA_ASSETS__=items;
  const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const save=()=>{localStorage.setItem(STORE,JSON.stringify(items.slice(-20)));window.__KZ_LOCAL_MEDIA_ASSETS__=items};
  function render(root){const list=root.querySelector('[data-kz-local-media-list]');if(!list)return;if(!items.length){list.innerHTML='<span class="kz-media-empty">还没有本地素材。可直接上传图片或视频；不上传也可以让 AI 自动生产。</span>';return}list.innerHTML=items.map((x,i)=>`<article class="kz-media-chip">${String(x.mime_type||'').startsWith('image/')?`<img src="${esc(x.file_url||'')}" alt="">`:'<b>视频</b>'}<div><strong>${esc(x.original_name||x.name||'本地素材')}</strong><small>${esc(x.comfyui_synced?'已保存并同步 ComfyUI':'已保存到本机')}</small></div><button type="button" data-kz-media-remove="${i}">×</button></article>`).join('');list.querySelectorAll('[data-kz-media-remove]').forEach(btn=>btn.onclick=()=>{items.splice(Number(btn.dataset.kzMediaRemove),1);save();render(root)})}
  async function upload(file,rights,status){status.textContent=`正在保存：${file.name}`;const r=await fetch('/api/local-media/upload',{method:'POST',headers:{'Content-Type':file.type||'application/octet-stream','X-KZ-Filename':encodeURIComponent(file.name),'X-KZ-Rights':encodeURIComponent(rights)},body:file});const data=await r.json().catch(()=>({}));if(!r.ok)throw new Error(data.error||'素材上传失败');items.push(data.asset);save();return data}
  function install(){const source=document.getElementById('kz-simple-source');if(!source||document.getElementById('kz-local-media-intake'))return false;const host=source.closest('label')||source.parentElement;if(!host)return false;const box=document.createElement('section');box.id='kz-local-media-intake';box.className='kz-local-media-intake';box.innerHTML=`<div class="kz-media-head"><div><b>添加本地素材 <em>可选</em></b><span>图片/视频从这里交给后台；GPT 决定哪些镜头使用。</span></div><label>素材权限<select data-kz-media-rights><option>本人或公司自有</option><option>已取得授权</option><option>虚拟资产</option></select></label></div><div class="kz-media-actions"><button type="button" data-kz-media-pick>＋ 上传图片 / 视频</button><input data-kz-media-input type="file" accept="image/jpeg,image/png,image/webp,video/mp4,video/webm,video/quicktime" multiple hidden><span data-kz-media-status>等待添加素材</span></div><div class="kz-media-list" data-kz-local-media-list></div>`;host.insertAdjacentElement('afterend',box);if(!document.getElementById('kz-local-media-style')){const s=document.createElement('style');s.id='kz-local-media-style';s.textContent=`.kz-local-media-intake{border:1px solid #dbe7f6;border-radius:10px;padding:12px;margin:10px 0;background:#f8fbff}.kz-media-head{display:flex;justify-content:space-between;gap:12px;align-items:center}.kz-media-head b{display:block}.kz-media-head em{font-style:normal;color:#6b7d93;font-weight:400}.kz-media-head span{font-size:12px;color:#718096}.kz-media-head label{font-size:12px}.kz-media-head select{margin-left:6px;padding:5px}.kz-media-actions{display:flex;align-items:center;gap:10px;margin-top:10px}.kz-media-actions button{background:#1769e0;color:#fff;border:0;border-radius:7px;padding:8px 13px;cursor:pointer}.kz-media-actions span{font-size:12px;color:#66758a}.kz-media-list{display:flex;gap:8px;flex-wrap:wrap;margin-top:10px}.kz-media-empty{font-size:12px;color:#7b8798}.kz-media-chip{display:flex;align-items:center;gap:8px;border:1px solid #dbe3ee;border-radius:8px;padding:6px;background:#fff;max-width:260px}.kz-media-chip img{width:44px;height:44px;object-fit:cover;border-radius:5px}.kz-media-chip div{min-width:0}.kz-media-chip strong,.kz-media-chip small{display:block;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.kz-media-chip strong{font-size:12px}.kz-media-chip small{font-size:11px;color:#728096}.kz-media-chip button{border:0;background:transparent;cursor:pointer;font-size:16px}`;document.head.appendChild(s)}const input=box.querySelector('[data-kz-media-input]'),status=box.querySelector('[data-kz-media-status]');box.querySelector('[data-kz-media-pick]').onclick=()=>input.click();input.onchange=async()=>{try{for(const file of [...input.files]){const data=await upload(file,box.querySelector('[data-kz-media-rights]').value,status);status.textContent=data.comfyui?.ok?'上传成功 · ComfyUI 已就绪':'上传成功 · 已保存到本机'}render(box)}catch(e){status.textContent=`上传失败：${e.message}`}finally{input.value=''}};render(box);return true}
  if(!install()){let n=0;const t=setInterval(()=>{if(install()||++n>80)clearInterval(t)},250)}
})();
'''


def _quality_rewrite_browser_script(source: str) -> str:
    rewritten = _original_rewrite_browser_script(source)
    rewritten = rewritten.replace("},180000,400);\n      showAnalysis(analyzed);", "},1860000,400);\n      showAnalysis(analyzed);")
    rewritten = rewritten.replace("首次调用本地模型可能需要 1–2 分钟，请保持页面打开。", "本地 AI 正在按质量优先模式处理；单个文本步骤最长允许约 30 分钟，请保持页面打开。")
    rewritten = rewritten.replace("const timeout = setTimeout(() => controller.abort(), 35000);", "const timeout = setTimeout(() => controller.abort(), 1860000);")
    rewritten = rewritten.replace("temperature:.35})", "temperature:.2,max_tokens:2400})")
    if "function analysisPrompt(item)" in rewritten and "parseReferenceJsonWithRetry" not in rewritten:
        rewritten = rewritten.replace("  function analysisPrompt(item){", """  function parseReferenceJson(text=''){
    const cleaned=stripJsonFence(text);
    try{return JSON.parse(cleaned);}catch(firstError){
      const start=cleaned.indexOf('{'),end=cleaned.lastIndexOf('}');
      if(start>=0&&end>start)return JSON.parse(cleaned.slice(start,end+1));
      throw firstError;
    }
  }
  async function parseReferenceJsonWithRetry(raw,item){
    try{return parseReferenceJson(raw);}catch(firstError){
      const compactPrompt=analysisPrompt(item)+`\n\n重要：上一次结构化输出没有完整闭合。请重新输出一个更精简但字段完整的 JSON。不要解释，不要 Markdown。structure 保留 5 个阶段；style_dna、learnable、must_recreate、do_not_use 每项最多 3 条且每条尽量 24 字以内；kazuizhi_versions 保留 3 个版本，每个字段简洁。必须输出完整闭合的 JSON 对象。`;
      const retryRaw=await callRouter(compactPrompt);
      try{return parseReferenceJson(retryRaw);}catch(secondError){throw new Error('AI 返回的结构化分析不完整，系统已自动重试一次；已完成任务不会丢失，请稍后直接重试本步骤。');}
    }
  }
  function analysisPrompt(item){""")
        rewritten = rewritten.replace("const raw=await callRouter(analysisPrompt(item)),parsed=JSON.parse(stripJsonFence(raw));", "const raw=await callRouter(analysisPrompt(item)),parsed=await parseReferenceJsonWithRetry(raw,item);")
    rewritten = rewritten.replace("reference_id:state.reference?.id||'',creative_id:creative?.id||''", "reference_id:state.reference?.id||'',source_title:state.reference?.title||'',source_url:state.reference?.source||'',creative_id:creative?.id||''")
    rewritten = rewritten.replace("const assets=[choices.character.id,choices.scene.id,choices.voice.id].filter(Boolean);", "const assets=[choices.character.id,choices.scene.id,choices.voice.id,...(window.__KZ_LOCAL_MEDIA_ASSETS__||[]).map(x=>x.id)].filter(Boolean);")
    if "window.__KZ_CONTENT_STUDIO_SIMPLE__" in rewritten and "data-kz-production-monitor-loader" not in rewritten:
        rewritten += """
\n;(() => {
  if (!document.querySelector('script[data-kz-production-monitor-loader]')) { const monitor=document.createElement('script'); monitor.src='content-production-monitor.js'; monitor.async=false; monitor.dataset.kzProductionMonitorLoader='1'; document.body.appendChild(monitor); }
  if (!document.querySelector('script[data-kz-mission-card-loader]')) { const mission=document.createElement('script'); mission.src='content-mission-card.js'; mission.async=false; mission.dataset.kzMissionCardLoader='1'; document.body.appendChild(mission); }
})();
"""
    if "window.__KZ_CONTENT_STUDIO_SIMPLE__" in rewritten and "kz-local-media-intake" not in rewritten:
        rewritten += _media_intake_browser_patch()
    return rewritten


_ai._rewrite_browser_script = _quality_rewrite_browser_script
_install_media_http_surface()
_ai.server.DashboardHandler._kz_quality_first_local_ai = True

from backend import dynamic_director_policy_patch as _dynamic_director_policy_patch  # noqa: E402,F401
from backend import production_runtime_monitor_patch as _production_runtime_monitor_patch  # noqa: E402,F401
from backend import production_mission_patch as _production_mission_patch  # noqa: E402,F401
