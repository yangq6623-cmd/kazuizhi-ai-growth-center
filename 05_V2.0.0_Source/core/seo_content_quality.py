"""Service-intent SEO copy and side-effect-free public HTML quality checks.

Keep this module pure: it must never publish, modify receipts, or call external AI.
"""
from __future__ import annotations

import html
import re

CONTENT_QUALITY_REVISION = "20261020-intent-copy-v1"
# Existing pages independently confirmed to contain duplicated/wrong-industry text.
# Refreshing these only avoids surprising bulk republishing of historic Assets.
TARGETED_QUALITY_REFRESH_SLUGS = frozenset({
    "9c7e309e8d0ebd77",  # 水电维修上门
    "077ab037e185be7b",  # 漏水电路故障
    "adadb41b67cec9e3",  # 家政保洁
})


def category(service: str, keyword: str) -> str:
    value = f"{service or ''} {keyword or ''}"
    if "保洁" in value or "家政" in value:
        return "cleaning"
    if "漏水电路" in value or ("漏水" in value and ("跳闸" in value or "电路" in value)):
        return "leak_electrical"
    if "水电" in value or "漏水" in value or "跳闸" in value:
        return "electric_plumbing"
    if "家电" in value or any(x in value for x in ("空调", "洗衣机", "冰箱", "热水器")):
        return "appliance"
    if any(x in value for x in ("疏通", "堵塞", "马桶", "下水")):
        return "drain"
    if "安装" in value:
        return "installation"
    if "个人任务" in value:
        return "personal_task"
    return "general"


def page_copy(service: str, keyword: str, region: str, brand: str) -> dict:
    """Different service intents must have materially different helpful bodies.

    No made-up prices, arrival guarantees, professional licences or customer cases.
    """
    kind = category(service, keyword)
    entry = f"请通过{brand}实际开放的正式入口发布需求，服务是否可约以小程序当前可用状态为准。"
    shared = {
        "action": "官网在线报修",
        "price": "先确认服务范围、报价组成和可能的附加费用，再决定是否下单",
        "faq_question": "提交需求前需要准备哪些信息？",
        "faq_answer": "说明区域、现场情况、希望服务的时间和验收要求；隐私信息只在正式沟通中提供。",
    }
    variants = {
        "cleaning": {
            "action": "官网发布需求",
            "answer": f"寻找{region}家政保洁服务时，建议先明确房屋面积、保洁范围、重点区域和上门时间。{entry}预约前应核对服务是否开放、清洁工具和耗材由谁提供。",
            "fit": "适合家庭日常保洁、厨房卫生间重点清洁和搬家前后的清洁需求；具体项目需与提供服务者逐项确认。",
            "first": "列出需要清洁的房间、面积和重点区域，说明是否有玻璃清洁、高处作业或特殊污渍；有安全风险的工作需提前确认限制。",
            "price": "按面积、项目、时长和是否包含清洁耗材沟通报价，确认范围后再预约",
            "prepare": "大致面积、房间数量、重点清洁位置、上门时间以及是否需要自带清洁工具。",
            "process": "先确认服务类别是否开放，再核对保洁项目、价格、时间、耗材与不包含的项目。完工后按照事先约定的清洁范围逐项检查，异议通过正式渠道反馈。",
            "faq_question": "家政保洁预约时怎样避免服务范围不清？",
            "faq_answer": "事先写清厨房、卫生间、地面、玻璃等具体清洁项目，并确认面积、耗材、附加项目和现场验收方式。",
        },
        "leak_electrical": {
            "answer": f"遇到{region}水管漏水或电路故障，应先判断是否存在触电、进水或火灾风险。能够安全操作时可先关闭相应水阀；电气故障不应带电自行拆修。{entry}",
            "fit": "主要面向水管接头渗漏、墙面水迹、漏水排查、跳闸反复发生及插座线路异常等故障，不代替专业现场检测。",
            "first": "先确认人员安全；漏水先尝试安全止水，发现电火花、异味或积水接触电器时远离危险区域并联系物业或专业人员。",
            "price": "故障排查、材料、更换项目和施工费用分别说明，用户确认后再维修",
            "prepare": "漏水或跳闸发生的位置、持续时间、是否影响相邻房间、可安全拍摄的照片，以及是否已关闭相关阀门。",
            "process": "说明漏水与电路异常是否同时存在，由具备相应能力的人员现场判断故障范围。检测、安全处理、材料更换和施工增项应分别沟通并通过正式记录确认。",
            "faq_question": "漏水附近出现跳闸，应该先修什么？",
            "faq_answer": "优先保障人身安全，不要触摸受潮电器或自行恢复送电。能安全关闭的水阀先关闭，再联系合适的专业人员分别排查水路与电路。",
        },
        "electric_plumbing": {
            "answer": f"在{region}寻找水电上门维修时，先说明是水龙头、阀门、水管、开关、灯具还是插座问题，以及故障发生的时间和位置。{entry}",
            "fit": "适合家庭水龙头、阀门、水管接头、开关插座、灯具和室内水电设施的小修与安装需求；涉及公共管线应先联系物业。",
            "first": "发现水管漏水时，在安全情况下关闭对应阀门；跳闸、焦糊味或裸露线路应避免触碰，必要时向物业或供电部门求助。",
            "price": "分别核对检测、配件、人工和可能的拆装费用，确认后再施工",
            "prepare": "故障设施类型、具体位置、问题表现、希望完成的维修事项和可安全拍摄的照片。",
            "process": "用户发布水电需求后，先确认服务范围及上门条件。维修前说明故障原因和材料清单，价格与施工增项经用户确认后再处理，并保留完工记录。",
            "faq_question": "维修开关插座或水龙头时应准备什么？",
            "faq_answer": "可提供设备样式和故障描述；不要自行拆卸带电线路。维修人员到场前确认是否需要备料及现场是否具备安全施工条件。",
        },
        "appliance": {
            "answer": f"在{region}寻找家电检修帮助时，应先提供家电种类、型号、故障现象及是否仍在保修期。{entry}",
            "fit": "适合空调、洗衣机、热水器、冰箱等家电的检测与维修需求，具体可接单项目以真实服务范围为准。",
            "first": "仍在保修期先联系品牌官方售后；涉及燃气泄漏、异味、冒烟或漏电风险时停止使用并联系合适的专业部门。",
            "price": "检测费、人工费及配件费分别说明，避免未经确认就更换零件",
            "prepare": "设备品牌型号、故障表现、是否报错、购买及保修信息、可安全拍摄的照片。",
            "process": "先核实设备与故障类别是否在服务范围，再沟通检测、配件、价格和维修方案。需要更换配件或增加维修项目时重新确认。",
            "faq_question": "家电还在保修期可以直接找上门师傅吗？",
            "faq_answer": "建议先确认官方保修条款与厂家售后渠道，避免自行拆修影响保修权益。",
        },
        "drain": {
            "answer": f"{region}厨房、卫生间或地漏排水堵塞时，先说明堵塞位置、返水程度及此前是否使用过疏通剂。{entry}",
            "fit": "适合厨房水槽、浴室地漏、马桶和室内排水管道堵塞的上门排查与疏通需求。",
            "first": "先停止继续大量排水；已使用化学疏通剂时，应明确告知服务人员，避免混用药剂或自行拆管。",
            "price": "确认疏通方式、是否拆装、按次计价或按项目计价及附加费用",
            "prepare": "堵塞位置、返水程度、此前尝试的方法、是否用过疏通剂及可安全拍摄的照片。",
            "process": "先确认堵塞范围与适用处理方式，提前说明价格及可能的拆装费用；完成后检查排水情况并记录服务结果。",
            "faq_question": "管道堵塞后可以继续倒疏通剂吗？",
            "faq_answer": "不建议混合不同疏通剂。应告知师傅此前使用过哪些产品，必要时停止使用并避免接触残液。",
        },
        "installation": {
            "answer": f"在{region}找人安装灯具、卫浴或其他家居用品时，先准备尺寸、型号和安装位置，并说明是否需要打孔或拆旧。{entry}",
            "fit": "适合家居用品、灯具、卫浴和相关设备的上门安装需求；电力和高空项目须由具备相应能力的人员完成。",
            "first": "提前确认墙面材质、尺寸、配件是否齐全；涉及电路和高空作业时不自行冒险操作。",
            "price": "确认安装人工、拆旧、打孔、辅料及特殊施工是否另计",
            "prepare": "安装物品品牌型号、尺寸重量、配件清单、墙体情况和希望上门时间。",
            "process": "安装前核对施工条件和所需配件，明确报价、安装步骤及验收方式；完成后检查牢固性和基本功能。",
            "faq_question": "预约安装服务前要拍什么照片？",
            "faq_answer": "可提供包装与配件、计划安装的位置、尺寸和墙面情况，避免上传家庭隐私信息。",
        },
        "personal_task": {
            "answer": f"需要在{region}发布临时生活任务时，请写清地点范围、时间、工作内容和验收要求。{entry}",
            "fit": "适合跑腿、搬运协助、取送等真实开放的个人任务类别；任务和接单权限以平台当前规则为准。",
            "first": "不公开证件号、银行卡、精确门牌等隐私信息；事先核对任务合法性、安全性和费用。",
            "price": "双方确认任务范围、费用、完成时间和可能的额外支出",
            "prepare": "任务内容、区域、约定时间、需要携带的工具及完成标准。",
            "process": "发布任务后，由平台按实际开放规则进行展示和匹配；完成方式、费用与交付标准应由双方确认。",
            "faq_question": "个人任务发布以后谁能接单？",
            "faq_answer": "具体接单权限以平台当前开放区域、注册审核和任务类别规则为准，不能保证所有人均可接单。",
        },
    }
    result = dict(shared)
    result.update(variants.get(kind, {
        "answer": f"在{region}寻找{service}服务时，应先说明需求、可服务区域、时间与验收条件。{entry}",
        "fit": "适合服务范围明确、可以提前沟通并确认费用的本地生活需求。",
        "first": "先核对该服务类别是否开放，公开描述避免泄露个人隐私。",
        "prepare": "具体服务项目、区域、时间和所需信息，不公开个人敏感信息。",
        "process": "先确认实际开放的服务类别与服务方，再沟通服务范围、费用和验收标准。",
    }))
    result["kind"] = kind
    return result


def validate_staged_content(asset: dict, page_html: str) -> dict:
    """Validate generated and refreshed pages before they may go live.

    This is intentionally structural and service-specific, not an AI score.
    It does not invent duplication percentages, indexation or publication.
    """
    text = str(page_html or "")
    keyword = str((asset or {}).get("keyword") or "").strip()
    service = str((asset or {}).get("service") or "").strip()
    source = str((asset or {}).get("source_tracking_id") or "").strip()
    category_name = category(service, keyword)
    problems = []
    if len(text) < 800:
        problems.append("页面正文过短")
    if "<h1>" not in text.lower():
        problems.append("缺少H1标题")
    if keyword and html.escape(keyword, quote=True) not in text:
        problems.append("页面缺少目标关键词")
    if source and source not in text:
        problems.append("来源追踪编号丢失")
    if "kz_source=" not in text or "asset_id=" not in text:
        problems.append("小程序来源参数不完整")
    if 'rel="canonical"' not in text:
        problems.append("canonical缺失")
    if category_name == "cleaning":
        banned = (
            "维修类项目应先检测", "现场检测后明细报价",
            "故障现象、发生时间、设备型号", "在线报修",
            "检测结果、报价、增项和完工确认",
        )
        if any(phrase in text for phrase in banned):
            problems.append("家政保洁页混入维修模板话术")
        if "保洁范围" not in text and "清洁范围" not in text:
            problems.append("缺少家政保洁特有的服务内容")
    if category_name == "leak_electrical" and ("止水" not in text or "电路" not in text):
        problems.append("漏水电路专题缺少水路及电路的独立故障说明")
    return {"ok": not problems, "reasons": problems, "category": category_name}
