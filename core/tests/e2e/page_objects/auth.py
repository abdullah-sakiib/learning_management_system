from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC

from .base import BasePage


class LoginPage(BasePage):
    def login(self, identity, password):
        self.open("/login/")
        self.browser.find_element(By.ID, "email").send_keys(identity)
        self.browser.find_element(By.ID, "password").send_keys(password)
        self.browser.find_element(By.ID, "submit-btn").click()
        self.wait.until(lambda driver: "/dashboard/" in driver.current_url)
        return self


class RegistrationPage(BasePage):
    def register_student(self, *, first_name, last_name, email, password):
        self.open("/register/")
        self.browser.find_element(By.ID, "first_name").send_keys(first_name)
        self.browser.find_element(By.ID, "last_name").send_keys(last_name)
        self.browser.find_element(By.ID, "email").send_keys(email)
        self.browser.find_element(By.ID, "password1").send_keys(password)
        self.browser.find_element(By.ID, "password2").send_keys(password)
        self.browser.find_element(By.ID, "terms").click()
        self.browser.find_element(By.ID, "submit-btn").click()
        self.wait.until(EC.url_contains("/dashboard/student/"))
        return self
