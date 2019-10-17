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
from random import shuffle
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


def analyzeStocks(date, stocks):
    dateString = date.strftime("%Y-%m-%d")
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


def makePredictionToday(processes):
    now = convertToEST(datetime.datetime.now())
    date = datetime.datetime(now.year, now.month, now.day)

    stocks = getTopStocks()
    stocks = stocks[:25]
    shuffle(stocks)

    analyzeStocks(date, stocks)
    dates = [datetime.datetime(now.year, now.month, 16, 9, 30), datetime.datetime(now.year, now.month, 17, 16)]
    basicPrediction(dates, stocks)

    # chunked = chunkIt(stocks, processes)
    # pool = Pool()
    # for i in range(processes):
    #     pool.apply_async(analyzeStocks, [date, chunked[i]])

    # pool.close()
    # pool.join()


def main():
    opt_parser = optparse.OptionParser()
    addOptions(opt_parser)
    options, args = opt_parser.parse_args()
    dateNow = datetime.datetime.now()

    makePredictionToday(1)
    return

    # print(getUpdatedCloseOpen('AAPL', datetime.datetime(dateNow.year, 9, 24)))
    # return

    if (options.users):
        # refreshUserStatus()
        analyzeUsers(False)
    elif (options.stocks):
        now = convertToEST(datetime.datetime.now())
        date = datetime.datetime(now.year, now.month, 3)
        stocks = getAllStocks()
        analyzeStocks(date, stocks)
    else:
        # now = convertToEST(datetime.datetime.now())
        # date = datetime.datetime(now.year, now.month, 10)
        # analyzeErrors(date)
        # updateUserNotAnalyzed()
        # return
        # getUserAccuracy('stockilluminatus')
        # return
        # print(getStatsPerUser('ACInvestorBlog'))
        # return

        # date = datetime.datetime(dateNow.year, 9, 3, 9, 30)
        # dateUpTo = datetime.datetime(dateNow.year, 9, 24, 16)

        # date = datetime.datetime(dateNow.year, 9, 25, 9, 30)
        # dateUpTo = datetime.datetime(dateNow.year, 10, 14, 16)

        date = datetime.datetime(dateNow.year, 9, 3, 9, 30)
        dateUpTo = datetime.datetime(dateNow.year, 10, 16, 16)
        dates = findTradingDays(date, dateUpTo)
        stocks = getTopStocks()
        stocks = stocks[:25]
        # for i in range(len(stocks)):
        #     print(i, stocks[i])
        # print(dates)
        # updateAllCloseOpen(stocks, dates)
        # return

        basicPrediction(dates, stocks)
        # updateBasicStockInfo(dates, stocks)

if __name__ == "__main__":
    main()
