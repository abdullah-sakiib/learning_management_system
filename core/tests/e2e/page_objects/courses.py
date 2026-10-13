from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC

from .base import BasePage


class CourseDetailPage(BasePage):
    def enroll(self, course_id):
        self.open(f"/courses/{course_id}/")
        button = self.wait.until(EC.element_to_be_clickable((By.XPATH, "//button[@type='submit' and contains(., 'Enroll')]")))
        button.click()
        self.wait.until(EC.url_contains(f"/courses/{course_id}/"))
        self.wait.until(lambda driver: "Enroll Now" not in driver.page_source)
        return self


class QuizTakePage(BasePage):
    def submit_answer(self, quiz_id, question_id, value):
        self.open(f"/quiz/{quiz_id}/take/")
        answer = self.wait.until(
            EC.element_to_be_clickable(
                (By.CSS_SELECTOR, f'input[name="answer_{question_id}"][value="{value}"]')
            )
        )
        answer.click()
        self.browser.find_element(By.XPATH, "//button[@type='submit' and contains(., 'Submit Quiz')]").click()
        self.wait.until(EC.url_contains(f"/quiz/{quiz_id}/take/"))
        self.wait.until(lambda driver: "Submit Quiz" not in driver.page_source)
        return self

