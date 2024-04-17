import pytest
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By

@pytest.fixture(scope="function")
def load_user_data(django_db_setup, django_db_blocker):
    from django.core.management import call_command
    with django_db_blocker.unblock():
        call_command('loaddata', 'warehouse/dashboard/fixtures/db_admin_fixture.json')


@pytest.mark.selenium
def test_dashboard_admin_login(live_server, load_user_data, chrome_browser_instance):
    browser = chrome_browser_instance
    browser.get(f"{live_server.url}/admin/login/")  # Using an f-string for better readability
    
    username_input = browser.find_element(By.NAME, "username")
    password_input = browser.find_element(By.NAME, "password")
    submit_button = browser.find_element(By.XPATH, '//input[@value="Log in"]')
    
    username_input.send_keys("a@a.com")  # User email from the fixture
    password_input.send_keys("password")  # Assuming 'password' is the correct password
    submit_button.click()
    
    assert "Site administration" in browser.page_source
