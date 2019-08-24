import datetime
import json
import math
import multiprocessing
import operator
import optparse
import os
import platform
import ssl
import sys
import time
from multiprocessing import Pool, Process

import pymongo
from dateutil.parser import parse
from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys

from bs4 import BeautifulSoup
from modules.analytics import *
from modules.fileIO import *
from modules.helpers import *
from modules.hyperparameters import *
from modules.messageExtract import *
from modules.prediction import *
from modules.scroll import *
from modules.stockAnalysis import *
from modules.stockPriceAPI import *
from modules.userAnalysis import *

client = pymongo.MongoClient("mongodb+srv://lijeffrey39:test@cluster0-qthez."
                             "mongodb.net/test?retryWrites=true&w=majority",
                             ssl_cert_reqs=ssl.CERT_NONE)


# ------------------------------------------------------------------------
# ----------------------- Analyze Specific Stock -------------------------
# ------------------------------------------------------------------------


def getAllStocks():
    allStocks = client.get_database('stocktwits_db').all_stocks
    cursor = allStocks.find()
    stocks = list(map(lambda document: document['_id'], cursor))
    stocks.sort()
    stocks.remove('SPY')
    stocks.remove('OBLN')
    return stocks


def shouldParseStock(symbol, dateString):
    db = client.get_database('stocks_data_db')
    tweetsErrorCollection = db.stock_tweets_errors
    if (tweetsErrorCollection.
            count_documents({'symbol': symbol,
                             'date': dateString}) != 0):
        return False

    tweetsCollection = db.stock_tweets
    tweetsForDay = tweetsCollection.find({'symbol': symbol,
                                          'date': dateString})
    tweetsMapped = list(map(lambda document: document, tweetsForDay))
    timesMapped = list(map(lambda tweet: parse(tweet['time']), tweetsMapped))
    timesMapped.sort(reverse=True)

    if (len(timesMapped) == 0):
        return True

    lastTime = timesMapped[0]
    currTime = datetime.datetime.now()
    totalHoursBack = (currTime - lastTime).total_seconds() / 3600.0

    # need to continue to parse if data is more than 3 hours old
    if (totalHoursBack > 3.0):
        return True
    else:
        return False


def analyzeStocks(date):
    stocks = getAllStocks()
    dateString = date.strftime("%Y-%m-%d")

    for symbol in stocks:
        print(symbol)
        if (shouldParseStock(symbol, dateString) is False):
            continue

        (soup, errorMsg, timeElapsed) = findPageStock(symbol, date)
        db = client.get_database('stocks_data_db')
        if (soup is ''):
            tweetsErrorCollection = db.stock_tweets_errors
            stockError = {'date': dateString,
                          'symbol': symbol,
                          'error': errorMsg,
                          'timeElapsed': timeElapsed}
            tweetsErrorCollection.insert_one(stockError)
            continue

        result = parseStockData(symbol, soup)
        stockDataCollection = db.stock_tweets
        stockDataCollection.insert_many(result)


# ------------------------------------------------------------------------
# ----------------------- Analyze Specific User --------------------------
# ------------------------------------------------------------------------


def analyzeUsers():
    db = client.get_database('stocktwits_db')
    allUsers = db.users_not_analyzed
    cursor = allUsers.find()
    users = list(map(lambda document: document['_id'], cursor))

    for username in users:
        print(username)
        analyzedUsers = client.get_database('user_data_db').users
        if (analyzedUsers.count_documents({'_id': username}) != 0):
            continue
        coreInfo = findUserInfo(username)

        # If API is down/user doesnt exist
        if (not coreInfo):
            errorMsg = "User doesn't exist"
            userInfoError = {'_id': username, 'error': errorMsg}
            analyzedUsers.insert_one(userInfoError)
            continue

        # If exceed the 200 limited API calls
        if (coreInfo['ideas'] == -1):
            (coreInfo, errorMsg) = findUserInfoDriver(username)
            if (not coreInfo):
                userInfoError = {'_id': username, 'error': errorMsg}
                analyzedUsers.insert_one(userInfoError)
                continue

        # If number of ideas are < the curren min threshold
        if (coreInfo['ideas'] < constants['min_idea_threshold']):
            coreInfo['error'] = 'Not enough ideas'
            coreInfo['_id'] = username
            analyzedUsers.insert_one(coreInfo)
            continue

        (soup, errorMsg, timeElapsed) = findPageUser(username)
        coreInfo['_id'] = username
        coreInfo['timeElapsed'] = timeElapsed
        if (soup == ''):
            coreInfo['error'] = errorMsg
            analyzedUsers.insert_one(coreInfo)
            continue
        else:
            coreInfo['error'] = ""
            analyzedUsers.insert_one(coreInfo)

        result = parseUserData(username, soup)
        userInfoCollection = client.get_database('user_data_db').user_info
        userInfoCollection.insert_many(result)
    

# ------------------------------------------------------------------------
# --------------------------- Main Function ------------------------------
# ------------------------------------------------------------------------


# TODO
# 1. SHOULD IGNORE DIFF if it is 0? count as correct
# 2. Remove outliers that are obviously not true prices
# 4. Weight likes/comments into the accuracy of user
# 6. Figure out why some invalid symbols are not actually invalid
# 7. View which stocks should be removed based on # users
# 8. Implement better caching
# 10. Find faster way to update templists folder
# 13. For dictPredictions, find the middle number of users for prediction rate

# Find outliers in stocks

def runInterval(date, endTime, sleepTime):
    prevHour = datetime.datetime.now()
    while (datetime.datetime.now() < endTime):
        # Compute stocks
        # computeStocksDay(date, 7)

        # View how much time has passed
        newHour = datetime.datetime.now()
        secPassed = (newHour - prevHour).seconds

        if (secPassed > sleepTime):
            prevHour = newHour
        else:
            timeRest = sleepTime - secPassed
            time.sleep(timeRest)


def findOutliers(stockName, date):
    folder = "userinfo/"
    allU = allUsers()
    print(len(allU))
    found = 0
    count = 0

    for u in allU:
        l = readMultiList('userInfo/' + u + '.csv')

        for r in l:
            four = float(r[2])
            nine = float(r[3])
            foundDate = parse(r[1])

            if (r[0] == stockName
                and foundDate.year == date.year
                and foundDate.day == date.day
                and foundDate.month == date.month):
                count += 2
                found += four
                found += nine

    print(found / count)


def addOptions(parser):
    parser.add_option('-u', '--users',
                      action='store_true', dest="users",
                      help="parse user information")

    parser.add_option('-s', '--stocks',
                      action='store_true', dest="stocks",
                      help="parse stock information")


def main():
    parser = optparse.OptionParser()
    addOptions(parser)

    options, args = parser.parse_args()
    dateNow = datetime.datetime.now()

    if (options.users):
        analyzeUsers()
    elif (options.stocks):
        now = datetime.datetime.now()
        date = datetime.datetime(now.year, now.month, 23)
        analyzeStocks(date)
    else:
        # date = datetime.datetime(dateNow.year, 1, 14)
        # dateUpTo = datetime.datetime(dateNow.year, 3, 1)

        db = client.get_database('stocktwits_db')
        allUsers = db.all_stocks
        return
        
        date = datetime.datetime(dateNow.year, 5, 18)
        dateUpTo = datetime.datetime(dateNow.year, 6, 4)

        currDate = datetime.datetime.now()
        dates = findTradingDays(date, dateUpTo)
        # dates = dates[0: len(dates)]

        print(dates)
        # dates = [datetime.datetime(dateNow.year, 5, 21)]

        money = 2000
        startMoney = 2000
        totalReturn = 0
        x = 0
        y = 0
        dictPrices = {}
        for date in dates:
            weights = [9, 0.48, 0.45, 0.64, 1.92]

            (res, hitPercent) = topStocks(date, money, weights)
            (foundReturn, pos, neg, newRes) = calcReturnBasedResults(date, res)

            for new in newRes:
                if (new[0] not in dictPrices):
                    dictPrices[new[0]] = new[1]
                else:
                    dictPrices[new[0]] += new[1]

            x += pos
            y += neg
            if (foundReturn >= 0):
                print("%s $%.2f +%.2f%%    Hit: %.2f%%" % (date.strftime("%m-%d-%y"), foundReturn,
                    round((((money + foundReturn) / money) - 1) * 100, 2), hitPercent))
            else:
                print("%s $%.2f %.2f%%    Hit: %.2f%%" % (date.strftime("%m-%d-%y"), foundReturn,
                    round((((money + foundReturn) / money) - 1) * 100, 2), hitPercent))
            totalReturn += foundReturn
            money += foundReturn

        sorted_x = sorted(dictPrices.items(), key = operator.itemgetter(1))
        # print(sorted_x)
        print("$%d -> $%d" % (startMoney, startMoney + totalReturn))
        print("+%.2f%%" % (round((((startMoney + totalReturn) / startMoney) - 1) * 100, 2)))
        print("+%d -%d" % (x, y))


if __name__ == "__main__":
    main()
