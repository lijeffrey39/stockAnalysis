import datetime
import optparse
from modules.sung_nn import *
from random import shuffle

from modules.helpers import *
from modules.hyperparameters import constants
from modules.messageExtract import *
from modules.prediction import *
from modules.scroll import *
from modules.stockAnalysis import (shouldParseStock,
                                   findPageStock,
                                   parseStockData,
                                   updateLastParsedTime,
                                   updateLastMessageTime,
                                   getTopStocks)
from modules.stockPriceAPI import *
from modules.userAnalysis import (findUsers,
                                  shouldParseUser,
                                  findPageUser,
                                  parseUserData,
                                  insertUpdateError,
                                  getAllUserInfo,
                                  findUserInfoDriver,
                                  updateUserNotAnalyzed)
from modules.nn import testing
from svm import usefulFunctions

client = constants['db_client']
clientUser = constants['db_user_client']
clientStockTweets = constants['stocktweets_client']


def insertResults(results):
    collection = clientStockTweets.get_database('tweets_db').tweets
    count = 0
    total = 0
    for r in results:
        total += 1
        try:
            collection.insert_one(r)
            count += 1
        except Exception as e:
            # print(str(e))
            continue
    print(count, total)

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

        insertUpdateError(coreInfo, reAnalyze, updateUser)
        insertResults(result)


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

    parser.add_option('-p', '--prediction',
                      action='store_true', dest="prediction",
                      help="make prediction for today")

    parser.add_option('-c', '--updateCloseOpens',
                      action='store_true', dest="updateCloseOpens",
                      help="update Close open times")


# Make a prediction for given date
def makePrediction(date):
    currDay = datetime.datetime(date.year, date.month, date.day, 9, 30)
    nextDay = currDay + datetime.timedelta(days=1)
    dates = [currDay]

    stocks = getTopStocks(20)
    # print(stocks)
    # analyzeStocks(date, stocks)
    # stocks = ['TSLA', 'AAPL', 'ADXS']
    basicPrediction(dates, stocks)


def main():
    opt_parser = optparse.OptionParser()
    addOptions(opt_parser)
    options, args = opt_parser.parse_args()
    dateNow = convertToEST(datetime.datetime.now())

    if (options.users):
        analyzeUsers(reAnalyze=True, findNewUsers=False, updateUser=False)
    elif (options.stocks):
        now = convertToEST(datetime.datetime.now())
        date = datetime.datetime(now.year, now.month, now.day)
        stocks = getAllStocks()
        stocks.remove('SPY')
        stocks.remove('OBLN')
        analyzeStocks(date, stocks)
    elif (options.prediction):
        makePrediction(dateNow)
    elif (options.updateCloseOpens):
        stocks = getTopStocks(100)
        date = datetime.datetime(dateNow.year, 7, 22, 9, 30)
        dateUpTo = datetime.datetime(dateNow.year, 12, 1, 16)
        dates = findTradingDays(date, dateUpTo)
        updateAllCloseOpen(stocks, dates)
    else:
        date = datetime.datetime(dateNow.year, 7, 22, 9, 30)
        dateUpTo = datetime.datetime(dateNow.year, 11, 29, 16)
        dates = findTradingDays(date, dateUpTo)
        stocks = getTopStocks(100)

        # (setup, testing) = generateFeatures(dates, stocks, True)
        # print(setup['AAPL'][datetime.datetime(dateNow.year, 7, 25, 9, 30)])
        # basicPrediction(dates, stocks)
        neuralnet()
        # updateBasicStockInfo(dates, stocks)

        # analyzedUsers = constants['db_user_client'].get_database('user_data_db').users
        # query = {"$and": [{'error': ''}, {'last_updated': {'$exists': True}}]}
        # cursor = analyzedUsers.find(query)
        # users = list(map(lambda document: document['_id'], cursor))
        # print(len(users))
        # shuffle(users)
        # for u in users:
        #     print(u)
        #     getAllUserInfo(u)


if __name__ == "__main__":
    main()
