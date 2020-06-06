import datetime
from datetime import timedelta
import time
from random import shuffle
import pickle

from selenium import webdriver
from selenium.webdriver.common.keys import Keys

from bs4 import BeautifulSoup

from . import scroll
from .helpers import convertToEST, customHash, endDriver
from .hyperparameters import constants
from .messageExtract import *
from .stockPriceAPI import *


# ------------------------------------------------------------------------
# ----------------------------- Functions --------------------------------
# ------------------------------------------------------------------------


def getTopStocks(numStocks=100):
    sortedStockList = getSortedStocks()
    sortedStockList.remove('HSGX')
    return sortedStockList[:numStocks]

def getSortedStocks():
    stockCounts = constants['db_client'].get_database(
        'stocktwits_db').stock_counts
    cursor = stockCounts.find()
    stocks = list(map(lambda document: document, cursor))
    newdict = sorted(stocks, key=lambda k: k['count'], reverse=True)
    newlist = list(map(lambda document: document['_id'], newdict))
    return newlist


def updateStockCount():
    currTime = convertToEST(datetime.datetime.now())
    prevTime = currTime - timedelta(days=300)    
    stockCounts = constants['db_client'].get_database(
        'stocktwits_db').stock_counts
    allStocks = constants['db_client'].get_database('stocktwits_db').all_stocks
    cursor = allStocks.find()
    stocks = list(map(lambda document: document['_id'], cursor))

    for s in stocks:
        tweets = constants['stocktweets_client'].get_database('tweets_db').tweets.find({"$and": [{'symbol': s},
                                                                 {'time': {'$gte': prevTime,
                                                                  '$lt': currTime}}]})
        lastTime = stockCounts.find({'_id': s})
        tweetsMapped = list(map(lambda document: document, lastTime))
        count = tweets.count()
        print(s, count)
        # If no last parsed time has been set yet
        if (len(tweetsMapped) == 0):
            stockCounts.insert_one({'_id': s, 'count': count})
        else:
            # update last parsed time as current time
            query = {'_id': s}
            newVal = {'$set': {'count': count}}
            stockCounts.update_one(query, newVal)


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

    try:
        driver.get(url)
    except Exception as e:
        end = time.time()
        endDriver(driver)
        return ('', str(e), end - start)

    # inputElement = driver.find_element_by_tag_name("input")
    # inputElement.send_keys(symbol)
    # inputElement.send_keys(Keys.ENTER)
    # time.sleep(1)
    # allButtons = driver.find_elements_by_class_name('st_1luPg-o')
    # for button in allButtons:
    #     if button.text == symbol:
    #         button.click()
    #         break
    #hoursBack = 13
    try:
        scroll.scrollFor(driver, hoursBack)
    except Exception as e:
        endDriver(driver)
        end = time.time()
        print(e)
        return ('', str(e), end - start)

    html = driver.page_source
    soup = BeautifulSoup(html, 'html.parser')

    end = time.time()
    print('Parsing stock took %d seconds' % (end - start))
    endDriver(driver)
    return (soup, '', (end - start))


# Returns whether the stock should be parsed or not
# Will be parsed if it has been more than 12 hours since the last time it was
def shouldParseStock(symbol, dateString):
    db = constants['stocktweets_client'].get_database('stocks_data_db')
    tweetsErrorCollection = db.stock_tweets_errors
    if (tweetsErrorCollection.
            count_documents({'symbol': symbol,
                             'date': dateString}) != 0):
        return (False, 0)

    lastParsed = db.last_parsed
    lastTime = lastParsed.find({'_id': symbol})
    tweetsMapped = list(map(lambda document: document, lastTime))
    currTime = convertToEST(datetime.datetime.now())

    if (len(tweetsMapped) == 0):
        datePrev = parse(dateString)
        hoursBack = ((currTime - datePrev).total_seconds() / 3600.0) + 1
        print(currTime, datePrev, hoursBack)
        return (True, hoursBack)

    lastTime = tweetsMapped[0]['time']
    totalHoursBack = (currTime - lastTime).total_seconds() / 3600.0
    #totalHoursBack = 1.1
    print(currTime, lastTime, totalHoursBack)

    # need to continue to parse if data is more than 3 hours old
    if (totalHoursBack > constants['hoursBackToAnalyze']):
        return (True, totalHoursBack)
    else:
        return (False, 0)


# Updates the time this symbol was last parsed
def updateLastParsedTime(db, symbol):
    lastParsedDB = db.last_parsed
    lastTime = lastParsedDB.find({'_id': symbol})
    tweetsMapped = list(map(lambda document: document, lastTime))
    currTime = convertToEST(datetime.datetime.now())

    # If no last parsed time has been set yet
    if (len(tweetsMapped) == 0):
        lastParsedDB.insert_one({'_id': symbol, 'time': currTime})
    else:
        # update last parsed time as current time
        query = {'_id': symbol}
        newVal = {'$set': {'time': currTime}}
        lastParsedDB.update_one(query, newVal)


# Updates the time stamp for the last message for
# this symbol to find avoid overlap
def updateLastMessageTime(db, symbol, result):
    currLastTime = result[0]['time']
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
        # if (tweet['time'] > lastTime):
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
        t = m.find('div', {'class': constants['timeAttr']}).find_all('a')
        # length of 2, first is user, second is date
        if (t is None):
            continue

        allT = m.find('div', {'class': constants['messageTextAttr']})
        allText = allT.find_all('div')
        username = findUser(t[0])
        textFound = allText[1].find('div').text  # No post processing
        if (textFound == 'Bearish' or textFound == 'Bullish'):
            textFound = allText[3].find('div').text
        isBull = isBullMessage(m)
        likeCnt = likeCount(m)
        commentCnt = commentCount(m)
        dateString = ""

        # Handle edge cases
        if (textFound == 'Lifetime' or textFound == 'Plus'):
            textFound = allText[4].find('div').text

        if (t[1].text == ''):
            dateString = t[2].text
        else:
            dateString = t[1].text

        (dateTime, errorMsg) = findDateTime(dateString)
        if (errorMsg != ""):
            print(errorMsg)
            continue

        dateAsString = dateTime.strftime("%Y-%m-%d %H:%M:%S")
        hashString = textFound + dateAsString + username
        hashID = customHash(hashString)

        cur_res = {}
        cur_res['_id'] = hashID
        cur_res['symbol'] = symbol
        cur_res['user'] = username
        cur_res['time'] = dateTime
        cur_res['isBull'] = isBull
        cur_res['likeCount'] = likeCnt
        cur_res['commentCount'] = commentCnt
        cur_res['messageText'] = textFound
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
