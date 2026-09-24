(() => {
  'use strict';

  let factory = null;

  const text = node => String(node?.textContent || '').replace(/\s+/g, ' ').trim();
  const leafNodes = root => [...(root?.querySelectorAll?.('*') || [])].filter(node => !node.children.length);

  async function readFactory(){
    try{
      const response = await fetch('/api/content-factory', {cache:'no-store'});
      if(!response.ok) throw new Error(`HTTP ${response.status}`);
      factory = await response.json();
    }catch(error){
      factory = factory || null;
    }
    return factory;
  }

  function activeCampaignId(data){
    return String(data?.active_campaign_id || data?.action_center?.active_campaign_id || data?.campaigns?.[0]?.id || '').trim();
  }

  function foregroundVideo(data){
    const currentId = String(data?.action_center?.current_video_id || '').trim();
    const videos = Array.isArray(data?.videos) ? data.videos : [];
    if(currentId){
      const exact = videos.find(item => item?.id === currentId);
      if(exact) return exact;
    }
    const campaignId = activeCampaignId(data);
    const scoped = videos.filter(item => !campaignId || item?.campaign_id === campaignId);
    const stamp = item => String(item?.runtime_updated_at || item?.plan_received_at || item?.requested_at || item?.created_at || '');
    return scoped.sort((a,b) => stamp(b).localeCompare(stamp(a)))[0] || null;
  }

  function maturityScore(data){
    const campaignId = activeCampaignId(data);
    const video = foregroundVideo(data);
    let score = 3.0;
    if(campaignId) score += 1.5;
    if(video?.production_plan) score += 1.0;
    const candidate = [...(video?.candidates || [])].reverse().find(item => item?.exists);
    const technicalPassed = Boolean((candidate?.technical_qc || video?.technical_qc || {}).passed);
    if(candidate && technicalPassed) score += 1.2;
    if(video?.local_qc?.decision === 'pass' || video?.local_qc?.status === 'passed') score += 1.1;
    if(['已授权发布','等待账号','等待最佳时间','发布执行中','已验证发布','已发布'].includes(String(video?.status || ''))) score += 0.5;
    const verifiedAccount = (data?.accounts || []).some(item => item?.connection_status === '已验证可发布');
    if(verifiedAccount) score += 0.5;
    if(Number(data?.verified_publications || 0) > 0) score += 0.7;
    const conversion = data?.conversion_summary || {};
    if([conversion.consultations, conversion.mini_program_requests, conversion.completed_orders].some(value => value !== null && value !== undefined)) score += 0.3;
    return Math.min(10, Math.round(score * 10) / 10);
  }

  function currentBlocker(data){
    const campaignId = activeCampaignId(data);
    const video = foregroundVideo(data);
    if(!campaignId) return '第1步 下达一个真实经营目标并建立 Mission';
    if(!video) return '第2步 为当前 Mission 建立第一条内容生产任务';
    if(video.status === '异常待处理') return `当前生产异常：${video.bottleneck || '需要查看待我处理中的真实异常'}`;
    if(video.status === '等待人工审核') return '第3步 老板审核 FINAL.MP4；审核通过后只进入发布队列，不代表已发布';
    if(['已授权发布','等待账号'].includes(video.status)){
      const verified = (data?.accounts || []).some(item => item?.connection_status === '已验证可发布');
      return verified ? '第4步 执行首个真实渠道发布并取得平台 URL / Post ID / Receipt' : '第4步 接入并验证首个真实发布渠道账号';
    }
    if(['等待最佳时间','发布执行中'].includes(video.status)) return '第4步 等待真实平台执行回执；没有 URL / Post ID / Receipt 不算发布成功';
    if(Number(data?.verified_publications || 0) > 0) return '第5步 打通曝光 → 咨询 → 小程序访问 → 订单的真实归因';
    if(['等待生产','生产中','技术质检','等待ChatGPT质检'].includes(video.status)) return `第2步 内容生产正在执行：${video.status}`;
    return `当前阶段：${video.status || '自动处理中'}；按 Mission 继续推进下一真实关口`;
  }

  function missionStage(data){
    const video = foregroundVideo(data);
    if(!video) return '等待执行计划';
    if(video.status === '等待人工审核') return '成片审核';
    if(video.status === '异常待处理') return '异常待处理';
    if(['已授权发布','等待账号','等待最佳时间','发布执行中'].includes(video.status)) return '真实渠道执行';
    if(['已验证发布','已发布'].includes(video.status)) return '结果回流';
    if(['等待生产','生产中','技术质检','等待ChatGPT质检'].includes(video.status)) return '内容生产';
    return video.status || '自动处理中';
  }

  function patchBossTruth(data){
    const dashboard = document.getElementById('dashboard');
    if(!dashboard) return;
    const score = maturityScore(data).toFixed(1);
    const blocker = currentBlocker(data);
    leafNodes(dashboard).forEach(node => {
      const value = text(node);
      if(/闭环得分\s*[\d.]+\s*\/\s*10/.test(value) || /自治闭环成熟度\s*[\d.]+\s*\/\s*10/.test(value)){
        node.textContent = `自治闭环成熟度 ${score}/10`;
      }
      if(value.startsWith('当前首要阻塞')){
        node.textContent = `当前首要阻塞：${blocker}`;
      }
    });
  }

  function patchDecisionTruth(data){
    const page = document.getElementById('workflow');
    if(!page) return;
    leafNodes(page).forEach(node => {
      const value = text(node);
      if(value === '今日要求完成度' || value === '今日要求完成') node.textContent = '今日例行任务完成度';
      if(/^\d+\s*\/\s*\d+\s*·\s*\d+%$/.test(value)) node.textContent = `今日例行任务完成度 ${value}`;
    });
    let note = document.getElementById('r810-current-mission-progress');
    if(!note){
      note = document.createElement('div');
      note.id = 'r810-current-mission-progress';
      note.className = 'r810-ai-readout';
      note.style.margin = '10px 0 14px';
      const anchor = page.querySelector('.r810-subtabs') || page.querySelector('.page-title');
      anchor?.insertAdjacentElement('afterend', note);
    }
    const video = foregroundVideo(data);
    note.innerHTML = `<b>当前 Mission：</b>${missionStage(data)}${video?.id ? ` · ${video.id}` : ''}。与下方“今日例行任务完成度”分开统计；例行任务 100% 不代表当前 Mission 已完成。`;
  }

  function countFromItem(items, id){
    const item = items.find(entry => String(entry?.id || '') === id);
    if(!item) return 0;
    const match = String(item.title || '').match(/(\d+)/);
    return match ? Number(match[1]) : 1;
  }

  function patchAttentionTruth(data){
    const items = Array.isArray(data?.action_center?.human_items) ? data.action_center.human_items : [];
    const count = items.length;
    const set = (id,value) => { const node=document.getElementById(id); if(node) node.textContent=String(value); };
    set('r810-human-total', count);
    set('r810-video-review', countFromItem(items,'final_review'));
    set('r810-login-human', countFromItem(items,'account_human'));
    set('r810-hard-errors', countFromItem(items,'production_exception'));
    const badge = document.getElementById('r810-attention-badge');
    if(badge){ badge.textContent=String(count); badge.hidden=!count; }
    const top = document.getElementById('r810-human-state');
    if(top) top.textContent=`待我处理：${count}`;

    // Older product layers may still render their own owner badge. Keep every
    // owner-facing badge bound to the same current-Mission action_center truth.
    leafNodes(document).forEach(node => {
      const value = text(node);
      if(/^待我处理\s*[:：]?\s*\d+$/.test(value)) node.textContent = `待我处理：${count}`;
      else if(/^待处理\s*\d+$/.test(value)) node.textContent = `待处理 ${count}`;
    });
  }

  function patchReviewLabels(root){
    if(!root) return;
    leafNodes(root).forEach(node => {
      const value = text(node);
      if(value === '通过并发布' || value === '确认发布'){
        node.textContent = '审核通过，进入发布队列';
        if(node.tagName === 'BUTTON') node.title = '仅授权进入发布队列；没有真实平台 URL / Post ID / Receipt 不算发布成功';
      }else if(value.includes('通过并发布')){
        node.textContent = value.replaceAll('通过并发布','审核通过进入发布队列');
      }
    });
  }

  function patchEmbeddedExecution(){
    const frame = document.getElementById('operational-frame');
    if(frame && !frame.dataset.r810TruthListener){
      frame.dataset.r810TruthListener = '1';
      frame.addEventListener('load', () => {
        try{ patchReviewLabels(frame.contentDocument); }catch(error){}
      });
    }
    try{
      const doc = frame?.contentDocument;
      if(doc) patchReviewLabels(doc);
    }catch(error){
      // Same-origin execution frame is expected; if unavailable, parent truth still remains correct.
    }
  }

  async function converge(){
    const data = await readFactory();
    if(!data) return;
    patchBossTruth(data);
    patchDecisionTruth(data);
    patchAttentionTruth(data);
    patchReviewLabels(document);
    patchEmbeddedExecution();
  }

  const observer = new MutationObserver(() => {
    clearTimeout(observer._timer);
    observer._timer = setTimeout(() => converge().catch(()=>{}), 120);
  });
  if(document.documentElement) observer.observe(document.documentElement,{childList:true,subtree:true,characterData:true});
  window.addEventListener('focus',()=>converge().catch(()=>{}));
  window.addEventListener('operational:refreshed',()=>setTimeout(()=>converge().catch(()=>{}),80));
  setInterval(()=>converge().catch(()=>{}),15000);
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',()=>setTimeout(()=>converge().catch(()=>{}),0),{once:true});
  else setTimeout(()=>converge().catch(()=>{}),0);
})();
