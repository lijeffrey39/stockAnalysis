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


def insertResults(results):
    collection = clientStockTweets.get_database('tweets_db').tweets
    for r in results:
        try:
            collection.insert_one(r)
        except Exception as e:
            print(str(e))

# ------------------------------------------------------------------------
# ----------------------- Analyze Specific Stock -------------------------
# ------------------------------------------------------------------------


def analyzeStocks(date):
    stocks = getAllStocks()
    dateString = date.strftime("%Y-%m-%d")
    stocks = ['A']
    for symbol in stocks:
        print(symbol)
        db = clientStockTweets.get_database('stocks_data_db')
        (shouldParse, hours) = shouldParseStock(symbol, dateString)
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

        results = updateLastMessageTime(db, symbol, result)
        updateLastParsedTime(db, symbol)

        # No new messages
        if (len(results) != 0):
            insertResults(results)


# ------------------------------------------------------------------------
# ----------------------- Analyze Specific User --------------------------
# ------------------------------------------------------------------------


def analyzeUsers(reAnalyze):
    users = findUsers(reAnalyze)
    # users = ['Beachswingtrader']
    for username in users:
        print(username)
        coreInfo = shouldParseUser(username, reAnalyze)
        if (not coreInfo):
            continue

        (soup, errorMsg, timeElapsed) = findPageUser(username)
        coreInfo['timeElapsed'] = timeElapsed
        if (errorMsg != ''):
            coreInfo['error'] = errorMsg
            insertUpdateError(coreInfo, reAnalyze)
            continue

        result = parseUserData(username, soup)
        if (len(result) == 0):
            coreInfo['error'] = "Empty result list"
            insertUpdateError(coreInfo, reAnalyze)
            continue

        insertUpdateError(coreInfo, reAnalyze)
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
        # refreshUserStatus()
        analyzeUsers(False)
    elif (options.stocks):
        now = convertToEST(datetime.datetime.now())
        date = datetime.datetime(now.year, now.month, 21)
        analyzeStocks(date)
    else:
        # now = convertToEST(datetime.datetime.now())
        # date = datetime.datetime(now.year, now.month, 10)
        # analyzeErrors(date)
        # updateUserNotAnalyzed()
        # return
        # getUserAccuracy('stockilluminatus')
        # return
        stocks = ['SQ', 'AMD', 'HSGX', 'AAPL', 'BIDU', 'TVIX', 'JNUG', 'ROKU', 'TSLA', 'UGAZ', 'CHK', 'DGAZ', 'QQQ', 'NIO']
        symbol = 'TVIX'

        date = datetime.datetime(dateNow.year, 8, 30, 10)
        dateUpTo = datetime.datetime(dateNow.year, 9, 18)
        dates = findTradingDays(date, dateUpTo)
        calculateAccuracy(symbol)
        basicPrediction(symbol, dates)
        return
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