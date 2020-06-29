import datetime
import optparse
import matplotlib. pyplot as plt
import math
import os
import yfinance as yf
import requests
import itertools

from modules.helpers import (convertToEST, findTradingDays, getAllStocks, recurse,
                             insertResults, findWeight, writePickleObject, readPickleObject)
from modules.hyperparameters import constants
from modules.prediction import (basicPrediction, findAllTweets, updateBasicStockInfo, setupUserInfos)
from modules.stockAnalysis import (findPageStock, getTopStocks, parseStockData, getTopStocksforWeek,
                                   shouldParseStock, updateLastMessageTime, updateStockCountPerWeek,
                                   updateLastParsedTime, updateStockCount, getSortedStocks)
from modules.stockPriceAPI import (updateAllCloseOpen, transferNonLabeled, findCloseOpen, closeToOpen, getUpdatedCloseOpen, 
                                    getCloseOpenInterval, updateyfinanceCloseOpen, exportCloseOpen, findCloseOpenCached)
from modules.userAnalysis import (findPageUser, findUsers, insertUpdateError,
                                  parseUserData, shouldParseUser, getStatsPerUser,
                                  updateUserNotAnalyzed,
                                  calculateAllUserInfo, parseOldUsers)
from modules.tests import (findBadMessages, removeMessagesWithStock, 
                           findTopUsers, findOutliers, findAllUsers, findErrorUsers)
                        
from modules.newPrediction import (findTweets, weightedUserPrediction, writeTweets, calculateUserFeatures, 
                                    editCachedTweets, prediction, findFeatures, pregenerateAllUserFeatures,
                                    saveUserTweets, cachedUserTweets, optimizeParams, findStockCounts)


client = constants['db_client']
clientUser = constants['db_user_client']
clientStockTweets = constants['stocktweets_client']


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
        if (soup == ''):
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
            print(e)
            continue

        if (len(result) == 0):
            stockError = {'date': dateString, 'symbol': symbol,
                          'error': 'Result length is 0??', 'timeElapsed': -1}
            db.stock_tweets_errors.insert_one(stockError)
            print(stockError)
            continue

        results = updateLastMessageTime(db, symbol, result)

        # No new messages
        if (len(results) != 0):
            insertResults(results)

        updateLastParsedTime(db, symbol)


# ------------------------------------------------------------------------
# ----------------------- Analyze Specific User --------------------------
# ------------------------------------------------------------------------


# updateUser reparses tweets made by user and adds status flag if non-existing
# findNewUsers updates user_not_analyzed table to find new users to parse/store
# reAnalyze reanalyzes users that errored out
def analyzeUsers(reAnalyze, findNewUsers, updateUser):
    users = findUsers(reAnalyze, findNewUsers, updateUser)
    print(len(users))
    for username in users:
        print(username)
        coreInfo = shouldParseUser(username, reAnalyze, updateUser)
        if (not coreInfo):
            continue

        (soup, errorMsg, timeElapsed) = findPageUser(username)
        coreInfo['timeElapsed'] = timeElapsed
        if (errorMsg != ''):
            coreInfo['error'] = errorMsg
            insertUpdateError(coreInfo, reAnalyze, updateUser)
            continue

        result = parseUserData(username, soup)
        if (len(result) == 0):
            coreInfo['error'] = "Empty result list"
            insertUpdateError(coreInfo, reAnalyze, updateUser)
            continue

        insertResults(result)
        insertUpdateError(coreInfo, reAnalyze, updateUser)

def dailyAnalyzeUsers(reAnalyze, updateUser, daysback):
    users = parseOldUsers(daysback)
    print(len(users))
    for username in users:
        print(username)
        coreInfo = shouldParseUser(username, reAnalyze, updateUser)
        if (not coreInfo):
            continue

        (soup, errorMsg, timeElapsed) = findPageUser(username)
        coreInfo['timeElapsed'] = timeElapsed
        if (errorMsg != ''):
            coreInfo['error'] = errorMsg
            insertUpdateError(coreInfo, reAnalyze, updateUser)
            continue

        result = parseUserData(username, soup)
        if (len(result) == 0):
            coreInfo['error'] = "Empty result list"
            insertUpdateError(coreInfo, reAnalyze, updateUser)
            continue

        insertUpdateError(coreInfo, reAnalyze, updateUser)
        insertResults(result)


# ------------------------------------------------------------------------
# --------------------------- Main Function ------------------------------
# ------------------------------------------------------------------------


def addOptions(parser):
    parser.add_option('-u', '--users',
                      action='store_true', dest="users",
                      help="parse user information")

    parser.add_option('-s', '--stocks',
                      action='store_true', dest="stocks",
                      help="parse stock information")

    parser.add_option('-p', '--prediction',
                      action='store_true', dest="prediction",
                      help="make prediction for today")

    parser.add_option('-c', '--updateCloseOpens',
                      action='store_true', dest="updateCloseOpens",
                      help="update Close open times")

    parser.add_option('-z', '--hourlyparser',
                      action='store_true', dest="hourlyparser",
                      help="parse through stock pages hourly")
    
    parser.add_option('-d', '--dailyparser',
                      action='store_true', dest="dailyparser",
                      help="parse through non-top x stock pages daily")
    
    parser.add_option('-o', '--optimizer',
                      action='store_true', dest="optimizer",
                      help="optimize prediction")

    parser.add_option('-a', '--dailyuserparser',
                      action='store_true', dest="dailyuserparser",
                      help="parse through user information that havent been parsed over last x days (14)")



# Executed hourly, finds all the tweets from the top x stocks
def hourlyparse():
    date = convertToEST(datetime.datetime.now())
    stocks = getTopStocks(50)
    date = datetime.datetime(date.year, date.month, date.day, 9, 30)
    analyzeStocks(date, stocks)

# Executed daily, finds all the tweets from the non-top x stocks
def dailyparse():
    now = convertToEST(datetime.datetime.now())
    date = datetime.datetime(now.year, now.month, now.day)
    stocks = getSortedStocks()
    analyzeStocks(date, stocks[101:1001])

def main():
    opt_parser = optparse.OptionParser()
    addOptions(opt_parser)
    options, _ = opt_parser.parse_args()
    dateNow = convertToEST(datetime.datetime.now())

    if (options.users):
        analyzeUsers(reAnalyze=False, findNewUsers=False, updateUser=True)
    elif (options.stocks):
        now = convertToEST(datetime.datetime.now())
        date = datetime.datetime(now.year, now.month, now.day)
        stocks = getTopStocksforWeek(date, 100)
        analyzeStocks(date, stocks)
    elif (options.optimizer):
        optimizeParams()
    elif (options.prediction):
        num_top_stocks = 15 # Choose top 20 stocks of the week to parse
        start_date = datetime.datetime(2019, 6, 9, 15, 30)
        end_date = datetime.datetime(2020, 6, 28, 9, 30)

        # Write stock tweet files
        # writeTweets(start_date, end_date, num_top_stocks, overwrite=True)
        # return

        # Find features for prediction
        path = 'newPickled/stock_features_all.pkl'
        found_features = findFeatures(start_date, end_date, num_top_stocks, path, False)

        # Make prediction
        weightings = {
            'bull_w': 2.84,
            'bear_w': 1.14
            # 'total_w': 8.5,
            # 'return_log_s_w': 8.1,
            # 'count_ratio_w': 3.9,
            # 'return_ratio': 3.9,
            # 'return_s_w': 4.2,
            # 'bear_return_s': 2.8,
            # 'bear': 7.7,
            # 'bear_return': 4.1
        }
        print(prediction(start_date, end_date, found_features, num_top_stocks, weightings, True))

    elif (options.updateCloseOpens):
        updateStockCount()
        now = convertToEST(datetime.datetime.now())
        date = datetime.datetime(now.year, now.month, now.day, 12, 30)
        dateNow = datetime.datetime(now.year, now.month, now.day, 13, 30)
        dates = findTradingDays(date, dateNow)
        print(dates)
        stocks = getSortedStocks()
        updateAllCloseOpen(stocks, dates)
    elif (options.hourlyparser):
        hourlyparse()
    elif (options.dailyparser):
        dailyparse()
    elif (options.dailyuserparser):
        dailyAnalyzeUsers(reAnalyze=True, updateUser=True, daysback=14)
    else:
        # bucket = readPickleObject('bucket.pkl')
        # data = list(map(lambda x: x[7], bucket['bucket']))
        # data.sort(reverse=True)
        # print(data[:20])
        # # print(len(data))
        # plt.hist(data[40:], density=False, bins=150)
        # plt.show()

        now = convertToEST(datetime.datetime.now())
        date = datetime.datetime(2020, 5, 9)
        delta = datetime.timedelta(days=7)
        result = []
        while (date < datetime.datetime(2020, 6, 26)):
            print(date, getTopStocksforWeek(date, 15))
            date += delta

        # updateStockCountPerWeek(datetime.datetime(2020, 6, 29))


if __name__ == "__main__":
    main()
