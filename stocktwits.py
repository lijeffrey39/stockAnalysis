import datetime
import optparse
import matplotlib. pyplot as plt
import math
import yfinance as yf
import requests

from modules.helpers import (convertToEST, findTradingDays, getAllStocks, recurse,
                             insertResults, findWeight, writePickleObject, readPickleObject)
from modules.hyperparameters import constants
from modules.prediction import (basicPrediction, findAllTweets, updateBasicStockInfo, setupUserInfos)
from modules.stockAnalysis import (findPageStock, getTopStocks, parseStockData, getTopStocksforWeek,
                                   shouldParseStock, updateLastMessageTime, updateStockCountPerWeek,
                                   updateLastParsedTime, updateStockCount, getSortedStocks)
from modules.stockPriceAPI import (updateAllCloseOpen, transferNonLabeled, findCloseOpen, closeToOpen, getUpdatedCloseOpen, 
                                    getCloseOpenInterval, updateyfinanceCloseOpen, exportCloseOpen)
from modules.userAnalysis import (findPageUser, findUsers, insertUpdateError,
                                  parseUserData, shouldParseUser, getStatsPerUser,
                                  updateUserNotAnalyzed,
                                  calculateAllUserInfo, parseOldUsers)
from modules.tests import (findBadMessages, removeMessagesWithStock, 
                           findTopUsers, findOutliers, findAllUsers, findErrorUsers)
                        
from modules.newPrediction import (findTweets, weightedUserPrediction, writeTweets,
                                    prediction, findFeatures, updateAllUsers)


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
    users = ['SDF9090']
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
        analyzeUsers(reAnalyze=False, findNewUsers=True, updateUser=False)
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
        start_date = datetime.datetime(2020, 3, 5, 9, 30)
        end_date = datetime.datetime(dateNow.year, dateNow.month, dateNow.day)
        
        # Write all user files
        # updateAllUsers()

        # Write stock tweet files
        # writeTweets(start_date, end_date, num_top_stocks)

        # Find features for prediction
        path = 'newPickled/features_new.pkl'
        found_features = findFeatures(start_date, end_date, num_top_stocks, path, False)

        # Make prediction
        weightings = {
            'total': 1,
            'return_log': 1,
            'return_ratio': 3,
            'return_s': 1,
            'bull_return_s': 1,
            'bull': 1,
            'count_ratio': 3
        }
        prediction(start_date, end_date, found_features, num_top_stocks, weightings)

        # Optimize features
        # return, bull_return_s, return_s not useful
        # combinedResults = {}
        # allPossibilities = []
        # recurse([1, 1, 1, 1, 1] * 1, 0, 3, set([]), allPossibilities)
        # print(len(allPossibilities))
        # for combo in allPossibilities:
        #     paramWeightings = {
        #         'total': combo[0],
        #         'return_log': combo[1],
        #         'count_ratio': combo[2], 
        #         'return_ratio': 3, 
        #         'bull_return_s': combo[3],
        #         'bull': combo[4]
        #     }
        #     (returns, accuracy) = prediction(dates, stocks, found_features, paramWeightings)
        #     print(tuple(paramWeightings.items()), returns, accuracy)
        #     combinedResults[tuple(paramWeightings.items())] = (returns, accuracy)

        # bestParams = list(combinedResults.items())
        # bestParams.sort(key=lambda x: x[1], reverse=True)
        # for x in bestParams[:25]:
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
        now = convertToEST(datetime.datetime.now())
        date = datetime.datetime(2020, 1, 6)
        delta = datetime.timedelta(days=7)

        while (date < now - delta):
            updateStockCountPerWeek(date)
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
