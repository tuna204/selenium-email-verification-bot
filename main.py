import csv
import os
import random
import time
import requests
import string
import re

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains


def generate_temp_email():
    domain_resp = requests.get("https://api.mail.tm/domains")
    domains = domain_resp.json()["hydra:member"]
    domain = domains[0]["domain"]

    username = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
    password = "Password123!"
    email = f"{username}@{domain}"

    register = requests.post("https://api.mail.tm/accounts", json={
        "address": email,
        "password": password
    })

    if register.status_code != 201:
        print("❌ Failed to create temp mail")
        return None, None, None

    token_resp = requests.post("https://api.mail.tm/token", json={
        "address": email,
        "password": password
    })

    token = token_resp.json()["token"]
    print(f"📧 Temp mail created: {email}")

    # Save used email
    with open("used_emails.csv", "a", newline='') as f:
        writer = csv.writer(f)
        writer.writerow([email])

    return email, token, username


def get_verification_code(token):
    headers = {"Authorization": f"Bearer {token}"}
    for attempt in range(30):
        print(f"⏳ Checking inbox... Attempt {attempt + 1}")
        try:
            resp = requests.get("https://api.mail.tm/messages", headers=headers, timeout=10)
            items = resp.json().get("hydra:member", [])
            if items:
                msg_id = items[0]["id"]
                msg = requests.get(f"https://api.mail.tm/messages/{msg_id}", headers=headers).json()
                body = msg.get("text") or msg.get("html") or ""
                print("📨 Raw message fetched.")

                if "<html" in body.lower():
                    soup = BeautifulSoup(body, "html.parser")
                    body = soup.get_text(separator=" ")

                print(f"📨 Mail received:\n{body}")

                match = re.search(r"\b\d{6}\b", body)
                if match:
                    code = match.group(0)
                    print(f"✅ OTP extracted: {code}")
                    return code
                else:
                    print("❌ OTP not found in email.")
        except Exception as e:
            print(f"❌ Error fetching email: {e}")
        time.sleep(3)
    return None

def generate_random_name():
    first_names = ["John", "James", "Michael", "Daniel", "David", "Chris", "Robert", "Brian"]
    last_names = ["Doe", "Smith", "Johnson", "Brown", "Williams", "Miller", "Taylor", "Clark"]
    first = random.choice(first_names)
    last = random.choice(last_names)
    return first, last

def generate_random_zip():
    zip_codes = ["10001", "90210", "30301", "60601"]  # You can add more like "30301", "60601"
    return random.choice(zip_codes)


def cast_vote():
    email, token, username = generate_temp_email()
    if not email:
        return None, "email_failed"

    options = Options()
    options.add_argument("--start-maximized")
    options.add_argument("--disable-blink-features=AutomationControlled")

    driver = webdriver.Chrome(options=options)
    wait = WebDriverWait(driver, 30)

    try:
        print("🌐 Opening page...")
        driver.get("https://voteei.com/tbitw/burggraf-roofing")
        driver.implicitly_wait(30)

        try:
            modal = driver.find_element(By.CLASS_NAME, "modal-content")
            driver.execute_script("arguments[0].remove();", modal)
        except:
            pass

        buttons = driver.find_elements(By.CSS_SELECTOR, "div.cvp-category button")
        for btn in buttons[:3]:
            ActionChains(driver).move_to_element(btn).click().perform()
            time.sleep(0.5)

        vote_btn = wait.until(EC.element_to_be_clickable((By.CLASS_NAME, "ballotButton")))
        ActionChains(driver).move_to_element(vote_btn).click().perform()
        print("✅ Vote casted.")

        inputs = driver.find_elements(By.CSS_SELECTOR, "input.o-input")
        if len(inputs) >= 5:
            first_name, last_name = generate_random_name()
            inputs[0].send_keys(first_name)
            inputs[1].send_keys(last_name)
            inputs[2].send_keys("1234567890")
            zip_code = generate_random_zip()
            inputs[3].send_keys(zip_code)
            inputs[4].send_keys(email)
            print("✍️ Form filled.")

        verify_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//span[normalize-space()='Verify']/ancestor::button")))
        ActionChains(driver).move_to_element(verify_btn).click().perform()
        print("✅ Verify button clicked.")

        code = get_verification_code(token)
        if not code:
            print("❌ No verification code.")
            return email, "no_code"

        print(f"🔍 Entering OTP: {code}")

        otp_inputs = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "input.o-input[type='text']")))
        if len(otp_inputs) >= 2:
            otp_input = otp_inputs[1]
            ActionChains(driver).move_to_element(otp_input).click().perform()
            otp_input.clear()
            time.sleep(0.5)

            for digit in code:
                ActionChains(driver).send_keys(digit).perform()
                time.sleep(0.2)

            driver.execute_script("""
                const input = arguments[0];
                ['input', 'change'].forEach(type => {
                    input.dispatchEvent(new Event(type, { bubbles: true }));
                });
            """, otp_input)
            print("✅ OTP entered and events dispatched.")
        else:
            print("❌ OTP input not found.")
            return email, "otp_input_not_found"

        # Submit the OTP
        submit_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//span[normalize-space()='Submit Code']/ancestor::button")))
        driver.execute_script("arguments[0].scrollIntoView(true);", submit_btn)
        time.sleep(1)
        driver.execute_script("arguments[0].click();", submit_btn)
        print("✅ Submit button clicked.")

        # Confirm submission
        try:
            confirmation = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Thank you for your vote')]"))
            )
            print("🎉 Confirmation detected!")
            return email, "success"
        except:
            print("⚠️ Submitted but no visible confirmation.")
            return email, "submitted_no_visible_msg"

    except Exception as e:
        print("🚫 Error:", e)
        return email, "error"

    finally:
        driver.quit()


# ==== Main Execution ====
results = []

for _ in range(50):
    result = cast_vote()
    if result:
        results.append(result)
    time.sleep(random.randint(2, 5))

with open("vote_results.csv", "w", newline='') as f:
    writer = csv.writer(f)
    writer.writerow(["Email", "Status"])
    writer.writerows(results)

print("✅ All votes processed.")
