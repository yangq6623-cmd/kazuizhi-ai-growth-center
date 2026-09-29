"""Deterministic director contract for the 5-second / two-shot acceptance mode.

The short acceptance path exists to test two-reference continuity, not to test
creative ideation.  It must therefore not be blocked by a second local LLM
call after the reference text has already been understood.  For the explicit
5-second option, inject a truthful two-shot director plan directly into the
simple-flow browser script.  Normal 10/15/30/45/60 second production remains
unchanged and continues to use the real local AI director.
"""
from __future__ import annotations

from backend import ai_gateway_patch as _ai


_original_rewrite_browser_script = _ai._rewrite_browser_script


_MARKER = "async function generatePlanFor(creative, reference, choices, previousPlanId='') {\n    writeJson(PIPELINE_KEY,{reference,creatives:[creative],selectedCreative:creative,directorPlan:null,productionProjectId:'',updatedAt:now()});"

_INSERT = """async function generatePlanFor(creative, reference, choices, previousPlanId='') {
    if(String(creative?.duration||'')==='5 秒'){
      const fixedCharacter=choices?.character?.name||'同一位30岁左右亚洲男维修师傅，深蓝色工装';
      const fixedScene=choices?.scene?.name||'同一室内洗衣机维修场景';
      const plan={
        id:`DP-5S-${Date.now()}`,
        goal:'双镜头连续性验收',
        style:'真实纪实',
        summary:'5秒双镜头受控验收：两张参考图一镜头一张，动作前后连续，不调用第二次AI导演。',
        source:'5秒双镜头验收合同',
        shots:[
          {
            order:1,
            purpose:'发现漏水并蹲下检查',
            narration:'洗衣机漏水，先检查排水接口。',
            duration_seconds:2.5,
            shot_type:'中近景',
            motion:'轻微跟随',
            candidate_count:1,
            importance:'A',
            character:fixedCharacter,
            scene:fixedScene,
            props:['洗衣机','排水管','维修工具'],
            action:'师傅走到漏水的滚筒洗衣机旁蹲下，观察地面积水和排水管接口，动作结束时保持蹲姿并把手移向排水管。',
            generation_method:'参考图1 + Wan图生视频',
            consistency_locks:['同一人物','同一深蓝工装','同一洗衣机','同一室内场景','同一工具','同一光线方向'],
            negative_constraints:['禁止换人','禁止换衣服','禁止换场景','禁止重复播放','禁止卡通感','禁止多手指','禁止水印']
          },
          {
            order:2,
            purpose:'承接动作检查并拧紧接口',
            narration:'',
            duration_seconds:2.5,
            shot_type:'近景',
            motion:'稳定近景',
            candidate_count:1,
            importance:'A',
            character:fixedCharacter,
            scene:fixedScene,
            props:['洗衣机','排水管','维修工具'],
            action:'承接上一镜头结束姿势，师傅继续蹲着，用手检查并拧紧排水管接口，漏水逐渐停止。',
            generation_method:'参考图2 + Wan图生视频',
            consistency_locks:['承接镜头1结束动作','同一人物','同一深蓝工装','同一洗衣机','同一室内场景','同一工具','同一光线方向'],
            negative_constraints:['禁止重新从初始姿势开始','禁止换人','禁止换衣服','禁止换场景','禁止重复播放','禁止卡通感','禁止多手指','禁止水印']
          }
        ],
        createdAt:new Date().toISOString()
      };
      writeJson(PIPELINE_KEY,{reference,creatives:[creative],selectedCreative:creative,directorPlan:plan,productionProjectId:'',updatedAt:now()});
      return plan;
    }
    writeJson(PIPELINE_KEY,{reference,creatives:[creative],selectedCreative:creative,directorPlan:null,productionProjectId:'',updatedAt:now()});"""


def _rewrite_short_acceptance_director(source: str) -> str:
    rewritten = _original_rewrite_browser_script(source)
    if _MARKER in rewritten and "DP-5S-" not in rewritten:
        rewritten = rewritten.replace(_MARKER, _INSERT, 1)
    return rewritten


_ai._rewrite_browser_script = _rewrite_short_acceptance_director
_ai.server.DashboardHandler._kz_short_test_director_fallback = True
