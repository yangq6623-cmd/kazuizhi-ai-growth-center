let keywordData=[];let promotionRecords=[];let lastPromotionText='';let currentPromotionRecord=null;
const SOURCE_LABELS={historical_public_signal:'公开研究词',owner_input:'手动添加',product_strategy_seed:'产品方向词'};
const FIELD_LABELS={title:'标题',meta_description:'页面简介',outline:'内容提纲',draft:'正文草稿',review_notes:'发布前检查',landing_page:'本地页面方案',local_profile:'本地资料检查',faq:'常见问题',measurement:'效果记录方法',audience:'目标用户',evidence_used:'使用的证据',positioning:'品牌表达',variants:'文案方案',safety_check:'安全检查',duration:'建议时长',hook:'开场',shots:'分镜脚本',caption:'配文',cta:'行动提示'};
function promotionPayload(){return{region:$('promo-region').value.trim(),service:$('promo-service').value.trim(),keyword:$('promo-keyword').value.trim(),audience:$('promo-audience').value.trim(),evidence:$('promo-evidence').value.trim()}}
function renderValue(value){if(Array.isArray(value))return`<div class="result-list">${value.map((item,i)=>typeof item==='object'?`<div class="result-step"><b>${i+1}</b><div>${renderValue(item)}</div></div>`:`<div class="result-step"><b>${i+1}</b><span>${esc(item)}</span></div>`).join('')}</div>`;if(value&&typeof value==='object')return Object.entries(value).map(([key,item])=>`<div class="result-field"><strong>${esc(FIELD_LABELS[key]||key)}</strong>${renderValue(item)}</div>`).join('');return`<p>${esc(value)}</p>`}
function showPromotion(record){currentPromotionRecord=record;$('promotion-output-title').textContent=record.kind+'（待人工审核）';$('promotion-output').className='promotion-output';$('promotion-output').innerHTML=renderValue(record.output);lastPromotionText=Object.entries(record.output).map(([k,v])=>`${FIELD_LABELS[k]||k}\n${typeof v==='string'?v:JSON.stringify(v,null,2)}`).join('\n\n');$('copy-promotion').disabled=false;const submit=$('promotion-submit-r8');if(submit)submit.disabled=false}
function filterKeywords(){const query=$('keyword-search').value.trim().toLowerCase();const source=$('keyword-source').value;const items=keywordData.filter(x=>(source==='all'||x.source===source)&&(!query||x.keyword.toLowerCase().includes(query)||String(x.region||'').includes(query)||String(x.category||'').includes(query)));$('keyword-count').textContent=`${items.length} 条`;$('keyword-list').className=items.length?'keyword-list':'friendly-empty';$('keyword-list').innerHTML=items.map(x=>`<button class="keyword-item" data-index="${keywordData.indexOf(x)}"><span><strong>${esc(x.keyword)}</strong><small>${esc([x.region,x.category].filter(Boolean).join(' · ')||'点击即可使用')}</small></span><em>${esc(SOURCE_LABELS[x.source]||'研究词')}</em></button>`).join('')||'没有找到匹配关键词，换个词试试。';document.querySelectorAll('.keyword-item').forEach(button=>button.addEventListener('click',()=>{const item=keywordData[Number(button.dataset.index)];$('promo-keyword').value=item.keyword;const region=item.region||['涟水','淮安','金湖','洪泽','清江浦','淮阴'].find(name=>item.keyword.startsWith(name));if(region&&!$('promo-region').value)$('promo-region').value=region;if(item.category&&!$('promo-service').value)$('promo-service').value=item.category;document.querySelectorAll('.keyword-item').forEach(x=>x.classList.remove('selected'));button.classList.add('selected');toast(region?'关键词和地区已填入右侧，请核对服务项目':'关键词已填入右侧，请补充地区和服务项目')}))}
async function loadPromotion(){const [keywords,history]=await Promise.all([api('/api/promotion/keywords'),api('/api/promotion/history')]);keywordData=keywords.items;promotionRecords=history.items;filterKeywords();$('promotion-history').className=promotionRecords.length?'history-list':'';$('promotion-history').innerHTML=promotionRecords.slice(0,8).map((x,i)=>`<button class="history-item" data-record="${i}"><span class="history-icon">${esc(x.kind.slice(0,1))}</span><span><strong>${esc(x.kind)}</strong><small>${formatTime(x.created_at)} · 待人工审核</small></span><b>查看</b></button>`).join('')||'<div class="friendly-empty">还没有草稿，生成第一份后会显示在这里。</div>';document.querySelectorAll('.history-item').forEach(button=>button.addEventListener('click',()=>{showPromotion(promotionRecords[Number(button.dataset.record)]);$('promotion-output').scrollIntoView({behavior:'smooth',block:'center'})}))}
window.loadPromotion=loadPromotion;
$('keyword-search').addEventListener('input',filterKeywords);$('keyword-source').addEventListener('change',filterKeywords);
$('save-keyword').addEventListener('click',async()=>{try{await api('/api/promotion/keywords',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({keyword:$('keyword-add').value,region:$('keyword-region').value})});$('keyword-add').value='';await loadPromotion();toast('关键词已保存')}catch(e){toast(e.message,'error')}});
$('clear-promotion').addEventListener('click',()=>{['promo-region','promo-service','promo-keyword','promo-audience','promo-evidence'].forEach(id=>$(id).value='');document.querySelectorAll('.keyword-item').forEach(x=>x.classList.remove('selected'));toast('内容输入已清空')});
$('copy-promotion').addEventListener('click',async()=>{try{await navigator.clipboard.writeText(lastPromotionText);toast('结果已复制，可粘贴到其他地方')}catch{toast('复制失败，请手动选择内容','error')}});
document.querySelectorAll('[data-generator]').forEach(button=>button.addEventListener('click',async()=>{for(const [id,label] of [['promo-region','地区'],['promo-service','服务项目'],['promo-keyword','主关键词']]){if(!$(id).value.trim()){$(id).focus();toast(`请先填写${label}，再生成草稿`,'error');return}}button.disabled=true;const original=button.innerHTML;button.textContent='正在生成…';try{const record=await api('/api/promotion/'+button.dataset.generator,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(promotionPayload())});showPromotion(record);await loadPromotion();toast('草稿已生成并保存在本机')}catch(e){toast(e.message,'error')}finally{button.disabled=false;button.innerHTML=original}}));
function ensurePromotionR8Bridge(){
  const actions=document.querySelector('#promotion .output-card .inline-actions');
  if(!actions||$('promotion-submit-r8'))return;
  const select=document.createElement('select');
  select.id='promotion-r8-platform';
  select.setAttribute('aria-label','目标发布平台');
  select.innerHTML='<option value="douyin">抖音</option><option value="xiaohongshu">小红书</option><option value="kuaishou">快手</option><option value="wechat_channels">视频号</option><option value="weibo">微博</option><option value="bilibili">B站</option><option value="forum">论坛/社区</option><option value="blog">博客/内容站</option>';
  select.style.cssText='border:1px solid #d8e0ec;border-radius:8px;padding:7px;background:#fff';
  const button=document.createElement('button');
  button.id='promotion-submit-r8';
  button.className='primary-small';
  button.textContent='提交到 R8 审核';
  button.disabled=true;
  button.addEventListener('click',async()=>{
    if(!currentPromotionRecord){toast('请先生成或打开一份内容草稿','error');return;}
    button.disabled=true;const old=button.textContent;button.textContent='正在提交…';
    try{
      const result=await api('/api/r8/growth/import-draft',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({draft_id:currentPromotionRecord.id,platform:select.value})});
      toast(result.message||'草稿已进入 R8 人工审核队列');
      if(typeof openPage==='function')openPage('r8-final-center');
      if(typeof window.loadR8FinalCenter==='function')window.loadR8FinalCenter();
    }catch(error){toast(error.message,'error');}
    finally{button.disabled=false;button.textContent=old;}
  });
  actions.prepend(button);actions.prepend(select);
  const guard=document.querySelector('#promotion .promotion-guard');
  if(guard)guard.innerHTML='<strong>真实发布链：</strong>先生成草稿 → 提交 R8 审核 → 选择已授权账号 → 真机发布 → 保存平台 URL 回执 → 24h/72h/7天复盘。未取得真实回执不会显示发布成功。';
}

ensurePromotionR8Bridge();
loadPromotion().catch(e=>toast(e.message,'error'));
