import datetime
import os
import ssl
import platform
import pytz
from datetime import *
from dateutil.tz import *

import pymongo
from selenium import webdriver
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities

caps = DesiredCapabilities().CHROME
caps["pageLoadStrategy"] = "normal"

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
timeZoneName = datetime.now(tzlocal()).tzname()
if (timeZoneName == 'Coordinated Universal Time'):
    timeZoneName = 'UTC'

constants = {
    'min_idea_threshold': 200,
    'max_tweets': 5000,
    'hoursBackToAnalyze': 0.1,
    'project_root': project_root,
    'driver_bin': driver_bin,
    'chrome_options': chrome_options,
    'caps': caps,
    'scroll_pause_time': 5,
    'alpha_vantage_api_key':'URK33PG7JX4SFFXH',
    'db_client': pymongo.MongoClient("mongodb+srv://lijeffrey39:test@cluster0"
                                     "-qthez.mongodb.net/test?retryWrites=true"
                                     "&w=majority",
                                     ssl_cert_reqs=ssl.CERT_NONE),
    'db_user_client': pymongo.MongoClient("mongodb+srv://lijeffrey39:test@"
                                          "cluster0-mlfxz.mongodb.net/test?"
                                          "retryWrites=true&w=majority",
                                          ssl_cert_reqs=ssl.CERT_NONE),
    'stocktweets_client': pymongo.MongoClient("mongodb+srv://lijeffrey39:"
                                              "test@cluster0-0x7lu."
                                              "mongodb.net/test?retryWrites"
                                              "=true&w=majority",
                                              ssl_cert_reqs=ssl.CERT_NONE),
    'messageStreamAttr': 'st_2o0zabc',
    'timeAttr': 'st_2q3fdlM',
    'messageTextAttr': 'st_29E11sZ',
    'ideaAttr': 'st__tZJhLh',
    'likeCountAttr': 'st_1tZ744c',
    'current_timezone': timeZoneName,
    'eastern_timezone': pytz.timezone('US/Eastern'),
    'keys': ['bullReturns', 'bearReturns', 'returnRatio', 'bullCount',
             'bearCount', 'countRatio', 'UBullReturns', 'UBearReturns',
             'UReturnRatio', 'UBullCount', 'UBearCount', 'UCountRatio',
             'totalLabeledTweets', 'totalLabeledTweetsUsed', 
             'UtotalLabeledTweetsUsed'],

    'html_class_user_div': 'st_CFwNYeI st_jGV698i st_PLa30pM',
    'html_class_user_info': 'st_21r0FbC st_2fTou_q',
    'html_class_plus': 'st_2ceteac st_8u0ePN3',
    'html_class_official': 'st_15f6hU9 st_2Y5n_y3',
    'html_class_premium_room': 'st_3ZUModE st_2fTou_q'
}
