"""Offline acceptance gate for R8-19 GEO Phase 2 analysis/comparison."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "05_V2.0.0_Source"


def main():
    old = os.environ.get("LOCALAPPDATA")
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["LOCALAPPDATA"] = tmp
        sys.path.insert(0, str(SRC))
        try:
            from core import geo_analysis
            from integrations import geo_chatgpt_analyzer

            receipts = [
                {
                    "official_truth": True,
                    "evidence_level": "A",
                    "evidence_id": "GEO-RECEIPT-001",
                    "question_id": "GEO50-D01",
                    "question_text": "涟水县哪里可以找水电维修师傅？",
                    "question_type": "discovery",
                    "service": "水电安装维修",
                    "intent": "local_discovery",
                    "provider": "chatgpt_web",
                    "model": "browser",
                    "raw_answer": "可以考虑卡嘴子寻找本地水电维修师傅。也可以看看美团。来源：https://kazuizhi.com/",
                    "citation_urls": ["https://kazuizhi.com/"],
                    "extracted_urls": ["https://kazuizhi.com/"],
                    "tested_at": "2026-10-01T10:00:00",
                },
                {
                    "official_truth": True,
                    "evidence_level": "B",
                    "evidence_id": "GEO-RECEIPT-002",
                    "question_id": "GEO50-C01",
                    "question_text": "涟水找维修师傅用什么平台比较方便？",
                    "question_type": "commercial",
                    "service": "综合维修",
                    "intent": "commercial_compare",
                    "provider": "openai_web_search",
                    "model": "gpt-test",
                    "raw_answer": "可以先看看58同城和美团的本地服务信息。",
                    "citation_urls": [],
                    "extracted_urls": [],
                    "tested_at": "2026-10-01T10:01:00",
                },
                {
                    "official_truth": True,
                    "evidence_level": "A",
                    "evidence_id": "GEO-RECEIPT-003",
                    "question_id": "GEO50-B01",
                    "question_text": "卡嘴子是什么平台？",
                    "question_type": "brand",
                    "service": "品牌",
                    "intent": "brand_fact",
                    "provider": "chatgpt_web",
                    "model": "browser",
                    "raw_answer": "卡嘴子是本地服务连接平台。",
                    "citation_urls": [],
                    "extracted_urls": [],
                    "tested_at": "2026-10-01T10:02:00",
                },
                {
                    "official_truth": False,
                    "evidence_level": "C",
                    "evidence_id": "GEO-RECEIPT-C01",
                    "question_id": "GEO50-D02",
                    "question_text": "涟水家里跳闸了找谁上门处理？",
                    "question_type": "discovery",
                    "service": "水电安装维修",
                    "intent": "urgent_service",
                    "provider": "local_model",
                    "model": "local",
                    "raw_answer": "卡嘴子可能会出现。",
                    "citation_urls": [],
                    "extracted_urls": [],
                },
            ]

            result = geo_analysis.refresh(receipts)
            summary = result["summary"]
            assert summary["tested"] == 3
            assert summary["mentioned"] == 2
            assert summary["recommended"] == 1
            assert summary["cited"] == 1
            assert summary["by_type"]["commercial"]["tested"] == 1
            assert summary["by_type"]["commercial"]["recommendation_rate"] == 0.0
            assert summary["gaps"][0]["code"] in {"recommendation_missing", "brand_visibility_missing", "official_citation_missing"}
            platforms = {item["name"] for item in summary["platform_candidates"]}
            assert {"58同城", "美团"}.issubset(platforms)
            assert result["auxiliary_count"] == 1
            assert result["chatgpt_judgement"]["required"] is True

            discovery = next(x for x in result["question_results"] if x["question_id"] == "GEO50-D01")
            assert discovery["brand_mentioned"] is True
            assert discovery["brand_recommended"] is True
            assert discovery["brand_cited"] is True
            assert discovery["visibility_score"] > 0

            brand = next(x for x in result["question_results"] if x["question_id"] == "GEO50-B01")
            assert brand["brand_mentioned"] is True
            assert brand["brand_cited"] is False
            assert any(g["code"] == "official_citation_missing" for g in brand["gaps"])

            advisor_status = geo_chatgpt_analyzer.status()
            assert isinstance(advisor_status.get("ready"), bool)
            assert geo_chatgpt_analyzer.SCHEMA["type"] == "object"
            assert "candidate_actions" in geo_chatgpt_analyzer.SCHEMA["properties"]

            pack = geo_analysis.analysis_pack()
            assert pack["facts_only"] is True
            assert pack["chatgpt_judgement_required"] is True
            assert all(item["evidence_level"] in {"A", "B"} for item in pack["question_results"])

            # Field regression: cumulative SEO stage state and today's delta must be visibly separated.
            seo_semantics = (SRC / "web" / "seo-geo-phase1-final.css").read_text(encoding="utf-8")
            assert "自动作业流水线（累计真实状态）" in seo_semantics
            assert "累计状态：" in seo_semantics
            assert "今日增量" in seo_semantics
            assert "两者不混用" in seo_semantics

            # Field regression: optional cloud API must not be presented as the ChatGPT control-brain state.
            chatgpt_semantics = (SRC / "web" / "geo-phase2-chatgpt.css").read_text(encoding="utf-8")
            assert "云端模型 " in chatgpt_semantics
            assert "ChatGPT 总控、网页真实验证、云端模型 API 为三个独立状态" in chatgpt_semantics
            assert "不影响 GEO 真实网页验证、Evidence / Receipt 保存与 A/B 正式证据统计" in chatgpt_semantics

            print("PASS: R8-19 GEO Phase 2 analysis/comparison + field truth semantics gate")
        finally:
            sys.path.remove(str(SRC))
            if old is None:
                os.environ.pop("LOCALAPPDATA", None)
            else:
                os.environ["LOCALAPPDATA"] = old


if __name__ == "__main__":
    main()
