import datetime
import optparse
import multiprocessing
import matplotlib. pyplot as plt
import math
import time
import requests
import os
import yfinance as yf
import requests
import itertools
import json
import shelve
import sys


from modules.helpers import (convertToEST, findTradingDays,findAllDays,
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
                        
from modules.newPrediction import (findTweets, weightedUserPrediction, writeTweets, calculateUserFeatures, dailyPrediction, fetchTweets,
                                    editCachedTweets, prediction, findFeatures, pregenerateAllUserFeatures, pregenerateUserFeatures,
                                    saveUserTweets, cachedUserTweets, optimizeParams, findStockCounts, insertUser, modifyTweets, getTopStocksCached)


client = constants['db_client']
clientUser = constants['db_user_client']
clientStockTweets = constants['stocktweets_client']


# ------------------------------------------------------------------------
# ----------------------- Analyze Specific Stock -------------------------
# ------------------------------------------------------------------------


def analyzeStocks(date, stocks):
    dateString = date.strftime("%Y-%m-%d")
    print(stocks)
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
        now = convertToEST(datetime.datetime.now())
        if now.hour == 15 and now.minute == 30:
            print('bye bye')
            sys.exit()
        print('--------------------------')
        print(username)
        print("parsing at " + convertToEST(datetime.datetime.now()).strftime("%m/%d/%Y, %H:%M:%S"))
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
        usercollection = constants['stocktweets_client'].get_database('tweets_db').tweets
        now = convertToEST(datetime.datetime.now())
        query = {'$and': [{'user': username}, {'time': {'$gte': now - datetime.timedelta(days=28),
                                '$lt': now}}, { "$or": [{'isBull': True}, {'isBull': False}] }]}
        all_tweet_query =  query = {'$and': [{'user': username}, {'time': {'$gte': now - datetime.timedelta(days=28),
                                '$lt': now}}]}
        bb = usercollection.find(query).count()
        allc = usercollection.find(all_tweet_query).count()
        print(bb)
        print(allc)
        userdb = constants['db_user_client'].get_database('user_data_db').users
        x = userdb.update({'_id': username}, {'$set': {'bbcount': bb, 'allcount': allc}})
        insertResults(result)
        coreInfo['error'] = ''
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
    stocks = stockcount1000daily(date, 500)
    analyzeStocks(date, stocks[100:]) 

def main():
    opt_parser = optparse.OptionParser()
    addOptions(opt_parser)
    options, _ = opt_parser.parse_args()
    dateNow = convertToEST(datetime.datetime.now())

    if (options.users):
        while True:
            analyzeUsers(reAnalyze=False, findNewUsers=False, updateUser=True)
    elif (options.stocks):
        now = convertToEST(datetime.datetime.now())
        date = datetime.datetime(now.year, now.month, now.day)
        stocks = stockcount1000daily(date, 100)
        analyzeStocks(date, stocks) 
    elif (options.optimizer):
        optimizeParams()
    elif (options.prediction):
        num_top_stocks = 30 # Choose top 20 stocks of the week to parse
        start_date = datetime.datetime(2019, 6, 3, 15, 30)
        end_date = datetime.datetime(2020, 7, 1, 9, 30)

        # Write stock tweet files
        # writeTweets(start_date, end_date, num_top_stocks, overwrite=True)
        # return

        # Find features for prediction
        path = 'newPickled/stock_features.pkl'
        found_features = findFeatures(start_date, end_date, num_top_stocks, path, False)
        # return
        # Make prediction
        weightings = {
            'bull_w': 3.14,
            'bear_w': 0.74,
            'bull_w_return_w1': 1.28,
            'bear_w_return_w1': 0.46,
            # 'bull_w_return_log': 3,
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
        print()
        print(stockcount1000daily(convertToEST(datetime.datetime.now()), 100))
        # now = convertToEST(datetime.datetime.now())
        # collection = constants['stocktweets_client'].get_database('tweets_db').tweets.find({'$and': [{'symbol': 'SPY'}, {'time': {'$gte': now - datetime.timedelta(hours=3)}}]})
        # for i in collection:
            # print(i)
        # userdb = constants['db_user_client'].get_database('user_data_db').users
        # for i in userdb:
        #     print(i)
        # print(userdb.find({"error" : {'$regex' : ".*chrome.*"}})[0])
        

        # x = constants['stocktweets_client'].get_database('tweets_db').tweets.find()
        # for i in x:
        #     print(i)
        # old = constants['db_client'].get_database('stocks_data_db').updated_close_open

        # oldYF = constants['db_client'].get_database('stocks_data_db').yfin_close_open.find()
        # newYF = constants['db_user_client'].get_database('user_data_db').yfin_close_open
        # print(oldYF.count())
        # print(newYF.find().count())
        # for i in oldYF[507898:]:
        #      newYF.replace_one(i, i, upsert=True)
        # print(newYF.find().count())

        # new = constants['db_user_client'].get_database('user_data_db').updated_close_open.find()
        
        # print(old.count())
        # print(new.find().count())
        # for i in old[514022:]:
        #      new.replace_one(i, i, upsert=True)
        # print(new.find().count())
        # stock_counts_collection = constants['db_user_client'].get_database('user_data_db').daily_stockcount.find()
        # for i in stock_counts_collection:
        #     print('')
        #     print(i)
        # start_date = datetime.datetime(2019, 7, 12, 00, 00)
        # end_date = datetime.datetime(2020, 7, 2, 00, 00)
        # td = datetime.timedelta(days=1)
        # while (start_date <= end_date):
        #     stockcount1000daily(start_date)
        #     start_date+=td
        # # start_date = datetime.datetime(2019, 6, 10, 15, 30)
        # end_date = datetime.datetime(2020, 6, 28, 9, 30)
        # td = datetime.timedelta(days=1)
        # while (start_date <= end_date):
        #     stockcount1000daily(start_date)
        #     start_date+=td
        # usercollection = constants['db_user_client'].get_database('user_data_db').users.find({ 'bbcount': { '$exists': True }})
        # res = []
        # for i in usercollection:
        #     if i['bbcount'] > 1 and i['bbcount'] < 20:
        #         res.append(i['bbcount'])
        # # print(len(res))
        # print(len(res))
        # plt.hist(res, density=False, bins=150)
        # plt.show()
        # res = pregenerateUserFeatures('tony93')
        # date_start = datetime.datetime(2020, 6, 27)

        # tweets = fetchTweets(datetime.datetime(2020, 7, 3), datetime.datetime(2020, 7, 4), 'SPY')
        # for t in tweets:
        #     print(t)

        # date_start = datetime.datetime(2019, 6, 27)
        # stock_counts = readPickleObject('newPickled/stock_counts_14.pkl')
        # print(getTopStocksCached(date_start, 40, stock_counts))


        # i = {'symbol': 'UPS', 'user': 'Discipline15', 'time': datetime.datetime(2020, 6, 29, 3, 9), 'isBull': True, 'likeCount': 3, 'commentCount': 0, 'messageText': '$UPS long to 140+ by next year.'}
        # collection = constants['stocktweets_client'].get_database('tweets_db').tweets

        # i = {'symbol': 'UPS', 'user': 'Discipline15', 'time': datetime.datetime(2020, 6, 29, 3, 9), 'isBull': True, 'likeCount': 3, 'commentCount': 0, 'messageText': '$UPS long to 140+ by next year.'}
        # collection = constants['stocktweets_client'].get_database('tweets_db').tweets

        # query = {'user': 'tony93'}
        # query = {'user': 'JacquesStrap'}
        # tweets = list(collection.find(query))
        # for t in tweets:
        #     print(t)

        # query = {
        #     'symbol': 'UPS',
        #     'user': 'Discipline15',
        #     'time': {'$gte': datetime.datetime(2020, 6, 29), '$lt': datetime.datetime(2020, 6, 29, 23, 59)},
        #     'isBull': True,
        #     'messageText': '$UPS long to 140+ by next year.'
        # }
        # res = collection.replace_one(query, i, upsert=True)
        # print(res.matched_count)
        # print(res.modified_count)

        # modifyTweets()
        # path = 'stock_files/' + 'TSLA.pkl'
        # tweets_per_stock = readPickleObject(path)

        # for t in tweets_per_stock['2019-06-07']:
        #     print(t['time'])
        # result = readPickleObject('newPickled/user_features.pickle')
        # for d in result['Discipline15']['general']:
        #     print(d, result['Discipline15']['general'][d]['num_predictions'])

        # date_end = datetime.datetime(2020, 6, 11)
        # modifyTweets()
        # tweets = list(col.find(query))
        # tweets = list(map(lambda t: {'user': t['user'], 'time': t['time'], 'w': findWeight(t['time'], 'log(x)'), 'isBull': t['isBull']}, tweets))
        # for t in tweets:
        #     print(t)
        # pregenerateAllUserFeatures()
        # for d in res['general']:
        #     print(d, res['general'][d]['num_predictions'])


        # res = pregenerateUserFeatures('zredpill')
        # for d in res['per_stock']['SPY']:
        #     print(d, res['per_stock']['SPY'][d]['num_predictions'])
        # for d in res['general']:
        #     print(d, res['general'][d])
        # writePickleObject('data_1.pkl', res)
        # demo = dir_archive('demo', serialized=True, cached=False)
        # demo['tony93'] = res

        # db = dir_archive('demo', serialized=True, cached=False)

        # print(time.time())
        # x = db['tony93']
        # print(time.time())
        # print(x)

        # insertUser()
        # print(res)



        #dailyPrediction(datetime.datetime(2020, 6, 30))
        # dailyPrediction(datetime.datetime(2020, 7, 1))


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
        # date = datetime.datetime(2019, 1, 1)
        # delta = datetime.timedelta(days=7)
        # # result = []
        # while (date < datetime.datetime(2019, 6, 26)):
        #     updateStockCountPerWeek(date)
        # #     d = getTopStocksforWeek(date, 15)
        # #     print(date, d)
        #     date += delta
        #     for s in d:
        #         if (s not in result):
        #             result.append(s)

        # print(result)
        # updateStockCountPerWeek(datetime.datetime(2020, 6, 29))
        # print(findWeight(datetime.datetime(2020, 6, 23, 9), 'log(x)'))

        

if __name__ == "__main__":
    main()
