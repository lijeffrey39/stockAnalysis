import datetime
import time

from dateutil.parser import parse
from iexfinance.stocks import get_historical_intraday
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys

from bs4 import BeautifulSoup

from .fileIO import *
from .helpers import addToFailedList, analyzedSymbolAlready
from .hyperparameters import constants
from .messageExtract import findDateTime

# ------------------------------------------------------------------------
# ----------------------------- Variables --------------------------------
# ------------------------------------------------------------------------


messageStreamAttr = 'st_2o0zabc'


# ------------------------------------------------------------------------
# ----------------------------- Functions --------------------------------
# ------------------------------------------------------------------------


def findLastTime(messages):
    lastMessage = messages[len(messages) - 1].text
    t = lastMessage.split('\n')
    if (t[0] == "Bearish" or t[0] == "Bullish"):
        dateTime = findDateTime(t[2])
        return dateTime
    else:
        dateTime = findDateTime(t[1])
        return dateTime


# Scroll for # days
def scrollFor(driver, hoursBack):
    currTime = datetime.datetime.now()
    oldTime = currTime - datetime.timedelta(hours = hoursBack)
    last_height = ""

    while(True):
        new_height = driver.execute_script("return document.body.scrollHeight")
        time.sleep(constants['scroll_pause_time'])

        messages = driver.find_elements_by_class_name(messageStreamAttr)
        if (len(messages) > constants['max_tweets']):
            break

        if (len(messages) == 0):
            raise Exception('Len of messages was 0 ???')

        currTime = findLastTime(messages)
        if (currTime == None):
            raise Exception('How did this happend')
        
        if (currTime < oldTime):
            break

        last_height = new_height
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")

    print("Finished Reading")
    return True
