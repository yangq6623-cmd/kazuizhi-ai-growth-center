from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "05_V2.0.0_Source"


def main():
    broker = (SOURCE / "backend" / "r8_12_auth_broker_patch.py").read_text(encoding="utf-8")
    bridge = (SOURCE / "web" / "r8_13_seo_geo_bridge.js").read_text(encoding="utf-8")

    for marker in (
        "/api/r8-12/auth/app-credentials/status",
        "/api/r8-12/auth/app-credentials",
        "oauth.app.google_search_console.client_id",
        "oauth.app.google_search_console.client_secret",
        "Windows DPAPI",
        "http://127.0.0.1:8876/api/r8-12/oauth/callback/google_search_console",
    ):
        assert marker in broker, marker

    for marker in (
        "配置 Google Search Console",
        "保存并继续授权",
        "https://console.cloud.google.com/apis/credentials",
        "配置百度搜索资源平台",
        "data.zz.baidu.com",
        "baidu_token",
        "allow_baidu_http_submission:true",
        "保存并真实提交",
    ):
        assert marker in bridge, marker

    assert "console.log(clientSecret" not in bridge
    assert "console.log(token" not in bridge
    print("PASS: guided Google Search Console + Baidu Search Resource secure connector setup is wired.")


if __name__ == "__main__":
    main()
