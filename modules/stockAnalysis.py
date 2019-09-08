import datetime
import os

from selenium import webdriver
from selenium.common.exceptions import TimeoutException

from bs4 import BeautifulSoup

from . import scroll
from .fileIO import *
from .helpers import convertToEST
from .hyperparameters import constants
from .messageExtract import *
from .stockPriceAPI import *
import time

# ------------------------------------------------------------------------
# ----------------------------- Variables --------------------------------
# ------------------------------------------------------------------------


timeAttr = 'st_2q3fdlM'
messageTextAttr = 'st_29E11sZ'


# ------------------------------------------------------------------------
# ----------------------------- Functions --------------------------------
# ------------------------------------------------------------------------


# Return soup object page of that stock
def findPageStock(symbol, date, hoursBack):
    driver = None
    try:
        driver = webdriver.Chrome(executable_path=constants['driver_bin'],
                                  options=constants['chrome_options'],
                                  desired_capabilities=constants['caps'])
        driver.set_page_load_timeout(90)
    except Exception as e:
        print(e)
        return ('', str(e), 0)

    error_message = ''
    start = time.time()
    url = "https://stocktwits.com/symbol/%s" % symbol

    # Handling exceptions and random shit
    try:
        driver.get(url)
    except Exception as e:
        end = time.time()
        driver.quit()
        print(e)
        return ('', str(e), end - start)

    try:
        scroll.scrollFor(driver, hoursBack)
    except Exception as e:
        driver.quit()
        end = time.time()
        print(e)
        return ('', str(e), end - start)

    html = driver.page_source
    soup = BeautifulSoup(html, 'html.parser')
    end = time.time()
    print('Parsing user took %d seconds' % (end - start))
    driver.quit()
    return (soup, error_message, (end - start))


def parseStockData(symbol, soup):
    res = []
    messages = soup.find_all('div', 
                             attrs={'class': constants['messageStreamAttr']})

    # want to add new users to users_not_analyzed table
    for m in messages:
        t = m.find('div', {'class': timeAttr}).find_all('a')
        # length of 2, first is user, second is date
        if (t is None):
            continue

        allT = m.find('div', {'class': messageTextAttr})
        allText = allT.find_all('div')
        username = findUser(t[0])
        textFound = allText[1].find('div').text  # No post processing
        isBull = isBullMessage(m)
        likeCnt = likeCount(m)
        commentCnt = commentCount(m)

        # need to convert to EDT time zone
        dateTime = findDateTime(t[1].text)
        if (username is None or dateTime is None):
            continue

        dateTime = convertToEST(dateTime)

        cur_res = {}
        cur_res['symbol'] = symbol
        cur_res['user'] = username
        cur_res['time'] = dateTime.strftime("%Y-%m-%d %H:%M:%S")
        cur_res['isBull'] = isBull
        cur_res['likeCount'] = likeCnt
        cur_res['commentCount'] = commentCnt
        cur_res['messageText'] = textFound
        cur_res['date'] = dateTime.strftime("%Y-%m-%d")

        res.append(cur_res)
    return res
