from selenium import webdriver
import platform
import os
import pymongo 

chrome_options = webdriver.ChromeOptions()
prefs = {"profile.managed_default_content_settings.images": 2}
chrome_options.add_experimental_option("prefs", prefs)
chrome_options.add_experimental_option("prefs", prefs)
# chrome_options.add_argument("--headless")
# chrome_options.add_argument('log-level=3')
chrome_options.add_argument("--disable-extensions")
chrome_options.add_argument('disable-infobars')
chrome_options.add_argument('--disable-gpu')
chrome_options.add_argument('start-maximized')
chrome_options.add_argument('--no-sandbox')

chrome_driver_name = 'chromedriver' if (platform.system() == "Darwin") else 'chromedriver.exe'
project_root = os.getcwd()
driver_bin = os.path.join(project_root, chrome_driver_name)
constants = {
    'min_idea_threshold': 100,
    'max_tweets': 360,
    'project_root': project_root,
    'driver_bin': driver_bin,
    'chrome_options': chrome_options,
    'scroll_pause_time': 2,
    'alpha_vantage_api_key': 'K8CFYSOMVFPGSXTM', 
    'db_client' : pymongo.MongoClient("mongodb+srv://lijeffrey39:test@cluster0-qthez.mongodb.net/test?retryWrites=true&w=majority"),
}
