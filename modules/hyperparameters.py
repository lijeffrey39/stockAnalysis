import datetime
import os
import ssl
import platform
import pytz
from datetime import *
from dateutil.tz import *

import pymongo
from selenium import webdriver

chrome_options = webdriver.ChromeOptions()
prefs = {"profile.managed_default_content_settings.images": 2}
chrome_options.add_experimental_option("prefs", prefs)
chrome_options.add_experimental_option("prefs", prefs)
chrome_options.add_argument("--headless")
chrome_options.add_argument('log-level=3')
chrome_options.add_argument("--disable-extensions")
chrome_options.add_argument('disable-infobars')
chrome_options.add_argument('--disable-gpu')
chrome_options.add_argument('start-maximized')
# chrome_options.add_argument('--no-sandbox')

chrome_driver_name = 'chromedriver' if (platform.system() == "Darwin") else 'chromedriver.exe'
project_root = os.getcwd()
driver_bin = os.path.join(project_root, chrome_driver_name)
constants = {
    'min_idea_threshold': 150,
    'max_tweets': 600,
    'project_root': project_root,
    'driver_bin': driver_bin,
    'chrome_options': chrome_options,
    'scroll_pause_time': 2,
    'alpha_vantage_api_key': 'K8CFYSOMVFPGSXTM',
    'db_client': pymongo.MongoClient("mongodb+srv://lijeffrey39:test@cluster0"
                                     "-qthez.mongodb.net/test?retryWrites=true"
                                     "&w=majority",
                                     ssl_cert_reqs=ssl.CERT_NONE),
    'db_user_client': pymongo.MongoClient("mongodb+srv://lijeffrey39:test@"
                                          "cluster0-mlfxz.mongodb.net/test?"
                                          "retryWrites=true&w=majority",
                                          ssl_cert_reqs=ssl.CERT_NONE),
    'messageStreamAttr': 'st_2o0zabc',
    'current_timezone': datetime.now(tzlocal()).tzname()
    'eastern_timezone': pytz.timezone('US/Eastern')
}
