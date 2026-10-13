import os
from pathlib import Path

import pytest
from selenium import webdriver


def pytest_addoption(parser):
    parser.addoption(
        "--run-selenium",
        action="store_true",
        default=False,
        help="Run browser-driven Selenium tests.",
    )


def pytest_collection_modifyitems(config, items):
    if config.getoption("--run-selenium"):
        return
    skip = pytest.mark.skip(reason="use --run-selenium to execute browser tests")
    for item in items:
        if "selenium" in item.keywords:
            item.add_marker(skip)


@pytest.fixture
def browser(request, tmp_path):
    browser_name = os.environ.get("STQA_BROWSER", "chrome").lower()
    headless = os.environ.get("STQA_HEADLESS", "false").lower() != "false"
    if browser_name == "edge":
        options = webdriver.EdgeOptions()
        if headless:
            options.add_argument("--headless=new")
        driver = webdriver.Edge(options=options)
    else:
        options = webdriver.ChromeOptions()
        if headless:
            options.add_argument("--headless=new")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1440,1000")
        options.add_experimental_option(
            "prefs",
            {"download.default_directory": str(tmp_path.resolve())},
        )
        driver = webdriver.Chrome(options=options)
    driver.set_window_size(1440, 1000)
    yield driver
    if hasattr(request.node, "rep_call") and request.node.rep_call.failed:
        evidence = Path("docs/stqa/evidence/selenium")
        evidence.mkdir(parents=True, exist_ok=True)
        driver.save_screenshot(str(evidence / f"{request.node.name}.png"))
    driver.quit()


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    setattr(item, f"rep_{report.when}", report)
