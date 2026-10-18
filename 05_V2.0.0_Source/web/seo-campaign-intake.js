(function () {
  'use strict';

  const $ = id => document.getElementById(id);
  const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));

  function addStyle() {
    if ($('kz-campaign-intake-style')) return;
    const style = document.createElement('style');
    style.id = 'kz-campaign-intake-style';
    style.textContent = `
      .campaign-intake{margin-top:16px}.campaign-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}.campaign-field{display:flex;flex-direction:column;gap:5px}.campaign-field.wide{grid-column:1/-1}.campaign-field label{font-size:12px;font-weight:700;color:#52667f}.campaign-field input,.campaign-field select,.campaign-field textarea{width:100%;border:1px solid #ccd7ea;border-radius:9px;padding:10px;font:inherit;background:#fff}.campaign-field textarea{min-height:170px;resize:vertical}.campaign-files{display:flex;gap:10px;flex-wrap:wrap;align-items:center}.campaign-confirm{display:flex;gap:9px;align-items:flex-start;margin-top:12px;color:#43556e}.campaign-confirm input{margin-top:4px}.campaign-result{margin-top:12px;padding:11px 13px;border-radius:10px;background:#f8faff;color:#52667f}.campaign-result.ok{background:#eef9f3;color:#166b4a}.campaign-result.error{background:#fff0f0;color:#a52d2d}.campaign-actions{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-top:13px}.campaign-preview{max-width:120px;max-height:90px;border-radius:9px;border:1px solid #dce5f2;object-fit:cover;display:none}@media(max-width:820px){.campaign-grid{grid-template-columns:1fr}.campaign-field.wide{grid-column:auto}}
    `;
    document.head.appendChild(style);
  }

  function templateContent() {
    return `## 哪些情况适合发布需求
- 家中漏水、跳闸、开关插座或灯具出现故障
- 需要本地师傅上门检查、维修或安装
- 希望先说明问题，再确认检测结果和明细报价

## 发布前准备
请写清所在区域、故障现象、发生时间和方便上门的时段。可以上传安全拍摄的现场照片，但不要公开填写门牌、身份证、银行卡等敏感信息。

## 费用与售后
维修类项目应先检测并提供明细报价，用户确认后施工；增项、完工确认和售后应通过正式订单或沟通记录留痕。实际响应时间和费用以双方真实确认为准。`;
  }

  function install() {
    if ($('kz-campaign-intake') || !$('pipeline-section')) return;
    addStyle();
    const section = document.createElement('section');
    section.className = 'section card campaign-intake';
    section.id = 'kz-campaign-intake';
    section.innerHTML = `
      <div class="toolbar"><div><h3>推广内容入库与全链路执行</h3><div class="sub">把已审核文案和图片登记为真实 SEO 资产，再依次执行生成、QC、公网上线、搜索提交和归因追踪。</div></div><span class="tag info">新增入口</span></div>
      <div class="campaign-grid">
        <div class="campaign-field"><label for="campaign-region">地区</label><input id="campaign-region" value="涟水县" maxlength="40"></div>
        <div class="campaign-field"><label for="campaign-service">服务类型</label><select id="campaign-service"><option>水电安装维修</option><option>家电维修</option><option>管道疏通</option><option>安装服务</option><option>个人任务</option></select></div>
        <div class="campaign-field"><label for="campaign-keyword">核心关键词</label><input id="campaign-keyword" value="涟水水电维修" maxlength="100"></div>
        <div class="campaign-field wide"><label for="campaign-title">标题</label><input id="campaign-title" value="涟水水电维修怎么找？卡嘴子本地需求发布与办理指南" maxlength="120"></div>
        <div class="campaign-field wide"><label for="campaign-summary">摘要</label><input id="campaign-summary" value="面向涟水县家庭水电维修需求，说明适用场景、发布步骤、报价确认和进入卡嘴子小程序的方法。" maxlength="300"></div>
        <div class="campaign-field wide"><label for="campaign-content">正文（可粘贴 Markdown 或导入 .md/.txt）</label><textarea id="campaign-content" maxlength="20000"></textarea></div>
        <div class="campaign-field wide"><label>文案与主图</label><div class="campaign-files"><label class="btn ghost">导入文案文件<input id="campaign-copy-file" type="file" accept=".md,.txt,text/plain,text/markdown" hidden></label><label class="btn ghost">选择推广主图<input id="campaign-image-file" type="file" accept="image/jpeg,image/png,image/webp" hidden></label><span id="campaign-file-note" class="sub">图片支持 JPG / PNG / WebP，最大 5MB</span><img id="campaign-image-preview" class="campaign-preview" alt="推广主图预览"></div></div>
      </div>
      <label class="campaign-confirm"><input id="campaign-rights" type="checkbox"><span>我确认文案和图片为本人/公司自有或已取得发布授权。</span></label>
      <label class="campaign-confirm"><input id="campaign-run-confirm" type="checkbox"><span>我确认本次入库后立即运行完整链路；只有取得真实公网验证与搜索平台回执时，系统才计为发布或提交成功。</span></label>
      <div class="campaign-actions"><button class="btn primary" id="campaign-import-run">导入并运行完整链路</button><button class="btn ghost" id="campaign-import-only">仅入库，稍后自动运行</button><span class="sub">不会把草稿、排队或本地文件冒充为公开曝光。</span></div>
      <div id="campaign-result" class="campaign-result">等待导入首轮推广内容。</div>
    `;
    $('pipeline-section').parentNode.insertBefore(section, $('pipeline-section'));
    $('campaign-content').value = templateContent();
    bind();
  }

  function readDataUrl(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result || ''));
      reader.onerror = () => reject(new Error('图片读取失败'));
      reader.readAsDataURL(file);
    });
  }

  async function payload(runNow) {
    const image = $('campaign-image-file').files[0];
    if (!$('campaign-rights').checked) throw new Error('请先确认文案和图片的发布权');
    if (runNow && !$('campaign-run-confirm').checked) throw new Error('立即执行前请勾选完整链路确认');
    if (image && image.size > 5 * 1024 * 1024) throw new Error('推广主图不能超过 5MB');
    const result = {
      region: $('campaign-region').value.trim(), service: $('campaign-service').value,
      keyword: $('campaign-keyword').value.trim(), title: $('campaign-title').value.trim(),
      summary: $('campaign-summary').value.trim(), content: $('campaign-content').value.trim(),
      rights_confirmed: true, owner_approved: runNow, run_now: runNow,
      priority: 'S', intent: '交易'
    };
    if (!result.keyword || !result.title || !result.summary || !result.content) throw new Error('关键词、标题、摘要和正文必须填写完整');
    if (image) {
      result.image_name = image.name;
      result.image_mime = image.type;
      result.image_base64 = await readDataUrl(image);
    }
    return result;
  }

  function describe(reply) {
    const imported = reply.import || {}, asset = imported.asset || {}, run = reply.run_result || {};
    const deploy = run.public_deploy || {}, search = run.search_submit || {};
    const published = (deploy.published || []).length;
    const submitted = Number(search.submitted_count || (search.submitted || []).length || 0);
    const failures = (deploy.failed || []).length + (search.failed || []).length;
    return `资产 ${asset.id || '已建立'} · 当前 ${asset.stage || 'GENERATED'} · 本轮真实公网发布 ${published} · 搜索提交回执 ${submitted} · 待处理/失败 ${failures}`;
  }

  async function submit(runNow, button) {
    const result = $('campaign-result');
    const old = button.textContent;
    button.disabled = true;
    button.textContent = runNow ? '正在执行完整链路…' : '正在入库…';
    result.className = 'campaign-result';
    result.textContent = button.textContent;
    try {
      const body = await payload(runNow);
      const reply = await post('/api/r8-13/seo-geo/campaign/import', body);
      result.className = 'campaign-result ok';
      result.textContent = describe(reply);
      if (typeof setActionStatus === 'function') setActionStatus('推广内容已进入真实资产流水线；页面将显示最新回执。');
      if (typeof load === 'function') await load();
    } catch (error) {
      result.className = 'campaign-result error';
      result.textContent = `操作失败：${error.message || error}`;
      if (typeof setActionStatus === 'function') setActionStatus(result.textContent, true);
    } finally {
      button.disabled = false;
      button.textContent = old;
    }
  }

  function bind() {
    $('campaign-copy-file').addEventListener('change', async event => {
      const file = event.target.files[0];
      if (!file) return;
      if (file.size > 200 * 1024) { $('campaign-result').textContent = '文案文件不能超过 200KB'; return; }
      $('campaign-content').value = await file.text();
      $('campaign-file-note').textContent = `已载入文案：${file.name}`;
    });
    $('campaign-image-file').addEventListener('change', event => {
      const file = event.target.files[0], preview = $('campaign-image-preview');
      if (!file) { preview.style.display = 'none'; return; }
      preview.src = URL.createObjectURL(file);
      preview.style.display = 'block';
      $('campaign-file-note').textContent = `已选择主图：${file.name}（${Math.round(file.size / 1024)}KB）`;
    });
    $('campaign-import-run').onclick = event => submit(true, event.currentTarget);
    $('campaign-import-only').onclick = event => submit(false, event.currentTarget);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', install, {once:true});
  else install();
})();
