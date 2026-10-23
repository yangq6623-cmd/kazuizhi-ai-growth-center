"""Regression gate for finite UI recovery and truthful owner status."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "05_V2.0.0_Source" / "web"


def read(name: str) -> str:
    return (WEB / name).read_text(encoding="utf-8")


def run() -> None:
    index = read("index.html")
    fetch_budget = read("build_info.js")
    assert index.index('src="build_info.js"') < index.index('src="app.js"')
    assert "const maxConcurrent=2" in fetch_budget
    assert "url.pathname.startsWith('/api/')" in fetch_budget
    assert "details.signal.addEventListener('abort'" in fetch_budget
    assert "window.KZFetchBudget" in fetch_budget

    app = read("app.js")
    assert 'src="about:blank" data-src="/operational.html?embedded=1" loading="lazy"' in app
    assert "window.KZEnsureOperationalFrame=ensureOperationalFrame" in app

    startup = read("r8_12_startup_coordinator.js")
    assert "MAX_AUTOMATIC_RECOVERY_ROUNDS = 2" in startup
    assert "AUTOMATIC_RECOVERY_BATCH_SIZE = 2" in startup
    assert "auto_retry_${failureRecoveryAttempts}" in startup
    assert "slice(0, automatic ? AUTOMATIC_RECOVERY_BATCH_SIZE" in startup
    assert "自动恢复已暂停，避免持续占用连接" in startup
    assert "if (!critical)" in startup
    assert "primeScriptSources(SCRIPT_SEQUENCE.slice(0, 1), SCRIPT_TIMEOUT_MS)" in startup
    assert "primeScriptSources(SCRIPT_SEQUENCE, SCRIPT_TIMEOUT_MS)" not in startup

    geo = read("geo-growth-os.js")
    assert "if(isForegroundGeoVisible())load();" in geo
    assert "if(isForegroundGeoVisible()&&!statusLoading)load();" in geo

    owner = read("main-productization.js")
    assert "startup?.failed_modules" in owner
    assert "界面模块未恢复；本地服务仍在线" in owner
    assert "kz:startup-module-failed" in owner
    assert "kz:startup-module-recovered" in owner
    anomaly_block = owner.split("function anomalyStateText(){", 1)[1].split("function ensureConnectionOwnerSummary", 1)[0]
    assert "/自动恢复失败/" in anomaly_block
    assert "|异常待处理|" not in anomaly_block

    integrations = read("integrations.js")
    assert "lastDiagnosticPayload" in integrations
    assert "startupFailures.map" in integrations
    assert "Number(data.summary?.failed||0)+startupFailures.length" in integrations

    r7 = read("r7.js")
    assert "let r7LoadPromise=null" in r7
    assert "if(r7LoadPromise)return r7LoadPromise" in r7
    assert "await r7Api('/api/r7/ui-snapshot')" in r7
    assert "const [jobs,engine]=await Promise.all" not in r7
    assert "const [agents,audit]=await Promise.all" not in r7
    assert "Promise.all([api('/api/r7/jobs'),api('/api/r7/agents'),api('/api/r7/engine')" not in r7

    operational = read("operational.js")
    assert "state.factory?.social_truth?.accounts" in operational
    assert "state.factory.accounts=socialAccounts" in operational

    print("R8-25 runtime truth and backpressure regression gate passed")


if __name__ == "__main__":
    run()
