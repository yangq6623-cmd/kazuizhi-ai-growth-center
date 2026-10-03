import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "05_V2.0.0_Source"
sys.path.insert(0, str(SOURCE))

from core import r8_control
from integrations import social_session_probe as probe


def account_state(account_id):
    return next(x for x in r8_control.control_status()["accounts"] if x["account_id"] == account_id)


def main():
    positive = probe.evaluate_douyin_session(
        alias="卡嘴子本地服务维修",
        package_installed=True,
        foreground_text="mCurrentFocus=com.ss.android.ugc.aweme/.main.MainActivity",
        ui_xml='<node text="卡嘴子本地服务维修"/><node text="编辑主页"/><node text="抖音号：61185186364"/><node text="作品"/>',
    )
    assert positive["status"] == "authorized"
    assert positive["reason"] == "real_device_profile_verified"

    wrong_account = probe.evaluate_douyin_session(
        alias="别的账号",
        package_installed=True,
        foreground_text="com.ss.android.ugc.aweme/.main.MainActivity",
        ui_xml='<node text="卡嘴子本地服务维修"/><node text="编辑主页"/><node text="抖音号：61185186364"/><node text="作品"/>',
    )
    assert wrong_account["status"] == "inconclusive", "another logged-in profile must not verify the bound alias"

    challenge = probe.evaluate_douyin_session(
        alias="卡嘴子本地服务维修",
        package_installed=True,
        foreground_text="com.ss.android.ugc.aweme/.main.MainActivity",
        ui_xml='<node text="安全验证"/><node text="请完成人脸验证"/>',
    )
    assert challenge["status"] == "needs_human"

    logged_out = probe.evaluate_douyin_session(
        alias="卡嘴子本地服务维修",
        package_installed=True,
        foreground_text="com.ss.android.ugc.aweme/.main.MainActivity",
        ui_xml='<node text="登录抖音"/><node text="手机号登录"/>',
    )
    assert logged_out["status"] == "logged_out"

    old_local = os.environ.get("LOCALAPPDATA")
    with tempfile.TemporaryDirectory() as temp:
        os.environ["LOCALAPPDATA"] = temp
        try:
            r8_control.register_device({"device_id": "ADB-R811", "label": "ELE-AL00", "device_type": "real_android", "transport": "usb"})
            r8_control.record_device_probe("ADB-R811", True, source="adb", detail="test")
            r8_control.register_account({
                "platform": "douyin", "device_id": "ADB-R811", "alias": "卡嘴子本地服务维修",
                "label": "卡嘴子本地服务维修", "role": "service", "region": "涟水县",
                "service_category": "水电安装维修", "automation_level": "L2",
            })
            acc = r8_control.control_status()["accounts"][0]
            account_id = acc["account_id"]
            assert acc["login_status"] == "not_verified", "binding alone must never claim a verified login"

            old_installed, old_foreground, old_xml = probe._package_installed, probe._foreground, probe._ui_xml
            probe._package_installed = lambda device_id, package: True
            probe._foreground = lambda device_id: "mCurrentFocus=com.ss.android.ugc.aweme/.main.MainActivity"
            probe._ui_xml = lambda device_id: '<node text="卡嘴子本地服务维修"/><node text="编辑主页"/><node text="抖音号：61185186364"/><node text="作品"/>'
            try:
                result = probe.verify_pending_accounts(force=True)
                assert result["checked"] == 1
                acc = account_state(account_id)
                assert acc["login_status"] == "authorized"
                assert acc["risk_level"] == "normal"
                assert acc["login_verified_at"]
                assert acc["last_login_probe_source"] == "device_probe"
                assert acc["last_login_probe_method"] == "automatic_device_probe"
                assert acc["last_login_probe_result"] == "authorized"
                assert acc["automation_paused"] is False

                # A real verification challenge must stop automation rather than bypass it.
                r8_control.update_account_status({"account_id": account_id, "login_status": "not_verified", "automation_paused": False, "risk_level": "unknown"})
                probe._ui_xml = lambda device_id: '<node text="安全验证"/><node text="人脸验证"/>'
                result = probe.verify_pending_accounts(force=True)
                acc = account_state(account_id)
                assert acc["login_status"] == "needs_human"
                assert acc["automation_paused"] is True
                assert acc["risk_level"] == "attention"
                assert result["results"][0]["status"] == "needs_human"

                # Field fallback: Douyin may render the visible account page while
                # UIAutomator exposes too little text. The owner may provide the
                # missing identity evidence, but only with the real ADB phone online
                # and Douyin actually foreground. This still never publishes.
                r8_control.update_account_status({"account_id": account_id, "login_status": "not_verified", "automation_paused": False, "risk_level": "unknown", "last_error": ""})
                probe._ui_xml = lambda device_id: '<hierarchy rotation="0"><node text="" content-desc=""/></hierarchy>'
                machine = probe.verify_pending_accounts(force=True)
                assert machine["results"][0]["status"] == "inconclusive"
                assert account_state(account_id)["login_status"] == "not_verified"

                confirmed = probe.confirm_owner_login(account_id)
                assert confirmed["status"] == "authorized"
                assert confirmed["reason"] == "owner_real_device_confirmation"
                assert confirmed["publishes_content"] is False
                acc = account_state(account_id)
                assert acc["login_status"] == "authorized"
                assert acc["risk_level"] == "normal"
                assert acc["automation_paused"] is False
                assert acc["last_login_probe_source"] == "device_probe"
                assert acc["last_login_probe_method"] == "owner_real_device_confirmation"
                assert acc["owner_confirmed_login_at"]

                # Owner confirmation may not override an actual login/risk challenge.
                r8_control.update_account_status({"account_id": account_id, "login_status": "not_verified", "automation_paused": False, "risk_level": "unknown"})
                probe._ui_xml = lambda device_id: '<node text="安全验证"/><node text="人脸验证"/>'
                blocked_confirm = probe.confirm_owner_login(account_id)
                assert blocked_confirm["status"] == "needs_human"
                acc = account_state(account_id)
                assert acc["login_status"] == "needs_human"
                assert acc["automation_paused"] is True

                # Owner confirmation also cannot authorize when Douyin is not foreground.
                r8_control.update_account_status({"account_id": account_id, "login_status": "not_verified", "automation_paused": False, "risk_level": "unknown"})
                probe._foreground = lambda device_id: "mCurrentFocus=com.android.launcher/.Launcher"
                no_foreground = probe.confirm_owner_login(account_id)
                assert no_foreground["status"] == "inconclusive"
                assert account_state(account_id)["login_status"] == "not_verified"
            finally:
                probe._package_installed, probe._foreground, probe._ui_xml = old_installed, old_foreground, old_xml
        finally:
            if old_local is None:
                os.environ.pop("LOCALAPPDATA", None)
            else:
                os.environ["LOCALAPPDATA"] = old_local

    source = (SOURCE / "integrations" / "social_session_probe.py").read_text(encoding="utf-8")
    assert "requests" not in source
    assert "bypass" in source
    assert "publishes_content" in source
    assert "owner_real_device_confirmation" in source
    print("PASS: R8-11 real-device Douyin verifier supports strong automatic evidence and a guarded owner-confirmed fallback without paid token services or publish bypass.")


if __name__ == "__main__":
    main()
