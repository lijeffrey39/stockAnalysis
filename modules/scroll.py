import datetime
import time
import sys

from dateutil.parser import parse
from iexfinance.stocks import get_historical_intraday
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys

from bs4 import BeautifulSoup

from .fileIO import *
from .helpers import convertToEST
from .hyperparameters import constants
from .messageExtract import findDateTime, findDateFromMessage


# ------------------------------------------------------------------------
# ----------------------------- Functions --------------------------------
# ------------------------------------------------------------------------


# Scroll for # days
def scrollFor(driver, hoursBack):
    currTime = convertToEST(datetime.datetime.now())
    hoursBack += 0.5 # Just to be safe
    compareTime = currTime - datetime.timedelta(hours=hoursBack)
    last_height = ""
    prevTime = None
    countSame = 0
    count = 0

    while(True):
        now = convertToEST(datetime.datetime.now())
        if now.hour == 15 and now.minute == 20:
            print('bye bye')
            sys.exit()
        new_height = driver.execute_script("return document.body.scrollHeight")
        time.sleep(constants['scroll_pause_time'])

        messages = driver.find_elements_by_class_name(constants['messageStreamAttr'])
        print(len(messages))
        if (len(messages) > constants['max_tweets']):
            break

        if (len(messages) == 0):
            raise Exception('Len of messages was 0 ???')

        (currTime, errorMsg) = findDateFromMessage(messages[len(messages) - 1])
        if (errorMsg != ""):
            raise Exception(errorMsg)

        print(count, currTime, compareTime)
        if (currTime < compareTime):
            break

        if (prevTime == currTime):
            countSame += 1
        else:
            countSame = 0
            prevTime = currTime

        # If scrolled on the same one, reached end of page
        if (countSame == 10):
            return True
            # raise Exception('Scroll for too long')

        last_height = new_height
        driver.execute_script("window.scrollTo(0,document.body.scrollHeight);")
        count += 1

    print("Finished Reading")
    return True
