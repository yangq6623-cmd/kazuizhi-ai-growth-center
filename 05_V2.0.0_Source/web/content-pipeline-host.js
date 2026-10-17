(() => {
  'use strict';
  if (window.__KZ_CONTENT_PIPELINE_HOST_STABLE__) return;
  window.__KZ_CONTENT_PIPELINE_HOST_STABLE__ = true;

  const FRAME_ID = 'content-studio-frame';
  let timer = null;
  let attempts = 0;

  function ensureScript(doc, selector, src, datasetKey, errorText) {
    if (!doc?.body || doc.querySelector(selector)) return true;
    const script = doc.createElement('script');
    script.src = src;
    script.async = false;
    script.dataset[datasetKey] = '1';
    script.onerror = () => {
      try { window.toast?.(errorText, 'error'); } catch (_) {}
    };
    doc.body.appendChild(script);
    return true;
  }

  function inject(frame) {
    if (!frame) return false;
    let doc;
    try { doc = frame.contentDocument; } catch (_) { return false; }
    if (!doc?.body || doc.readyState !== 'complete') return false;
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
      '最终成片模块加载失败，请重新安装最新版本'
    );
    if (pipelineReady && finalReady) {
      document.documentElement.dataset.kzContentPipelineHost = 'ready';
      return true;
    }
    return false;
  }

  function bindFrame(frame) {
    if (!frame || frame.dataset.kzPipelineHostBound === '1') return;
    frame.dataset.kzPipelineHostBound = '1';
    frame.addEventListener('load', () => {
      window.setTimeout(() => inject(frame), 160);
    });
  }

  function ensure() {
    const frame = document.getElementById(FRAME_ID);
    if (!frame) return false;
    bindFrame(frame);
    if (frame.contentDocument?.readyState === 'complete') return inject(frame);
    return false;
  }

  function converge() {
    if (timer) window.clearTimeout(timer);
    if (ensure()) return;
    attempts += 1;
    if (attempts < 30) timer = window.setTimeout(converge, 200);
  }

  document.addEventListener('r810:workbench-ready', () => { attempts = 0; converge(); });
  window.addEventListener('kz:app-ready', () => { attempts = 0; converge(); });
  window.addEventListener('kz:lazy-workspace-ready', event => {
    if (event.detail?.name === 'content_studio') { attempts = 0; converge(); }
  });
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', converge, {once:true});
  else converge();
})();