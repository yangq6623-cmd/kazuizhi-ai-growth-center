import argparse
import json
import sys
import time

from selenium import webdriver
from selenium.common.exceptions import StaleElementReferenceException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait


PRIMARY_ROUTES = [
    ("老板总控", "dashboard"),
    ("AI决策中心", "workflow"),
    ("内容创导", "content-studio"),
    ("执行中心", "operational-hub"),
    ("待我处理", "r810-attention"),
    ("经营结果", "analytics"),
    ("SEO/GEO增长", "r813-seo-geo"),
    ("自进化中心", "r810-evolution"),
]

SECONDARY_ROUTES = [
    ("系统状态与连接", "connections", ""),
    ("历史与审计", "history", ""),
    ("高级设置", "connections", "advanced"),
]


def visible(driver, element_id):
    try:
        node = driver.find_element(By.ID, element_id)
        return node.is_displayed() and "active" in (node.get_attribute("class") or "").split()
    except Exception:
        return False


def wait_active(driver, target, timeout=12):
    WebDriverWait(driver, timeout).until(lambda d: visible(d, target))
    return driver.find_element(By.ID, target)


def click_route(driver, target, action="", timeout=12):
    suffix = f'[data-action="{action}"]' if action else ':not([data-action])'
    selector = f'.r810-nav-button[data-target="{target}"]{suffix}'
    wait = WebDriverWait(driver, timeout)
    button = wait.until(lambda d: next((x for x in d.find_elements(By.CSS_SELECTOR, selector) if x.is_displayed()), None))
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", button)
    try:
        button.click()
    except StaleElementReferenceException:
        button = driver.find_element(By.CSS_SELECTOR, selector)
        button.click()
    page = wait_active(driver, target, timeout)
    return page


def assert_content_studio(driver):
    frame = WebDriverWait(driver, 15).until(
        lambda d: d.find_element(By.ID, "content-studio-frame")
        if d.find_elements(By.ID, "content-studio-frame")
        else None
    )
    if not frame.is_displayed():
        raise AssertionError("内容创导 iframe 已创建但不可见")
    driver.switch_to.frame(frame)
    try:
        WebDriverWait(driver, 12).until(lambda d: d.find_elements(By.ID, "studio-root"))
        text = driver.find_element(By.ID, "studio-root").text
        if "卡嘴子 AI 内容创导平台" not in text and "今天的内容生产从这里开始" not in text:
            raise AssertionError("内容创导 iframe 未显示真实工作台内容")
    finally:
        driver.switch_to.default_content()


def assert_execution_center(driver):
    frame = WebDriverWait(driver, 12).until(
        lambda d: d.find_element(By.ID, "operational-frame")
        if d.find_elements(By.ID, "operational-frame")
        else None
    )
    if not frame.is_displayed():
        raise AssertionError("执行中心 iframe 已创建但不可见")
    driver.switch_to.frame(frame)
    try:
        WebDriverWait(driver, 12).until(
            lambda d: d.find_elements(By.ID, "dashboard") or d.find_elements(By.CSS_SELECTOR, ".app-shell")
        )
    finally:
        driver.switch_to.default_content()


def assert_seo_geo(driver):
    WebDriverWait(driver, 15).until(lambda d: d.find_elements(By.CSS_SELECTOR, "#r813-seo-geo .r813-growth-tabs"))
    seo_frame = WebDriverWait(driver, 15).until(
        lambda d: d.find_element(By.ID, "r813-seo-frame")
        if d.find_elements(By.ID, "r813-seo-frame")
        else None
    )
    if not seo_frame.is_displayed():
        raise AssertionError("SEO/GEO 主工作区已创建但 SEO iframe 不可见")

    geo_tab = driver.find_element(By.CSS_SELECTOR, '#r813-seo-geo [data-r813-workspace="geo"]')
    geo_tab.click()

    growth = WebDriverWait(driver, 6).until(
        lambda d: d.find_element(By.ID, "geo-growth-os")
        if d.find_elements(By.ID, "geo-growth-os") and d.find_element(By.ID, "geo-growth-os").is_displayed()
        else None
    )
    if not growth.is_displayed():
        raise AssertionError("主平台直载 GEO 自动增长工作台存在但不可见")
    if driver.find_elements(By.ID, "r813-geo-core-loading"):
        loading = driver.find_element(By.ID, "r813-geo-core-loading")
        if loading.is_displayed():
            raise AssertionError("主平台 GEO 仍停留在初始化提示")

    state = WebDriverWait(driver, 8).until(
        lambda d: (d.find_element(By.ID, "geo-os-state").text or "").strip()
        if d.find_elements(By.ID, "geo-os-state")
        else ""
    )
    if not state:
        raise AssertionError("主平台 GEO 状态标签为空")
    if state == "未启动":
        raise AssertionError("GEO 工作台已显示，但自动运营仍处于未启动状态")

    # Formal A/B count in the legacy SEO summary and the new Growth OS must use
    # the same official Evidence truth ledger.
    parity = driver.execute_async_script("""
      const done=arguments[0];
      Promise.all([
        fetch('/api/r8-13/seo-geo',{cache:'no-store'}).then(r=>r.json()),
        fetch('/api/r8-24/geo-growth/fast',{cache:'no-store'}).then(r=>r.json())
      ]).then(([legacy,growth])=>done({
        legacy:Number((legacy.data||legacy).geo?.tested_questions||0),
        growth:Number((growth.data||growth).formal_ab_completed||0),
        source:String((legacy.data||legacy).geo?.truth_source||'')
      })).catch(error=>done({error:String(error)}));
    """)
    if parity.get("error"):
        raise AssertionError(f"GEO truth parity request failed: {parity['error']}")
    if parity.get("growth", 0) > 0:
        if parity.get("legacy") != parity.get("growth") or parity.get("source") != "r8-19-official-evidence":
            raise AssertionError(f"GEO official truth mismatch: {parity}")
    elif parity.get("source") not in {"r8-19-official-evidence", "r8-13-legacy-observation"}:
        raise AssertionError(f"GEO truth source is unknown when no formal Evidence exists: {parity}")




def assert_geo_advanced(driver):
    # Run the heavy advanced Evidence/browser tool check after the complete
    # sidebar pass. This proves the tool works without letting its background
    # browser modules distort the timing of unrelated navigation checks.
    click_route(driver, "r813-seo-geo")
    geo_tab = WebDriverWait(driver, 10).until(
        lambda d: d.find_element(By.CSS_SELECTOR, '#r813-seo-geo [data-r813-workspace="geo"]')
        if d.find_elements(By.CSS_SELECTOR, '#r813-seo-geo [data-r813-workspace="geo"]')
        else None
    )
    driver.execute_script("arguments[0].click();", geo_tab)
    WebDriverWait(driver, 8).until(
        lambda d: d.find_elements(By.ID, "geo-growth-os") and d.find_element(By.ID, "geo-growth-os").is_displayed()
    )

    advanced = driver.find_element(By.ID, "geo-growth-advanced")
    summary = advanced.find_element(By.TAG_NAME, "summary")
    driver.execute_script("arguments[0].click();", summary)
    advanced_frame = WebDriverWait(driver, 12).until(
        lambda d: d.find_element(By.ID, "r813-geo-frame")
        if d.find_elements(By.ID, "r813-geo-frame") and d.find_element(By.ID, "r813-geo-frame").is_displayed()
        else None
    )
    driver.switch_to.frame(advanced_frame)
    try:
        WebDriverWait(driver, 15).until(
            lambda d: d.execute_script("return document.documentElement.dataset.kzGeoAdvancedReady === '1'")
        )
        inner_advanced = driver.find_element(By.ID, "geo-growth-advanced")
        if not inner_advanced.get_attribute("open"):
            raise AssertionError("高级 GEO Evidence 工具没有真正展开")
        fallback = driver.find_element(By.ID, "geo-direct-fallback")
        if fallback.is_displayed():
            raise AssertionError("高级 GEO 工具仍停留在初始化 fallback")
        if driver.find_element(By.ID, "geo-growth-os").is_displayed():
            raise AssertionError("高级工具 iframe 错误重复显示 GEO 主核心面板")
    finally:
        driver.switch_to.default_content()

    if not driver.find_element(By.ID, "geo-growth-os").is_displayed():
        raise AssertionError("高级 GEO 工具展开影响了主平台核心面板")

    # A user must still be able to leave GEO with one click after the advanced
    # iframe is live. This catches navigation ownership regressions explicitly.
    click_route(driver, "dashboard")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args()

    url = f"http://127.0.0.1:{args.port}/index.html?sidebar-field-smoke=1"
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-background-networking")
    options.add_argument("--disable-extensions")
    options.add_argument("--no-first-run")
    options.add_argument("--window-size=1800,1200")

    driver = webdriver.Chrome(options=options)
    results = []
    try:
        # Reproduce a slower field PC/browser instead of validating only on a
        # fast clean GitHub runner. Owner navigation must still converge.
        try:
            driver.execute_cdp_cmd("Emulation.setCPUThrottlingRate", {"rate": 4})
        except Exception:
            pass
        driver.set_page_load_timeout(25)
        driver.get(url)
        wait = WebDriverWait(driver, 20)
        wait.until(lambda d: d.find_elements(By.CSS_SELECTOR, ".r810-primary-nav .r810-nav-button"))
        wait.until(
            lambda d: d.execute_script(
                "return ['ready','degraded'].includes(document.documentElement.dataset.kzStartupPhase || '')"
            )
        )
        direct_shells = driver.execute_script(
            "return {content: typeof window.openKazuizhiContentStudio === 'function', geo: !!window.KZR813SeoGeoBridge?.open, geoCore: typeof window.__KZ_GEO_GROWTH_OS_BOOT__ === 'function'};"
        )
        if not direct_shells.get("content") or not direct_shells.get("geo") or not direct_shells.get("geoCore"):
            raise AssertionError(f"owner route shells were not loaded directly: {direct_shells}")

        driver.execute_script("""
          const originalFetch = window.fetch.bind(window);
          window.fetch = (input, init) => {
            const url = String(input && input.url ? input.url : input || '');
            if (/content-studio-shell\\.js|content-pipeline-host\\.js|r8_13_seo_geo_bridge\\.js/.test(url)) {
              return Promise.reject(new Error('field-smoke: dynamic owner-shell fetch blocked'));
            }
            return originalFetch(input, init);
          };
        """)

        for label, target in PRIMARY_ROUTES:
            started = time.monotonic()
            click_route(driver, target)
            if target == "content-studio":
                assert_content_studio(driver)
            elif target == "operational-hub":
                assert_execution_center(driver)
            elif target == "r813-seo-geo":
                assert_seo_geo(driver)
            elapsed = round(time.monotonic() - started, 2)
            results.append({"label": label, "target": target, "seconds": elapsed, "ok": True})

        for label, target, action in SECONDARY_ROUTES:
            started = time.monotonic()
            try:
                click_route(driver, target, action=action)
            except Exception as error:
                active = driver.execute_script("return [...document.querySelectorAll('main > .page.active')].map(x=>x.id);")
                raise AssertionError(f"左侧导航失败：{label} -> {target}/{action or 'normal'}；当前活动页={active}") from error
            elapsed = round(time.monotonic() - started, 2)
            results.append({"label": label, "target": target, "action": action, "seconds": elapsed, "ok": True})

        assert_geo_advanced(driver)
        results.append({"label": "GEO高级证据工具", "target": "r813-seo-geo", "seconds": 0, "ok": True})
        results.append({"label": "高级GEO后返回老板总控", "target": "dashboard", "seconds": 0, "ok": True})

        expected = {x[1] for x in PRIMARY_ROUTES} | {x[1] for x in SECONDARY_ROUTES}
        tested = {row["target"] for row in results}
        if not expected.issubset(tested):
            raise AssertionError(f"sidebar routes not fully exercised: {sorted(expected - tested)}")

        # No route should leave the shell without exactly one active owner page.
        active_pages = driver.find_elements(By.CSS_SELECTOR, "main > .page.active")
        if len(active_pages) != 1:
            raise AssertionError(f"owner shell ended with {len(active_pages)} active pages instead of exactly one")

        print("PASS: real Chrome clicked every owner sidebar route and every destination responded")
        print(json.dumps({"ok": True, "url": url, "results": results}, ensure_ascii=True))
    finally:
        driver.quit()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"FAIL: owner sidebar Chrome field smoke: {exc}", file=sys.stderr)
        raise
