import os
import datetime
from . import scroll
from .fileIO import *
from .stockPriceAPI import *
from .messageExtract import *
from bs4 import BeautifulSoup
from .hyperparameters import constants

from selenium.common.exceptions import TimeoutException
from selenium import webdriver

from .helpers import addToFailedList


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



def getBearBull(symbol, date, soup):
    savedSymbolHistorical = []
    try:
        savedSymbolHistorical = get_historical_intraday(symbol, date, token = "pk_55ae0f09f54547eaaa2bd514cf3badc6")
    except:
        return []

    messages = soup.find_all('div', attrs={'class': messageStreamAttr})
    res = []

    print(len(messages))
    for m in messages:
        t = m.find('div', {'class': timeAttr})
        t = t.find_all('a') # length of 2, first is user, second is date
        if (t == None):
            continue

        allT = m.find('div', {'class': messageTextAttr})
        allText = allT.find_all('div')
        dateTime = findDateTime(t[1].text)
        user = findUser(t[0])
        textFound = allText[1].find('div').text
        cleanText = ' '.join(removeSpecialCharacters(textFound).split())
        isBull = isBullMessage(m)

        # print(cleanText, user, dateTime)

        if (isValidMessage(dateTime, date, isBull, user, symbol, 0) == False):
            continue

        foundAvg = priceAtTime(dateTime, savedSymbolHistorical) # fix this function to take dateTimeadjusted

        messageInfo = [user, isBull, dateTime, foundAvg, cleanText]
        res.append(messageInfo)

    return res
