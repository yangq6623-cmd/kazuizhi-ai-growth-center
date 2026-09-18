/* Compact executive layout for Autonomous Decision Center.
   Keeps the same data and actions while reducing blank space and page height. */
(() => {
  if (window.__kazuizhiDecisionLayoutPatchLoaded) return;
  window.__kazuizhiDecisionLayoutPatchLoaded = true;

  const style = document.createElement('style');
  style.id = 'decision-layout-patch-style';
  style.textContent = `
    /* Manager judgement and employee reports should read like one company dashboard,
       not two uneven columns with a large blank area. */
    .decision-grid{grid-template-columns:1fr!important;gap:14px!important}
    .decision-grid>article{min-width:0}
    .decision-stack{grid-template-columns:repeat(2,minmax(0,1fr));gap:10px!important}
    .decision-agent-grid{grid-template-columns:repeat(4,minmax(0,1fr))!important;gap:10px!important}
    .decision-agent{min-height:0;display:flex;flex-direction:column}
    .decision-agent-judge{min-height:38px}
    .decision-agent-open{margin-top:auto;padding-top:8px}

    /* Keep the executive page compact enough to scan without hiding detail. */
    .decision-team,.region-center{margin-top:14px!important}
    .decision-shared-context{grid-template-columns:repeat(4,minmax(0,1fr))!important}
    .decision-shared-item{min-width:0}
    .decision-hero{padding-bottom:16px}
    .decision-item,.decision-agent{padding:11px!important}

    @media(max-width:1250px){
      .decision-agent-grid{grid-template-columns:repeat(2,minmax(0,1fr))!important}
      .decision-shared-context{grid-template-columns:repeat(2,minmax(0,1fr))!important}
    }
    @media(max-width:820px){
      .decision-stack,.decision-agent-grid,.decision-shared-context{grid-template-columns:1fr!important}
    }
  `;
  document.head.appendChild(style);
})();
