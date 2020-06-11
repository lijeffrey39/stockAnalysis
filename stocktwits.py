import datetime
import optparse
import matplotlib. pyplot as plt
import math

from modules.helpers import (convertToEST, findTradingDays, getAllStocks,
                             insertResults, findWeight, writePickleObject, readPickleObject)
from modules.hyperparameters import constants
#from modules.nn import calcReturns, testing
from modules.prediction import (basicPrediction, findAllTweets, updateBasicStockInfo, setupUserInfos)
from modules.stockAnalysis import (findPageStock, getTopStocks, parseStockData,
                                   shouldParseStock, updateLastMessageTime,
                                   updateLastParsedTime, updateStockCount, getSortedStocks)
from modules.stockPriceAPI import (updateAllCloseOpen, transferNonLabeled, findCloseOpen, closeToOpen, getUpdatedCloseOpen, 
                                    getCloseOpenInterval, updateyfinanceCloseOpen)
from modules.userAnalysis import (findPageUser, findUsers, insertUpdateError,
                                  parseUserData, shouldParseUser, getStatsPerUser,
                                  updateUserNotAnalyzed, getAllUserInfo,
                                  calculateAllUserInfo, parseOldUsers)
from modules.tests import (findBadMessages, removeMessagesWithStock, 
                           findTopUsers, findOutliers, findAllUsers, findErrorUsers)


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

        insertUpdateError(coreInfo, reAnalyze, updateUser)
        insertResults(result)

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
        makePrediction(dateNow)
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
        print('')
        import yfinance as yf
        tick = yf.Ticker('AAPL')
        now = convertToEST(datetime.datetime.now())
        date1 = datetime.datetime(now.year, 5, 20, 12, 30)
        dateNow = datetime.datetime(now.year, now.month, now.day, 13, 30)
        dates = findTradingDays(date1, dateNow)
        count = 0
        for date in dates:
            print(date)
            yOpen = tick.history(start=date, end=date)[['Close']].values[0][0].item()
            print(type(yOpen))
            count+=1
        
        #db = constants['db_client'].get_database('stocks_data_db').yfin_close_open
        # import pickle
        # #allUsers = constants['db_user_client'].get_database('user_data_db').user_accuracy_v2.find()
        # userList = readPickleObject("pickledObjects/test.pkl")
        # newList = []
        # for val in userList:
        #     if val > 70:
        #         newList.append(math.sqrt(math.sqrt(val)))
        # # newList = list(map(lambda x:math.log10(x),newList))
        # plt.hist(newList, 10)
        # plt.show()

        # testing yfinance
        # import yfinance as yf
        # gss = ['BDX']
        # openDiff = closeDiff = 0
        # maxo = maxc = 0
        # for i in gss:
        #     print(i)
        #     tick = yf.Ticker(i)
        #     yesterday = convertToEST(datetime.datetime.now())-datetime.timedelta(days=4)
        #     print(yesterday)
        #     yOpen = tick.history(start=yesterday, end=yesterday)[['Open']].values[0][0].item()
        #     yClose = tick.history(start=yesterday, end=yesterday)[['Close']].values[0][0].item()   
        #     (ogClose, ogOpen, test, bleh) = getUpdatedCloseOpen(i, yesterday)
        #     # print('ours')
        #     print(test, ogClose)
        #     # print('yahoo')
        #     print(yOpen, yClose)
        #     print('diff')
        #     print(test-yOpen, ogClose-yClose)
        #     openDiff += abs(test-yOpen)
        #     closeDiff += abs(ogClose-yClose)
        #     if abs(test-yOpen) > maxo:
        #         maxo = abs(test-yOpen)
        #     if abs(ogClose-yClose) > maxc:
        #         maxc = abs(ogClose-yClose)

        # print('avg o diff: ' + str(openDiff/len(gss)))
        # print('avg c diff: ' + str(closeDiff/len(gss)))
        # print('maxo : ', maxo)
        # print('maxc : ', maxc)
        # print(ogClose)
        # print(ogOpen)
        
        # dateStart = datetime.datetime(2020, 6, 9, 12, 00)
        # dateEnd = datetime.datetime(2020, 6, 9, 16, 30)
        # stocks = getTopStocks(100)
        # stocks1 = getSortedStocks()[101:1001]
        # #test = ['MDR', 'I', 'HSGX', 'RTTR', 'UWT', 'JCP', 'SES', 'DWT', 'SPEX', 'RBZ', 'YUMA', 'BPMX', 'SNNA', 'PTIE', 'FOMX', 'TROV', 'HIIQ', 'S', 'XGTI', 'MDCO', 'NLNK', 'SSI', 'VLRX', 'ATIS', 'INNT', 'DCAR', 'CUR', 'AKS', 'FTNW', 'KEG', 'CNAT', 'MLNT', 'GNMX', 'AKRX', 'CLD', 'ECA', 'DCIX', 'PIR', 'DF', 'AXON', 'CIFS', 'XON', 'SBOT', 'KOOL', 'HAIR', 'ARQL', 'IPCI', 'ACHN', 'ABIL', 'RTN', 'AMR', 'FTR', 'DERM', 'CBS', 'OILU', 'JMU', 'CELG', 'DRYS', 'AGN', 'SBGL', 'UPL', 'VTL', 'BURG', 'DO', 'SN', 'PVTL', 'UTX', 'HEB', 'WFT', 'CY', 'SYMC', 'PTX', 'AKAO', 'AVP', 'GEMP', 'CBK', 'HABT', 'RARX', 'ORPN', 'IGLD', 'ROX', 'LEVB', 'CTRP', 'CARB', 'AAC', 'HK', 'CRZO', 'MNGA', 'PEGI', 'OHGI', 'ZAYO', 'GLOW', 'MLNX', 'COT', 'SORL', 'BBT', 'FGP', 'SGYP', 'STI', 'FCSC', 'NIHD', 'ONCE', 'ANFI', 'VSI', 'INSY', 'CVRS', 'GG', 'WIN', 'BRS', 'NVLN', 'EMES', 'CBLK', 'ARRY', 'ESV', 'HRS', 'APHB', 'RHT', 'CLDC', 'EPE', 'APC', 'ACET', 'DATA', 'SDLP', 'GHDX', 'OHRP', 'EDGE', 'DFRG', 'VSM', 'RGSE', 'ASNS', 'BSTI', 'CADC', 'MXWL', 'PETX', 'IMDZ', 'ATTU', 'RLM', 'OMED']
        # for i in stocks:
        #     print(i)
        #     tweets = clientStockTweets.get_database('tweets_db').tweets.find({"$and": [{'symbol': i},
        #                                                                     {'time': {'$gte': dateStart,
        #                                                                     '$lt': dateEnd}}]})
        #     print(tweets.count())
        # for i in tweets:
        #     print(i)

        # check last parsetime
        # stocks = getTopStocks(100)
        # stocks1 = getSortedStocks()[101:551]

        # db = constants['stocktweets_client'].get_database('stocks_data_db')
        # lastParsed = db.last_parsed
        # for i in stocks1:
        #     lastTime = lastParsed.find({'_id': i})
        #     print(str(i) + ':' + str(lastTime[0]))

        # db = clientStockTweets.get_database('stocks_data_db')
        # errors = db.stock_tweets_errors.find()
        # for i in errors:
        #     print(i)

        # now = convertToEST(datetime.datetime.now())
        # date = datetime.datetime(now.year, now.month, now.day)
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

        # calculateAllUserInfo()
        # getStatsPerUser('DaoofDow')
        # print(getAllUserInfo('sjs7'))

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
