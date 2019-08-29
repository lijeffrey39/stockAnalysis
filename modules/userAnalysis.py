from datetime import *
from dateutil.tz import *
import os
import time
import pytz

import requests
from dateutil import parser
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys

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


# TODO: Invalid symbols so they aren't check again
timeAttr = 'st_2q3fdlM'
messageTextAttr = 'st_29E11sZ'
ideaAttr = 'st__tZJhLh'


# ------------------------------------------------------------------------
# ----------------------------- Functions --------------------------------
# ------------------------------------------------------------------------

def endDriver(driver):
    driver.close()
    driver.quit()


# Return soup object page of that user
def findPageUser(username):
    driver = None
    try:
        driver = webdriver.Chrome(executable_path=constants['driver_bin'],
                                  options=constants['chrome_options'])
        driver.set_page_load_timeout(45)
    except Exception as e:
        return ('', str(e), 0)

    driver.set_page_load_timeout(45)

    # Hardcoded to the first day we have historical stock data
    start_date = datetime.datetime(2019, 7, 22)
    current_date = datetime.datetime.now()
    date_span = current_date - start_date
    current_span_hours = 24 * date_span.days + int(date_span.seconds/3600)
    error_message = ''
    start = time.time()
    url = 'https://stocktwits.com/%s' % username
    try:
        driver.get(url)
    except Exception as e:
        print("Timed Out from findPageUser")
        end = time.time()
        endDriver(driver)
        return ('', str(e), end - start)

    messages = driver.find_elements_by_class_name(constants['messageStreamAttr'])
    if (len(messages) == 0):
        endDriver(driver)
        end = time.time()
        return ('', 'User has no tweets', end - start)

    try:
        scroll.scrollFor(driver, current_span_hours)
    except Exception as e:
        endDriver(driver)
        end = time.time()
        return ('', str(e), end - start)

    html = driver.page_source
    soup = BeautifulSoup(html, 'html.parser')
    end = time.time()
    print('Parsing user took %d seconds' % (end - start))
    endDriver(driver)
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


def parseKOrInt(s):
    if ('k' in s):
        num = float(s[:-1])
        return int(num * 1000)
    else:
        return int(s)


# Gets initial information for user from selenium
def findUserInfoDriver(username):
    driver = None
    try:
        driver = webdriver.Chrome(executable_path=constants['driver_bin'],
                                  options=constants['chrome_options'])
        driver.set_page_load_timeout(45)
    except Exception as e:
        endDriver(driver)
        return (None, str(e))

    driver.set_page_load_timeout(45)
    url = 'https://stocktwits.com/%s' % username
    try:
        driver.get(url)
    except Exception as e:
        endDriver(driver)
        return (None, str(e))

    user_info_dict = dict()
    html = driver.page_source
    soup = BeautifulSoup(html, 'html.parser')
    ideas = soup.find_all('h2', attrs={'class': ideaAttr})
    memberTextArray = soup.find_all('span', attrs={'class': 'st_21r0FbC st_2fTou_q'})

    if (len(ideas) == 0):
        endDriver(driver)
        return (None, "User doesn't exist")

    if (len(memberTextArray) >= 1):
        try:
            joinDateArray = memberTextArray[-1].text.split(' ')[2:]
            joinDate = ' '.join(map(str, joinDateArray))
            dateTime = parser.parse(joinDate).strftime("%Y-%m-%d")
            user_info_dict['join_date'] = dateTime
        except Exception as e:
            endDriver(driver)
            return (None, str(e))

    user_info_dict['ideas'] = parseKOrInt(ideas[0].text)
    user_info_dict['following'] = parseKOrInt(ideas[1].text)
    user_info_dict['followers'] = parseKOrInt(ideas[2].text)
    user_info_dict['like_count'] = parseKOrInt(ideas[3].text)

    endDriver(driver)
    return (user_info_dict, '')


# Gets initial information for user
def findUserInfo(username):
    response = requests.get(url='https://api.stocktwits.com/api/2/streams/user/%s.json' % username)

    # If exceed the 200 limited API calls
    try:
        responseStatus = response.json()['response']['status']
        if (responseStatus == 429):
            return {'ideas': -1}
    except KeyError:
        return None

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
    messages = soup.find_all('div',
                             attrs={'class': constants['messageStreamAttr']})
    for m in messages:
        t = m.find('div', {'class': timeAttr}).find_all('a')
        # t must be length of 2, first is user, second is date
        if (t is None):
            continue

        allT = m.find('div', {'class': messageTextAttr})
        allText = allT.find_all('div')
        messageTextView = allText[1]
        textFound = messageTextView.find('div').text  # No post processing
        isBull = isBullMessage(m)
        likeCnt = likeCount(m)
        commentCnt = commentCount(m)

        # need to convert to EDT time zone
        dateTime = findDateTime(t[1].text)
        if (dateTime is None):
            continue

        if (constants['current_timezone'] != 'EDT'):
            # localize to current time zone
            currTimeZone = pytz.timezone(constants['current_timezone'])
            dateTime = currTimeZone.localize(dateTime)
            dateTime = dateTime.astimezone(constants['eastern_timezone'])

        cur_res = {}
        cur_res['user'] = username
        cur_res['time'] = dateTime.strftime("%Y-%m-%d %H:%M:%S")
        cur_res['isBull'] = isBull
        cur_res['likeCount'] = likeCnt
        cur_res['commentCount'] = commentCnt
        cur_res['messageText'] = textFound
        res.append(cur_res)

    return res
