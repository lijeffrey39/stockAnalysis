import datetime
import optparse
import matplotlib. pyplot as plt
from klepto.archives import dir_archive
import math
import time
import os
import yfinance as yf
import requests
import itertools
import json
import ujson
import shelve

from modules.helpers import (convertToEST, findTradingDays, getAllStocks,
                            insertResults, findWeight, writePickleObject, readPickleObject)
from modules.hyperparameters import constants
from modules.prediction import (basicPrediction, findAllTweets, updateBasicStockInfo, setupUserInfos)
from modules.stockAnalysis import (findPageStock, getTopStocks, parseStockData, getTopStocksforWeek,
                                shouldParseStock, updateLastMessageTime, updateStockCountPerWeek,
                                updateLastParsedTime, updateStockCount, getSortedStocks, stockcount1000daily)
from modules.stockPriceAPI import (updateAllCloseOpen, transferNonLabeled, findCloseOpen, closeToOpen, getUpdatedCloseOpen, 
                                    getCloseOpenInterval, updateyfinanceCloseOpen, exportCloseOpen, findCloseOpenCached)
from modules.userAnalysis import (findPageUser, findUsers, insertUpdateError,
                                parseUserData, shouldParseUser, getStatsPerUser,
                                updateUserNotAnalyzed,
                                calculateAllUserInfo, parseOldUsers)
from modules.tests import (findBadMessages, removeMessagesWithStock, 
                        findTopUsers, findOutliers, findAllUsers, findErrorUsers)
                        
from modules.newPrediction import (findTweets, weightedUserPrediction, writeTweets, calculateUserFeatures, dailyPrediction,
                                    editCachedTweets, prediction, findFeatures, pregenerateAllUserFeatures, pregenerateUserFeatures,
                                    saveUserTweets, cachedUserTweets, optimizeParams, findStockCounts, insertUser)


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
        (soup, errorMsg, timeElapsed) = findPageStock(symbol, hours)
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
        path = 'newPickled/stock_features_all_14.pkl'
        found_features = findFeatures(start_date, end_date, num_top_stocks, path, True)

        # Make prediction
        weightings = {
            'bull': 3,
            'bear': 1,
            # 'bull_w_return_log': 0.8,
            # 'bear_w_return_log': 0.2,
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
         stock_counts_collection = constants['db_client'].get_database('stocktwits_db').stock_counts_daily_1000.find()
         for i in stock_counts_collection:
             print('')
             print(i)

        # start_date = datetime.datetime(2019, 6, 10, 15, 30)
        # end_date = datetime.datetime(2020, 6, 28, 9, 30)
        # td = datetime.timedelta(days=1)
        # while (start_date <= end_date):
        #     stockcount1000daily(start_date)
        #     start_date+=td
        # usercollection = constants['db_user_client'].get_database('user_data_db').users.find({ 'bbcount': { '$exists': True }})
        # res = []
        # for i in usercollection:
        #     if i['_id'] == 'Kirkim':
        #         print(i)
        # print(usercollection.count())
        # for i in usercollection:
        #     if i['bbcount'] > 40:
        #         res.append(i['bbcount'])
        # print(len(res))
        # plt.hist(res, density=False, bins=150)
        # plt.show()
        # res = pregenerateUserFeatures('tony93')
        # demo = dir_archive('demo', serialized=True, cached=False)
        # demo['tony93'] = res

        # db = dir_archive('demo', serialized=True, cached=False)

        # print(time.time())
        # x = db['tony93']
        # print(time.time())
        # print(x)

        # insertUser()
        # print(res)

        # path = "data_file.json"
        # with open(path, 'r') as f:
        #     print(time.time())
        #     x = ujson.load(f)
        #     print(time.time())

        # pregenerateAllUserFeatures()


        #dailyPrediction(datetime.datetime(2020, 6, 30))


        # num_tweets_unique 30
        # num_tweets_s_unique 20
        # return_unique 40
        # return_unique_s 20
        # return_unique_w1 20
        # return_unique_log 20

        # bucket = readPickleObject('newPickled/bucket.pkl')
    
        # res = []
        # x = []
        # y = []
        # i = 0
        # for u in bucket:
        #     i += 1
            # logged = math.log10(bucket[u]['return_unique_s']) + 1
            # if (logged > 5):
            #     continue
            # if (bucket[u]['return_unique_log'] > 1000):
            #     continue
            # res.append(bucket[u]['return_unique_log'])
            # accuracy = bucket[u]['num_tweets_s_unique']
            # if (accuracy > 10 and accuracy < 500):
            #     res.append(accuracy)
        # print(len(res))
    
        # plt.hist(res, density=False, bins=150)
        # plt.show()
        # data = list(map(lambda x: x[7], bucket['bucket']))
        # data.sort(reverse=True)
        # print(data[:20])
        # # print(len(data))

        # now = convertToEST(datetime.datetime.now())
        # delta = datetime.timedelta(days=7)
        # result = []
        # while (date < datetime.datetime(2020, 6, 26)):
        #     print(date, getTopStocksforWeek(date, 15))
        #     date += delta
        # updateStockCountPerWeek(datetime.datetime(2020, 6, 29))
        # print(findWeight(datetime.datetime(2020, 6, 23, 9), 'log(x)'))

        

if __name__ == "__main__":
    main()
