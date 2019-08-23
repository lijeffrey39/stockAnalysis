import datetime
import os

from selenium import webdriver
from selenium.common.exceptions import TimeoutException

from bs4 import BeautifulSoup

from . import scroll
from .fileIO import *
from .helpers import addToFailedList
from .hyperparameters import constants
from .messageExtract import *
from .stockPriceAPI import *


# ------------------------------------------------------------------------
# ----------------------------- Variables --------------------------------
# ------------------------------------------------------------------------


messageStreamAttr = 'st_2o0zabc'
timeAttr = 'st_2q3fdlM'
messageTextAttr = 'st_29E11sZ'


# ------------------------------------------------------------------------
# ----------------------------- Functions --------------------------------
# ------------------------------------------------------------------------


# Return soup object page of that stock
def findPageStock(symbol):
    driver = None
    try:
        driver = webdriver.Chrome(executable_path = constants['driver_bin'], options = constants['chrome_options'])
        driver.set_page_load_timeout(45)
    except Exception as e:
        return ('', e, 0)

    dateNow = datetime.datetime.now()
    datePrev = datetime.datetime(dateNow.year, dateNow.month, dateNow.day)
    hoursBack = ((dateNow - datePrev).total_seconds / 3600.0) + 1

    error_message = ''
    start = time.time()
    url = "https://stocktwits.com/symbol/" + symbol

    # Handling exceptions and random shit
    try:
        driver.get(url)
    except:
        end = time.time()
        driver.quit()
        return ('', e, end - start)

    try:
          scroll.scrollFor(driver, hoursBack)
    except:
        driver.quit()
        end = time.time()
        return ('', e, end - start)

    html = driver.page_source
    soup = BeautifulSoup(html, 'html.parser')
    end = time.time()
    print('Parsing user took %d seconds' % (end - start))
    driver.quit()
    return (soup, error_message, (end - start))


def parseStockData(symbol, soup):
    res = []
    messages = soup.find_all('div', attrs={'class': messageStreamAttr})

    # want to add new users to users_not_analyzed table
    for m in messages:
        t = m.find('div', {'class': timeAttr}).find_all('a')
        # length of 2, first is user, second is date
        if (t == None):
            continue

        allT = m.find('div', {'class': messageTextAttr})
        allText = allT.find_all('div')
        dateTime = findDateTime(t[1].text)
        username = findUser(t[0])
        textFound = allText[1].find('div').text
        cleanText = ' '.join(removeSpecialCharacters(textFound).split())
        isBull = isBullMessage(m)

        likeCnt = likeCount(m)
        commentCnt = commentCount(m)

        if (isValidMessage(dateTime, date, isBull, user, symbol, 0) == False):
            continue

        cur_res = {}
        cur_res['symbol'] = symbol
        cur_res['user'] = username
        cur_res['time'] = dateTime.strftime("%Y-%m-%d %H:%M:%S")
        cur_res['isBull'] = isBull
        cur_res['likeCnt'] = likeCnt
        cur_res['commentCnt'] = commentCnt
        cur_res['cleanText'] = cleanText

        res.append(cur_res)

    return res
