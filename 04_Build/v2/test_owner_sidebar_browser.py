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
    geo_frame = WebDriverWait(driver, 10).until(
        lambda d: d.find_element(By.ID, "r813-geo-frame")
        if d.find_elements(By.ID, "r813-geo-frame") and d.find_element(By.ID, "r813-geo-frame").is_displayed()
        else None
    )
    driver.switch_to.frame(geo_frame)
    try:
        growth = WebDriverWait(driver, 10).until(
            lambda d: d.find_element(By.ID, "geo-growth-os")
            if d.find_elements(By.ID, "geo-growth-os") and d.find_element(By.ID, "geo-growth-os").is_displayed()
            else None
        )
        if not growth.is_displayed():
            raise AssertionError("集成 GEO 工作台存在但不可见")
        fallback = driver.find_element(By.ID, "geo-direct-fallback")
        if driver.execute_script("return getComputedStyle(arguments[0]).display", fallback) != "none":
            raise AssertionError("集成 GEO 仍停留在 fallback/初始化壳")
    finally:
        driver.switch_to.default_content()


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
            "return {content: typeof window.openKazuizhiContentStudio === 'function', geo: !!window.KZR813SeoGeoBridge?.open};"
        )
        if not direct_shells.get("content") or not direct_shells.get("geo"):
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
            click_route(driver, target, action=action)
            elapsed = round(time.monotonic() - started, 2)
            results.append({"label": label, "target": target, "action": action, "seconds": elapsed, "ok": True})

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
