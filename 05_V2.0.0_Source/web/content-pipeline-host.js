(() => {
  'use strict';
  if (window.__KZ_CONTENT_PIPELINE_HOST__) return;
  window.__KZ_CONTENT_PIPELINE_HOST__ = true;

  const FRAME_ID = 'content-studio-frame';
  let timer = null;
  let attempts = 0;

  function ensureScript(doc, selector, src, datasetKey, errorText) {
    if (doc.querySelector(selector)) return true;
    const script = doc.createElement('script');
    script.src = src;
    script.async = false;
    script.dataset[datasetKey] = '1';
    script.onerror = () => {
      try { window.toast?.(errorText, 'error'); } catch (_) {}
    };
    (doc.body || doc.documentElement).appendChild(script);
    return true;
  }

  function inject(frame) {
    if (!frame) return false;
    let doc;
    try { doc = frame.contentDocument; } catch (_) { return false; }
    if (!doc || !doc.documentElement) return false;
    const pipelineReady = ensureScript(
      doc,
      'script[data-kz-content-pipeline-v11]',
      '/content-pipeline-v11.js',
      'kzContentPipelineV11',
      '内容创导 V1.1 闭环模块加载失败，请重新安装最新版本'
    );
    const finalReady = ensureScript(
      doc,
      'script[data-kz-final-output-71]',
      '/content-final-output.js',
      'kzFinalOutput71',
      '#71 最终成片模块加载失败，请重新安装最新版本'
    );
    return pipelineReady && finalReady;
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
