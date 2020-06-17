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
                        
from modules.newPrediction import (findTweets, weightedUserPrediction, writeTweets, calculateUserFeatures, editCachedTweets,
                                    prediction, findFeatures, updateAllUsers, saveUserTweets, cachedUserTweets, optimizeParams)


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

    parser.add_option('-a', '--dailyuserparser',
                      action='store_true', dest="dailyuserparser",
                      help="parse through user information that havent been parsed over last x days (14)")


# Make a prediction for given date
def makePrediction(date):
    dates = [datetime.datetime(date.year, date.month, date.day, 9, 30)]
    stocks = getTopStocks(20)
    stocks.remove('AMZN')
    stocks = ['TSLA']
    analyzeStocks(date, stocks)
    # basicPrediction(dates, stocks, True, True)

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
        stocks = getTopStocks(100)
        # print(len(stocks))
        # for i in range(len(stocks)):
        #     if (stocks[i] == "SESN"):
        #         print(i)
        analyzeStocks(date, stocks)
    elif (options.prediction):
        num_top_stocks = 20 # Choose top 20 stocks of the week to parse
        start_date = datetime.datetime(2020, 1, 9, 15, 30)
        end_date = datetime.datetime(2020, 6, 9, 9, 30)
        # end_date = datetime.datetime(dateNow.year, dateNow.month, dateNow.day - 3)
        
        # Write all user files
        # updateAllUsers()

        # Write stock tweet files
        # writeTweets(start_date, end_date, num_top_stocks)

        # Find features for prediction
        path = 'newPickled/features_new_sqrtx.pkl'
        found_features = findFeatures(start_date, end_date, num_top_stocks, path, False)

        # Optimize paramters
        optimizeParams()

        # Make prediction
        # weightings = {
        #     'count_ratio': 9,
        #     'return_log_ratio': 0.6,
        #     'total': 0.6
        # }
        # prediction(start_date, end_date, found_features, num_top_stocks, weightings)
        # return
        # Optimize features
        # return, bull_return_s, return_s, bull not useful
        # total, return, return_log, bear, bull_return_log_s, bull_return, bull_return_log not useful
        # count_ratio, return_ratio good



        # return_ratio, return_s_ratio, return_log_s, return_log_s_ratio USELESS

        # count_ratio: 6-10
        # return_log_ratio: 1-3
        # return_log: 0-2
        # bull_return_log_s: 0-2
        # combinedResults = {}
        # a = [[6,7,8,9,10],[1,1.5,2],[0,1,2],[0,0.5,1],[0,1,2,3],[0,1,2,3]]
        # allPossibilities = list(itertools.product(*a))
        # print(len(allPossibilities))
        # for combo in allPossibilities:
        #     # if (combo[0] == 0 and combo[1] == 0 and combo[2] == 0):
        #     #     continue
        #     paramWeightings = {
        #         'count_ratio': combo[0],
        #         'return_log_ratio': combo[1],
        #         'return_log_s_ratio': combo[2],
        #         'return_log': combo[3],
        #         'return_log_s': combo[4],
        #         'bull_return_log_s': combo[5]
        #     }
        #     (returns, accuracy) = prediction(start_date, end_date, found_features, num_top_stocks, paramWeightings)
        #     print(tuple(paramWeightings.items()), returns, accuracy)
        #     combinedResults[tuple(paramWeightings.items())] = (returns, accuracy)

        # bestParams = list(combinedResults.items())
        # bestParams.sort(key=lambda x: x[1], reverse=True)
        # print("--------")
        # for x in bestParams[:20]:
        #     print(x[0], x[1])

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
        cached_prices = readPickleObject('newPickled/averaged.pkl')
        # print(getTopStocksforWeek(datetime.datetime(2020, 1, 9, 15, 30), 20))

        
        # print(findCloseOpenCached('JNUG', datetime.datetime(2020, 5, 29, 15, 30), cached_prices))
        # for t in tweets:
        #     print(t)
        # for i in [1, 2, 3, 4, 5, 6, 1, 2, 3, 4, 5, 6,1, 2, 3, 4, 5, 6,1, 2, 3, 4, 5, 6,1, 2, 3, 4, 5, 6]:
        #     print("hi")
        # res = calculateUserFeatures('johnyyywardyy', datetime.datetime(2020, 6, 12), cached_prices)

        # arr = os.listdir('user_tweets/')
        # count = 0
        # for u in arr:
        #     username = u[:-4]
        #     editCachedTweets(username)
        #     count += 1
        #     if (count % 1000 == 0):
        #         print(count)

        # now = convertToEST(datetime.datetime.now())
        date = datetime.datetime(2020, 1, 9)
        delta = datetime.timedelta(days=7)

        while (date < datetime.datetime(2020, 6, 9)):
            print(getTopStocksforWeek(date, 20))
            date += delta

        # print(date)
        # stocks = getAllStocks()
        # print(len(stocks))
        # for i in range(len(stocks)):
        #     if (stocks[i] == "SESN"):
        #         print(i)
        # analyzeStocks(date, ['SNAP'])


        # stocks = getAllStocks()
        # print(dates)
        # findAllTweets(stocks, dates, True)
        # testing(35)
        # for i in range(5, 20):
        #     testing(i)
        # calcReturns(35)
        # stocks.remove('AMZN')
        # stocks.remove('SLS')
        # stocks.remove('CEI')

        # tweets = findAllTweets(stocks, dates)
        # updateBasicStockInfo(dates, stocks, tweets)
        # return
        # basicPrediction(dates, stocks, True)

        # time = datetime.datetime(2019, 12, 12, 16, 3)
        # print(findCloseOpen('AAPL', time))

        # updateAllCloseOpen(['TTNP'], dates)
        # for d in dates:
        #     print(d, closeToOpen('TVIX', d))
        # date = datetime.datetime(2019, 12, 16, 16, 10) - datetime.datetime(2019, 12, 16)
        # print(16 * 60 * 60)
        # print(date.total_seconds())
        # for i in range(11, 25):
        #     for j in range(0, 23):
        #         date = datetime.datetime(2019, 12, i, j, 10)
        #         # findCloseOpen('AAPL', date)
        #         print(date, findCloseOpen('AAPL', date))
        #         # print(date, round(findWeight(date, 'x'), 1))


        # exportCloseOpen()
        # calculateAllUserInfo()

        # getStatsPerUser('Buckeye1212')
        # print(getAllUserInfo('hirashima'))

        # print(len(findTweets(date, 'AAPL')))

        # getAllUserInfo('SDF9090')
        # print(weightedUserPrediction(getAllUserInfo('SDF9090'), ''))
        # transferNonLabeled(stocks)

        # findBadMessages('ArmedInfidel')
        # findTopUsers()
        # removeMessagesWithStock('AAPL')
        # findOutliers('GNCA')

        # findTopUsers()

        # setupUserInfos(updateObject=True)
        # findAllUsers()
        
        # findErrorUsers()

        # updateUserNotAnalyzed()
        # (setup, testing) = generateFeatures(dates, stocks, True)
        # basicPrediction(dates, stocks, False, False)
        # neuralnet()
        # updateBasicStockInfo(dates, stocks, findAllTweets(stocks, dates))


if __name__ == "__main__":
    main()
