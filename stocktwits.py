import datetime
import json
import math
import multiprocessing
import operator
import optparse
import os
import platform
import sys
import time
import ssl
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
from modules.messageExtract import *
from modules.prediction import *
from modules.scroll import *
from modules.stockAnalysis import *
from modules.stockPriceAPI import *
from modules.userAnalysis import *
from modules.hyperparameters import *

client = pymongo.MongoClient("mongodb+srv://lijeffrey39:test@cluster0-qthez.mongodb.net/test?retryWrites=true&w=majority", ssl_cert_reqs=ssl.CERT_NONE)

# ------------------------------------------------------------------------
# -------------------------- Global Variables ----------------------------
# ------------------------------------------------------------------------

cpuCount = multiprocessing.cpu_count()
DAYS_BACK = 75
DEBUG = True
PROGRESSIVE = False
MULTIPLE_DAYS = True


# ------------------------------------------------------------------------
# ----------------------- Analyze Specific Stock -------------------------
# ------------------------------------------------------------------------


def getAllStocks():
    db = client.get_database('stocktwits_db')
    allStocks = db.all_stocks
    cursor = allStocks.find()
    stocks = list(map(lambda document: document['_id'], cursor))
    stocks.sort()
    stocks.remove('SPY')
    stocks.remove('OBLN')


def analyzeStocksToday():
    stocks = getAllStocks()
    dateNow = datetime.datetime.now()
    dateString = dateNow.strftime("%m-%d-%y")
    dateStringErrors = dateNow.strftime("%m-%d-%y-errors")

    for symbol in stocks:
        print(symbol)
        db = client.get_database('stocks_data_db')
        currCollection = db[dateString]
        if (currCollection.count_documents({'_id': symbol}) != 0 or 
            db[dateStringErrors].count_documents({'_id': symbol}) != 0):
            continue

        (soup, errorMsg, timeElapsed) = findPageStock(symbol)
        if (soup is ''):
            currCollectionErrors = db[dateStringErrors]
            stockError = {'_id': symbol, 'error': errorMsg, 'timeElapsed': timeElapsed}
            if (currCollectionErrors.count_documents({'_id': symbol}) != 0):
                continue
            currCollectionErrors.insert_one(stockError)
            continue

        result = parseStockData(symbol, soup)
        stockDataCollection = client.get_database('stocks_data_db')[dateString]
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
        analyzeStocksToday()
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
