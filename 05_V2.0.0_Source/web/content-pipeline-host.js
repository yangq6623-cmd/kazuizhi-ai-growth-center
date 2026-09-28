(() => {
  'use strict';
  if (window.__KZ_CONTENT_PIPELINE_HOST__) return;
  window.__KZ_CONTENT_PIPELINE_HOST__ = true;

  const FRAME_ID = 'content-studio-frame';
  let timer = null;
  let attempts = 0;

  function inject(frame) {
    if (!frame) return false;
    let doc;
    try { doc = frame.contentDocument; } catch (_) { return false; }
    if (!doc || !doc.documentElement) return false;
    if (doc.querySelector('script[data-kz-content-pipeline-v11]')) return true;
    const script = doc.createElement('script');
    script.src = '/content-pipeline-v11.js';
    script.async = false;
    script.dataset.kzContentPipelineV11 = '1';
    script.onerror = () => {
      try { window.toast?.('内容创导 V1.1 闭环模块加载失败，请重新安装最新版本', 'error'); } catch (_) {}
    };
    (doc.body || doc.documentElement).appendChild(script);
    return true;
  }

  function ensure() {
    const frame = document.getElementById(FRAME_ID);
    if (frame) {
      if (!frame.dataset.kzPipelineHostBound) {
        frame.dataset.kzPipelineHostBound = '1';
        frame.addEventListener('load', () => setTimeout(() => inject(frame), 30));
      }
      if (inject(frame)) return true;
    }
    return false;
  }

  function converge() {
    clearTimeout(timer);
    if (ensure()) return;
    attempts += 1;
    if (attempts < 80) timer = setTimeout(converge, 120);
  }

  document.addEventListener('r810:workbench-ready', () => { attempts = 0; converge(); });
  window.addEventListener('kz:app-ready', () => { attempts = 0; converge(); });
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', converge, {once:true});
  else converge();
  setTimeout(converge, 500);
  setTimeout(converge, 1600);
})();
