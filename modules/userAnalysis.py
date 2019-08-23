import os
import datetime
import requests
import time
import datetime

from .hyperparameters import constants

from . import scroll

from .fileIO import *
from .stockPriceAPI import *
from .messageExtract import *

from bs4 import BeautifulSoup

from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException

from .helpers import addToFailedList


# ------------------------------------------------------------------------
# ----------------------------- Variables --------------------------------
# ------------------------------------------------------------------------


# TODO
# Invalid symbols so they aren't check again
invalidSymbols = []
messageStreamAttr = 'st_1m1w96g'
timeAttr = 'st_2q3fdlM'
messageTextAttr = 'st_29E11sZ'
ideaAttr = 'st__tZJhLh'


# ------------------------------------------------------------------------
# ----------------------------- Functions --------------------------------
# ------------------------------------------------------------------------



# Return soup object page of that user
def findPageUser(username):
    driver = None
    try:
        driver = webdriver.Chrome(executable_path = constants['driver_bin'], options = constants['chrome_options'])
		driver.set_page_load_timeout(45)
    except Exception as e:
        return ('', e, end-start)

    driver.set_page_load_timeout(45)
    start_date = datetime.datetime(2019, 7, 22)
    current_date = datetime.datetime.now()
    date_span = current_date - start_date
    current_span_hours = 24 * date_span.days + int(date_span.seconds/3600)
    error_message = ''
    start = time.time()
    url = 'https://stocktwits.com/%s'%username
    try:
        driver.get(url)
    except Exception as e:
        print("Timed Out from findPageUser")
        end = time.time()
        driver.quit()
        return ('', e, end - start)

    try:
        scroll.scrollFor(driver, 10)
    except Exception as e:
        driver.quit()
        end = time.time()
        return ('', e, end - start)

    html = driver.page_source
    soup = BeautifulSoup(html, 'html.parser')
    end = time.time()
    print('Parsing user took %d seconds' % (end - start))
    driver.quit()
    return (soup, error_message, (end - start))


# First write to userCalculated, then write to newUserInfo.csv
def saveUserToCSV(username, result, otherInfo):
    res = []
    read = list(filter(lambda x: x[5] != -1, result))
    symbols = list(set(map(lambda x: x[0], read)))
    total = float(len(read))

    for s in symbols:
        filterSymbol = list(filter(lambda x: x[0] == s, read))
        totalCorrect = list(map(lambda x: abs(float(x[7])), list(filter(lambda x: x[5] == 1, filterSymbol))))
        totalIncorrect = list(map(lambda x: abs(float(x[7])), list(filter(lambda x: x[5] == 0, filterSymbol))))
        summedCorrect = reduce(lambda a, b: a + b, totalCorrect) if len(totalCorrect) > 0 else 0
        summedIncorrect = reduce(lambda a, b: a + b, totalIncorrect) if len(totalIncorrect) > 0 else 0
        res.append([s, round(100 * len(filterSymbol) / total, 2), len(totalCorrect),
            len(totalIncorrect), round(summedCorrect - summedIncorrect, 2)])

    res.sort(key = lambda x: x[4], reverse = True)
    writeSingleList('newUserCalculated/' + username + '_info.csv', res)

    resNewUserInfo = []
    if (len(res) == 0):
        resNewUserInfo = [username, 0, 0, 0.0]
    else:
        totalReturn = round(reduce(lambda a, b: a + b, list(map(lambda x: x[4], res))), 4)
        correct = round(reduce(lambda a, b: a + b, list(map(lambda x: x[2], res))), 4)
        incorrect = round(reduce(lambda a, b: a + b, list(map(lambda x: x[3], res))), 4)
        resNewUserInfo = [username, correct, incorrect, totalReturn]

    resNewUserInfo.extend(otherInfo)
    currNewUserInfo = readMultiList('newUserInfo.csv')
    currNewUserInfo.append(resNewUserInfo)
    currNewUserInfo.sort(key = lambda x: float(x[3]), reverse = True)
    writeSingleList('newUserInfo.csv', currNewUserInfo)


# Gets initial information for user 
def findUserInfo(username):
    response = requests.get(url='https://api.stocktwits.com/api/2/streams/user/%s.json' % username)
    try:
        info = response.json()['user']
    except KeyError:
        return None
    user_info_dict = dict()
    fields = {'join_date', 'followers', 'following', 'ideas', 'like_count'}
    for f in fields:
        user_info_dict[f] = info[f]
    return user_info_dict


def parseUserData(username, soup):
	res = []
    messages = soup.find_all('div', attrs={'class': messageStreamAttr})
    for m in messages:
        t = m.find('div', {'class': timeAttr}).find_all('a') 
		# t must be length of 2, first is user, second is date
        if (t == None):
            continue

        allT = m.find('div', {'class': messageTextAttr})
        allText = allT.find_all('div')
		messageTextView = allText[1]
        dateTime = findDateTime(t[1].text)
        textFound = messageTextView.find('div').text
        cleanText = ' '.join(removeSpecialCharacters(textFound).split())
        isBull = isBullMessage(m)

        symbol = findSymbol(messageTextView)
        likeCnt = likeCount(m)
        commentCnt = commentCount(m)

		cur_res = {}
        cur_res['user'] = username
        cur_res['symbol'] = symbol
        cur_res['time'] = dateTime.strftime("%Y-%m-%d %H:%M:%S")
        cur_res['isBull'] = isBull
        cur_res['likeCnt'] = likeCnt
        cur_res['commentCnt'] = commentCnt
        cur_res['cleanText'] = cleanText
        res.append(cur_res)

    return res
