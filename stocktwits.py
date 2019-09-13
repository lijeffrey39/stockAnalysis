import datetime
import json
import math
import multiprocessing
import operator
import optparse
import argparse
import os
import platform
import ssl
import sys
import time
from multiprocessing import Pool, Process
from random import shuffle

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
from modules.hyperparameters import constants

client = constants['db_client']
clientUser = constants['db_user_client']
clientStockTweets = constants['stocktweets_client']


# ------------------------------------------------------------------------
# ----------------------- Analyze Specific Stock -------------------------
# ------------------------------------------------------------------------


def analyzeStocks(date):
    stocks = getAllStocks()
    dateString = date.strftime("%Y-%m-%d")

    for symbol in stocks:
        print(symbol)
        db = clientStockTweets.get_database('stocks_data_db')
        (shouldParse, hours) = shouldParseStock(symbol, dateString, db)
        if (shouldParse is False):
            continue

        (soup, errorMsg, timeElapsed) = findPageStock(symbol, date, hours)
        if (soup is ''):
            stockError = {'date': dateString, 'symbol': symbol,
                          'error': errorMsg, 'timeElapsed': timeElapsed}
            db.stock_tweets_errors.insert_one(stockError)
            continue

        try:
            result = parseStockData(symbol, soup)
        except Exception as e:
            stockError = {'date': dateString, 'symbol': symbol,
                          'error': str(e), 'timeElapsed': -1}
            db.stock_tweets_errors.insert_one(stockError)
            continue

        if (len(result) == 0):
            stockError = {'date': dateString, 'symbol': symbol,
                          'error': 'Result length is 0??', 'timeElapsed': -1}
            db.stock_tweets_errors.insert_one(stockError)
            continue

        result = updateLastMessageTime(db, symbol, result)

        # No new messages
        if (len(result) != 0):
            db.stock_tweets.insert_many(result)
        updateLastParsedTime(db, symbol)


# ------------------------------------------------------------------------
# ----------------------- Analyze Specific User --------------------------
# ------------------------------------------------------------------------


def shouldParseUser(username):
    analyzedUsers = clientUser.get_database('user_data_db').users
    if (analyzedUsers.count_documents({'_id': username}) != 0):
        return None

    (coreInfo, error) = findUserInfo(username)
    # coreInfo['ideas'] = -1
    # username = 'ElliottwaveForecast'

    # If API is down/user doesnt exist
    if (not coreInfo):
        errorMsg = "User doesn't exist / API down"
        userInfoError = {'_id': username, 'error': errorMsg}
        analyzedUsers.insert_one(userInfoError)
        return None

    # If exceed the 200 limited API calls
    if (coreInfo['ideas'] == -1):
        (coreInfo, errorMsg) = findUserInfoDriver(username)
        if (not coreInfo):
            userInfoError = {'_id': username, 'error': errorMsg}
            analyzedUsers.insert_one(userInfoError)
            return None

    # If number of ideas are < the curren min threshold
    if (coreInfo['ideas'] < constants['min_idea_threshold']):
        coreInfo['error'] = 'Not enough ideas'
        coreInfo['_id'] = username
        analyzedUsers.insert_one(coreInfo)
        return None

    coreInfo['last_updated'] = convertToEST(datetime.datetime.now())

    return coreInfo


def refreshUserStatus():
    analyzedUsers = clientUser.get_database('user_data_db').users
    query = {"error": ""}
    goodUsers = analyzedUsers.find(query)

    curTime = convertToEST(datetime.datetime.now())
    for users in goodUsers:
        # only update if data is over 7 days old
        if 'last_updated' in users:
            lastTime = users['last_updated']
            lastTime = convertToEST(lastTime)
            hoursPast = (curTime - lastTime).total_seconds() / 3600.0
            if (hoursPast < 168):
                continue

        username = users['_id']
        print(username)
        (result, error) = findUserInfoDriver(username)
        users.update(result)
        users['last_updated'] = convertToEST(datetime.datetime.now())
        updateQuery = {'_id': username}
        newValues = {'$set': users}
        analyzedUsers.update_one(updateQuery, newValues)


def analyzeUsers():
    db = client.get_database('stocktwits_db')
    allUsers = db.users_not_analyzed
    cursor = allUsers.find()
    users = list(map(lambda document: document['_id'], cursor))
    shuffle(users)

    for username in users:
        print(username)
        coreInfo = shouldParseUser(username)
        if (not coreInfo):
            continue

        analyzedUsers = clientUser.get_database('user_data_db').users
        (soup, errorMsg, timeElapsed) = findPageUser(username)
        coreInfo['_id'] = username
        coreInfo['timeElapsed'] = timeElapsed
        if (soup == ''):
            coreInfo['error'] = errorMsg
            analyzedUsers.insert_one(coreInfo)
            continue

        result = parseUserData(username, soup)
        if (len(result) == 0):
            coreInfo['error'] = "Empty result list"
            analyzedUsers.insert_one(coreInfo)
            continue

        coreInfo['error'] = ""
        analyzedUsers.insert_one(coreInfo)
        userInfoCollection = clientUser.get_database('user_data_db').user_info
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


def addOptions(parser):
    parser.add_option('-u', '--users',
                      action='store_true', dest="users",
                      help="parse user information")

    parser.add_option('-s', '--stocks',
                      action='store_true', dest="stocks",
                      help="parse stock information")


def main():
    opt_parser = optparse.OptionParser()
    addOptions(opt_parser)
    options, args = opt_parser.parse_args()
    dateNow = datetime.datetime.now()

    if (options.users):
        analyzeUsers()
    elif (options.stocks):
        now = convertToEST(datetime.datetime.now())
        date = datetime.datetime(now.year, now.month, 13)
        analyzeStocks(date)
    else:
        now = convertToEST(datetime.datetime.now())
        date = datetime.datetime(now.year, now.month, 10)
        analyzeErrors(date)
        # updateUserNotAnalyzed()
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