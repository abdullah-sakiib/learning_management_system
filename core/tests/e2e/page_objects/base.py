from selenium.webdriver.support.ui import WebDriverWait


class BasePage:
    def __init__(self, browser, base_url):
        self.browser = browser
        self.base_url = base_url.rstrip("/")
        self.wait = WebDriverWait(browser, 10)

    def open(self, path):
        self.browser.get(f"{self.base_url}{path}")
        return self
