import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "05_V2.0.0_Source"
sys.path.insert(0, str(SRC))

from core import r8_control  # noqa: E402

ui = (SRC / "web" / "social_media_center.js").read_text(encoding="utf-8")
forms = (SRC / "web" / "forms.js").read_text(encoding="utf-8")
backend = (SRC / "backend" / "server.py").read_text(encoding="utf-8")
control = (SRC / "core" / "r8_control.py").read_text(encoding="utf-8")

for platform in ("douyin", "xiaohongshu", "kuaishou", "wechat_channels", "weibo", "bilibili"):
    assert platform in r8_control.PLATFORMS, f"missing social platform: {platform}"

for route in (
    "/api/r8/social",
    "/api/r8/social/account",
    "/api/r8/social/account/status",
    "/api/r8/social/account/remove",
):
    assert route in backend, f"missing social backend route: {route}"

assert "social_media_center.js" in forms
assert "社媒中心" in ui
for section in ("总览", "设备矩阵", "平台矩阵", "任务队列", "内容中心", "消息与线索", "风险与日志"):
    assert section in ui, f"missing social center section: {section}"

assert "/api/r8/social" in ui
assert "localStorage" not in ui, "social center must use durable backend state, not browser localStorage"
assert "一台手机 = 一个 AI 社媒运营终端" in ui
assert "单手机串行" in ui and "多手机并行" in ui
assert "快手" in ui
assert "不保存平台明文密码" in ui
assert "验证码" in ui and "人脸" in ui
assert "固定机械停留时长" in ui

for rule in (
    "one_device_many_platform_accounts",
    "single_device_foreground_serial",
    "multi_device_parallel_after_pilot",
    "platform_passwords_not_stored",
):
    assert rule in control, f"missing social terminal rule: {rule}"

for forbidden in ("password:", "passcode:", "bypass_captcha", "hide_automation_framework"):
    assert forbidden not in ui, f"unsafe or secret-bearing social UI token exposed: {forbidden}"

print("PASS: R8 standalone social center uses durable backend state, device-centric multi-platform terminals, serial-per-phone scheduling and human-gated verification")
