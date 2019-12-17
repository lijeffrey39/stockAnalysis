import datetime
import optparse

from modules.helpers import (convertToEST, findTradingDays, getAllStocks,
                             insertResults)
from modules.hyperparameters import constants
from modules.nn import calcReturns, testing
from modules.prediction import (basicPrediction, findAllTweets, updateBasicStockInfo)
from modules.stockAnalysis import (findPageStock, getTopStocks, parseStockData,
                                   shouldParseStock, updateLastMessageTime,
                                   updateLastParsedTime)
from modules.stockPriceAPI import updateAllCloseOpen
from modules.userAnalysis import (findPageUser, findUsers, insertUpdateError,
                                  parseUserData, shouldParseUser, getStatsPerUser,
                                  updateUserNotAnalyzed)


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
    dates = [datetime.datetime(date.year, date.month, 16, 9, 30)]
    stocks = getTopStocks(20)
    stocks.remove('AMZN')
    stocks.remove('SLS')
    stocks.remove('CEI')
    # analyzeStocks(date, stocks)
    basicPrediction(dates, stocks, True, True)


def main():
    opt_parser = optparse.OptionParser()
    addOptions(opt_parser)
    options, args = opt_parser.parse_args()
    dateNow = convertToEST(datetime.datetime.now())

    if (options.users):
        analyzeUsers(reAnalyze=False, findNewUsers=False, updateUser=True)
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
        date = datetime.datetime(dateNow.year, 11, 22, 9, 30)
        dateUpTo = datetime.datetime(dateNow.year, 12, 12, 16)
        dates = findTradingDays(date, dateUpTo)
        stocks = getTopStocks()
        # print(dates)
        # findAllTweets(stocks, dates, True)
        # testing(35)
        # for i in range(5, 20):
        #     testing(i)
        # calcReturns(35)
        stocks.remove('AMZN')
        stocks.remove('SLS')
        stocks.remove('CEI')
        # basicPrediction(dates, stocks)
        getStatsPerUser('Jeffkins')
        # updateUserNotAnalyzed()
        # (setup, testing) = generateFeatures(dates, stocks, True)
        # basicPrediction(dates, stocks, False, False)
        # neuralnet()
        # updateBasicStockInfo(dates, stocks, findAllTweets(stocks, dates))


if __name__ == "__main__":
    main()
