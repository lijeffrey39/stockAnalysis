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


def endDriver(driver):
    driver.close()
    driver.quit()


# Returns list of all stocks
def getAllStocks():
    allStocks = constants['db_client'].get_database('stocktwits_db').all_stocks
    cursor = allStocks.find()
    stocks = list(map(lambda document: document['_id'], cursor))
    stocks.sort()
    stocks.remove('SPY')
    stocks.remove('OBLN')
    return stocks


# Return soup object page of that stock
def findPageStock(symbol, date, hoursBack):
    driver = None
    try:
        driver = webdriver.Chrome(executable_path=constants['driver_bin'],
                                  options=constants['chrome_options'],
                                  desired_capabilities=constants['caps'])
        driver.set_page_load_timeout(90)
    except Exception as e:
        return ('', str(e), 0)

    start = time.time()
    url = "https://stocktwits.com/symbol/%s" % symbol

    # Handling exceptions and random shit
    try:
        driver.get(url)
    except Exception as e:
        end = time.time()
        endDriver(driver)
        return ('', str(e), end - start)

    try:
        scroll.scrollFor(driver, hoursBack)
    except Exception as e:
        endDriver(driver)
        end = time.time()
        return ('', str(e), end - start)

    html = driver.page_source
    soup = BeautifulSoup(html, 'html.parser')
    end = time.time()
    print('Parsing user took %d seconds' % (end - start))
    endDriver(driver)
    return (soup, '', (end - start))


# Returns whether the stock should be parsed or not
# Will be parsed if it has been more than 12 hours since the last time it was
def shouldParseStock(symbol, dateString, db):
    tweetsErrorCollection = db.stock_tweets_errors
    if (tweetsErrorCollection.
            count_documents({'symbol': symbol,
                             'date': dateString}) != 0):
        return (False, 0)

    lastParsed = db.last_parsed
    lastTime = lastParsed.find({'_id': symbol})
    tweetsMapped = list(map(lambda document: document, lastTime))
    currTime = convertToEST(datetime.datetime.now())
    dateNow = currTime.replace(tzinfo=None)

    if (len(tweetsMapped) == 0):
        datePrev = parse(dateString)
        hoursBack = ((dateNow - datePrev).total_seconds() / 3600.0) + 1
        print(dateNow, datePrev, hoursBack)
        return (True, hoursBack)

    lastTime = tweetsMapped[0]['time']
    totalHoursBack = (dateNow - lastTime).total_seconds() / 3600.0
    print(lastTime, dateNow, totalHoursBack)

    # need to continue to parse if data is more than 3 hours old
    if (totalHoursBack > 13):
        return (True, totalHoursBack)
    else:
        return (False, 0)


# Updates the time this symbol was last parsed
def updateLastParsedTime(db, symbol):
    lastParsedDB = db.last_parsed
    lastTime = lastParsedDB.find({'_id': symbol})
    tweetsMapped = list(map(lambda document: document, lastTime))
    currTime = convertToEST(datetime.datetime.now())
    dateNow = currTime.replace(tzinfo=None)

    # If no last parsed time has been set yet
    if (len(tweetsMapped) == 0):
        lastParsedDB.insert_one({'_id': symbol, 'time': dateNow})
    else:
        # update last parsed time as current time
        query = {'_id': symbol}
        newVal = {'$set': {'time': dateNow}}
        lastParsedDB.update_one(query, newVal)


# Updates the time stamp for the last message for
# this symbol to find avoid overlap
def updateLastMessageTime(db, symbol, result):
    currLastTime = parse(result[0]['time'])
    lastMessageTimeCollection = db.last_message

    lastTime = lastMessageTimeCollection.find({'_id': symbol})
    timesMapped = list(map(lambda document: document, lastTime))

    # if no last message has been set yet
    if (len(timesMapped) == 0):
        newLastMessage = {'_id': symbol, 'time': currLastTime}
        lastMessageTimeCollection.insert_one(newLastMessage)
        return result

    lastTime = timesMapped[0]['time']
    newResult = []
    for tweet in result:
        if (parse(tweet['time']) > lastTime):
            newResult.append(tweet)

    query = {'_id': symbol}
    newVal = {'$set': {'time': currLastTime}}
    lastMessageTimeCollection.update_one(query, newVal)
    return newResult


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
        dateTime = None

        # Handle edge cases
        if (textFound == 'Lifetime' or textFound == 'Plus'):
            if (t[1].text == ''):
                textFound = allText[4].find('div').text
                dateTime = findDateTime(t[2].text)
            else:
                dateTime = findDateTime(t[1].text)
        else:
            if (t[1].text == ''):
                dateTime = findDateTime(t[2].text)
            else:
                dateTime = findDateTime(t[1].text)

        if (username is None or dateTime is None):
            raise Exception("How was datetime None")

        # need to convert to EDT time zone
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


# Remove duplicate tweets from db given a symbol
def removeDuplicatesDB(symbol):
    return symbol


# Analyze errored stocks
def analyzeErrors(date):
    dateString = date.strftime("%Y-%m-%d")

    clientStockTweets = constants['stocktweets_client']
    db = clientStockTweets.get_database('stocks_data_db')
    tweetsErrorCollection = db.stock_tweets_errors
    allStocks = constants['db_client'].get_database('stocktwits_db').all_stocks
    errorsWithDate = tweetsErrorCollection.find({'date': dateString})
    errorsMapped = list(map(lambda document: document, errorsWithDate))

    # Remove stocks that are empty
    # for error in errorsMapped:
    #     print(error['error'])
    #     print(error['symbol'])
    #     if (error['error'] == 'Len of messages was 0 ???'):
    #         allStocks.delete_one({'_id': error['symbol']})
    #         tweetsErrorCollection.delete_one({'_id': error['_id']})

    return
