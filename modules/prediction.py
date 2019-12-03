import ast
import csv
import datetime
import math
import os
import pickle
import statistics
import time
from functools import reduce

from dateutil.parser import parse

from .helpers import (readPickleObject,
                      writePickleObject,
                      writeToCachedFile,
                      cachedCloseOpen,
                      recurse,
                      calcRatio)
from .hyperparameters import constants
from .messageExtract import *
from .stockPriceAPI import *


# ------------------------------------------------------------------------
# ----------------------------- Variables --------------------------------
# ------------------------------------------------------------------------


CREATED_DICT_USERS = False
dictPredictions = {}
dictAccuracy = {}


# ------------------------------------------------------------------------
# ----------------------------- Functions --------------------------------
# ------------------------------------------------------------------------


# Build result for sentiment of tweets
def buildResult():
    result = {'totalLabeledTweets': 0}
    for start in ['', 'U']:
        for ending in ['Return', 'ReturnUnique']:
            for second in ['user', 'stock']:
                for label in ['Bull', 'Bear']:
                    result[start + second + label + ending] = 0.0
    for label in ['bull', 'bear']:
        for start in ['', 'U']:
            result[start + label + 'Count'] = 0
    for start in ['', 'U']:
        for ending in ['Return', 'ReturnUnique']:
            for second in ['user', 'stock']:
                result[start + second + ending + 'Ratio'] = 0.0
    return result


# Calculate features based on list of tweets
def newCalculateSentiment(tweets, symbol, userAccDict):
    usersTweeted = {'bull': set([]), 'bear': set([])}
    result = buildResult()

    for tweet in tweets:
        username = tweet['user']
        isBull = tweet['isBull']
        result['totalLabeledTweets'] += 1
        if (username not in userAccDict or symbol not in userAccDict[username]['perStock']):
            continue

        lWord = 'bull'
        uWord = 'Bull'
        if (isBull is False):
            lWord = 'bear'
            uWord = 'Bear'

        userInfo = userAccDict[username]
        stockInfo = userInfo['perStock'][symbol]
        if (stockInfo[lWord + 'ReturnCloseOpen'] > 0):
            result['user' + uWord + 'Return'] += userInfo[lWord + 'ReturnCloseOpen']
            result['user' + uWord + 'ReturnUnique'] += userInfo[lWord + 'ReturnUnique']
            result['stock' + uWord + 'Return'] += stockInfo[lWord + 'ReturnCloseOpen']
            result['stock' + uWord + 'ReturnUnique'] += stockInfo[lWord + 'ReturnUnique']
            result[lWord + 'Count'] += 1
            if (username not in usersTweeted[lWord]):
                usersTweeted[lWord].add(username)
                result['Uuser' + uWord + 'Return'] += userInfo[lWord + 'ReturnCloseOpen']
                result['Uuser' + uWord + 'ReturnUnique'] += userInfo[lWord + 'ReturnUnique']
                result['Ustock' + uWord + 'Return'] += stockInfo[lWord + 'ReturnCloseOpen']
                result['Ustock' + uWord + 'ReturnUnique'] += stockInfo[lWord + 'ReturnUnique']
                result['U' + lWord + 'Count'] += 1

    for start in ['', 'U']:
        for ending in ['Return', 'ReturnUnique']:
            for second in ['user', 'stock']:
                result[start + second + ending + 'Ratio'] = calcRatio(result[second + 'Bull' + ending],
                          result[second + 'Bear' + ending])

    result['countRatio'] = calcRatio(result['bullCount'], result['bearCount'])
    result['UCountRatio'] = calcRatio(result['UbullCount'], result['UbearCount'])
    result['totalLabeledTweetsUsed'] = result['bullCount'] + result['bearCount']
    result['UtotalLabeledTweetsUsed'] = result['UbullCount'] + result['UbearCount']
    return result


# Close opens from saved file
def setupCloseOpen(dates, stocks, updateObject=False):
    print("Setup Close Open Info")
    path = 'pickledObjects/closeOpen.pkl'
    result = readPickleObject(path)
    if (updateObject is False):
        return result

    for symbol in stocks:
        if (symbol not in result):
            result[symbol] = {}
        for date in dates:
            if (date not in result[symbol]):
                print(date, symbol)
                dayRes = cachedCloseOpen(symbol, date)
                if (dayRes is None):
                    continue
                result[symbol][date] = cachedCloseOpen(symbol, date)

    writePickleObject(path, result)
    return result


# User Infos from saved file
def setupUserInfos(stocks, updateObject=False):
    print("Setup User Info")
    path = 'pickledObjects/userInfos.pkl'
    result = readPickleObject(path)
    if (updateObject is False):
        return result

    result = {}
    for symbol in stocks:
        accuracy = constants['db_user_client'].get_database('user_data_db').new_user_accuracy
        allUsersAccs = accuracy.find({'perStock.' + symbol: {'$exists': True}})
        for user in allUsersAccs:
            if (user['_id'] not in result):
                result[user['_id']] = user

    writePickleObject(path, result)
    return result


# Stock Infos from saved file
def setupStockInfos(stocks, updateObject=False):
    print("Setup Stock Info")
    path = 'pickledObjects/stockInfos.pkl'
    result = readPickleObject(path)
    if (updateObject is False):
        return result

    basicStockInfo = constants['stocktweets_client'].get_database('stocks_data_db').training_stock_info_1201
    result = {}
    for symbol in stocks:
        symbolInfo = basicStockInfo.find_one({'_id': symbol})
        result[symbol] = symbolInfo
    writePickleObject(path, result)
    return result


def setupResults(dates, keys):
    results = {}
    for date in dates:
        results[date] = {}
        results[date]['params'] = {}
        results[date]['closeOpen'] = {}
        results[date]['params'] = buildResult()
        for k in results[date]['params']:
            results[date]['params'][k] = {}
        for k in keys:
            results[date]['params'][k] = {}
    return results


def findAllTweets(stocks, dates, updateObject=False, dayPrediction=False):
    print("Setup Tweets")
    path = 'pickledObjects/testing.pkl'
    result = readPickleObject(path)
    if (updateObject is False):
        return result

    if (dayPrediction):
        result = {}
    tweetsDB = constants['stocktweets_client'].get_database('tweets_db')
    for symbol in stocks:
        print(symbol)
        if (symbol not in result):
            result[symbol] = {}
        for date in dates:
            d = date.strftime('%m/%d/%Y')
            if (d not in result[symbol]):
                result[symbol][d] = []
                dateStart = datetime.datetime(date.year,
                                              date.month, date.day, 9, 30)
                dateEnd = datetime.datetime(date.year,
                                            date.month, date.day, 16, 0)
                query = {"$and": [{'symbol': symbol},
                                  {"$or": [
                                        {'isBull': True},
                                        {'isBull': False}
                                  ]},
                                  {'time': {'$gte': dateStart,
                                            '$lt': dateEnd}}]}
                tweets = list(tweetsDB.tweets.find(query))
                for tweet in tweets:
                    result[symbol][d].append(tweet)

                tweets = list(map(lambda x: [x['time'], x['isBull'], x['commentCount'],
                                             x['likeCount'], x['user']], tweets))

                if (dayPrediction is False):
                    with open('./cachedTweets/' + symbol + '.csv', "a") as f:
                        csvWriter = csv.writer(f, delimiter=',')
                        csvWriter.writerows(tweets)

    if (dayPrediction is False):
        writePickleObject(path, result)
    return result


def simpleWeightPredictionReturns(date, results, paramWeightings):
    summedDict = {}
    for param in paramWeightings:
        if (param == 'numStocks'):
            continue
        resultsForDay = results[date]['params'][param]
        paramWeight = paramWeightings[param]
        for symbol in resultsForDay:
            if (symbol not in summedDict):
                summedDict[symbol] = (resultsForDay[symbol] * paramWeight)
            else:
                summedDict[symbol] += (resultsForDay[symbol] * paramWeight)

    resPerParam = list(summedDict.items())
    resPerParam.sort(key=lambda x: abs(x[1]), reverse=True)
    resPerParam = resPerParam[:paramWeightings['numStocks']]
    sumDiffs = reduce(lambda a, b: a + b,
                      list(map(lambda x: abs(x[1]), resPerParam)))

    returnToday = 0
    for symbolObj in resPerParam:
        symbol = symbolObj[0]
        stdDev = symbolObj[1]
        if symbol not in results[date]['closeOpen']:
            continue
        closeOpen = results[date]['closeOpen'][symbol]
        try:
            returnToday += ((stdDev / sumDiffs) * closeOpen)
        except:
            continue
    try:
        mappedResult = list(map(lambda x: [x[0], round(x[1] / sumDiffs * 100, 2), results[date]['closeOpen'][x[0]]], resPerParam))
    except:
        mappedResult = list(map(lambda x: [x[0], round(x[1] / sumDiffs * 100, 2)], resPerParam))
    # print(date, round(returnToday, 3), mappedResult)
    return (returnToday, mappedResult)


# Basic prediction algo
def basicPrediction(dates, stocks):
    userInfos = setupUserInfos(stocks)
    stockInfos = setupStockInfos(stocks)
    closeOpenInfos = setupCloseOpen(dates, stocks)
    allTweets = findAllTweets(stocks, dates, True, True)
    results = setupResults(dates, constants['keys'])
    combinedResult = 0

    for symbol in stocks:
        print(symbol)
        symbolInfo = stockInfos[symbol]
        for date in dates:
            if (date.strftime('%m/%d/%Y') not in allTweets[symbol]):
                continue
            tweets = allTweets[symbol][date.strftime('%m/%d/%Y')]
            sentiment = newCalculateSentiment(tweets, symbol, userInfos)
            for param in sentiment:
                paramVal = sentiment[param]
                paramMean = symbolInfo[param]['mean']
                paramStd = symbolInfo[param]['stdev']
                if (paramStd == 0.0):
                    results[date]['params'][param][symbol] = 0
                    continue
                stdDev = round((paramVal - paramMean) / paramStd, 2)
                results[date]['params'][param][symbol] = stdDev
            if (date not in closeOpenInfos[symbol]):
                continue
            closeOpen = closeOpenInfos[symbol][date]
            if (closeOpen is None):
                continue
            results[date]['closeOpen'][symbol] = closeOpen[2]

    symbolReturns = {}
    symbolCounts = {}
    for date in dates:
        # params = ['numStocks']
        # allPossibilities = []
        # recurse([0] * 1, 0, 6, set([]), allPossibilities)
        # for combo in allPossibilities:
        #     paramWeightings = {'stockReturnUniqueRatio': 1, 
        #                        'stockReturnRatio': 2,
        #                        'UCountRatio': 5,
        #                        'UuserReturnRatio': 1,
        #                        'userReturnRatio': 1,
        #                        'UstockReturnRatio': 2,
        #                        'UstockBullReturnUnique': 5,
        #                        'userReturnUniqueRatio': 1,
        #                        'countRatio': 3}
        #     for i in range(len(params)):
        #         paramWeightings[params[i]] = combo[i]

        #     try:
        #         returns = simpleWeightPredictionReturns(date, results, paramWeightings)
        #     except:
        #         continue
        #     if (tuple(paramWeightings.items()) not in combinedResults):
        #         combinedResults[tuple(paramWeightings.items())] = [returns]
        #     else:
        #         combinedResults[tuple(paramWeightings.items())].append(returns)

        paramWeightings = {'stockReturnUniqueRatio': 1,
                            'stockReturnRatio': 2,
                            'UCountRatio': 5,
                            'UuserReturnRatio': 1,
                            'userReturnRatio': 1,
                            'UstockReturnRatio': 2,
                            'UstockBullReturnUnique': 5,
                            'userReturnUniqueRatio': 1,
                            'countRatio': 3,
                            'numStocks': 3}
        returns, listReturns = simpleWeightPredictionReturns(date, results, paramWeightings)
        print(date, round(returns, 3), listReturns)
        for s in listReturns:
            if (len(s) == 2):
                continue
            symbol = s[0]
            val = 0
            if ((s[1] < 0 and s[2] < 0) or (s[1] > 0 and s[2] > 0)):
                val = abs(s[2])
            else:
                val = -s[2]
            if (symbol not in symbolReturns):
                symbolReturns[symbol] = val
                symbolCounts[symbol] = {}
                symbolCounts[symbol]['y'] = 1
                if (val > 0):
                    symbolCounts[symbol]['x'] = 1
            else:
                symbolReturns[symbol] += val
                symbolCounts[symbol]['y'] += 1
                if (val > 0):
                    if ('x' not in symbolCounts[symbol]):
                        symbolCounts[symbol]['x'] = 1
                    else:
                        symbolCounts[symbol]['x'] += 1
        combinedResult += returns
    print(combinedResult)

    bestParams = list(symbolReturns.items())
    bestParams.sort(key=lambda x: x[1], reverse=True)
    for x in bestParams:
        print(x)

    otherBest = list(symbolCounts.items())
    otherBest.sort(key=lambda x: x[1]['x'] / x[1]['y'], reverse=True)
    for x in otherBest:
        print(x)

    # bestParams = list(combinedResults.items())
    # bestParams.sort(key=lambda x: sum(x[1]), reverse=True)
    # for x in bestParams[:50]:
    #     print(x[0], sum(x[1]))


def generateFeatures(dates, stocks, updateObject=False):
    path = 'pickledObjects/features.pkl'
    if (updateObject is False):
        features = readPickleObject(path)
        testing = [datetime.datetime(2019, 11, 19, 9, 30), datetime.datetime(2019, 10, 23, 9, 30), datetime.datetime(2019, 10, 4, 9, 30), datetime.datetime(2019, 9, 24, 9, 30), datetime.datetime(2019, 11, 15, 9, 30), datetime.datetime(2019, 11, 13, 9, 30), datetime.datetime(2019, 8, 1, 9, 30), datetime.datetime(2019, 7, 24, 9, 30), datetime.datetime(2019, 10, 8, 9, 30), datetime.datetime(2019, 10, 14, 9, 30), datetime.datetime(2019, 8, 27, 9, 30), datetime.datetime(2019, 10, 30, 9, 30), datetime.datetime(2019, 8, 7, 9, 30), datetime.datetime(2019, 8, 22, 9, 30), datetime.datetime(2019, 8, 2, 9, 30), datetime.datetime(2019, 10, 9, 9, 30), datetime.datetime(2019, 10, 16, 9, 30), datetime.datetime(2019, 9, 23, 9, 30)]
        return (features, testing)

    allTweets = findAllTweets(stocks, dates)
    shuffle(dates)
    training = dates[:75]
    testing = dates[75:]
    print(testing)

    # Generate means and std for stocks
    # updateBasicStockInfo(training, stocks, allTweets)

    features = {}
    accuracy = constants['db_user_client'].get_database('user_data_db').new_user_accuracy
    for symbol in stocks:
        print(symbol)
        features[symbol] = {}
        allUsersAccs = accuracy.find({'perStock.' + symbol: {'$exists': True}})
        userAccDict = {}
        for user in allUsersAccs:
            userAccDict[user['_id']] = user

        for date in training:
            if (date.strftime('%m/%d/%Y') not in allTweets[symbol]):
                continue
            features[symbol][date] = {}
            tweets = allTweets[symbol][date.strftime('%m/%d/%Y')]
            sentiment = newCalculateSentiment(tweets, symbol, userAccDict)
            for k in sentiment:
                features[symbol][date][k] = sentiment[k]

    writePickleObject(path, features)
    return features


# Updates stock mean and standard deviation
def updateBasicStockInfo(dates, stocks, allTweets):
    basicStockInfo = constants['stocktweets_client'].get_database('stocks_data_db').training_stock_info_svm

    for symbol in stocks:
        accuracy = constants['db_user_client'].get_database('user_data_db').new_user_accuracy
        allUsersAccs = accuracy.find({'perStock.' + symbol: {'$exists': True}})
        userAccDict = {}
        for user in allUsersAccs:
            userAccDict[user['_id']] = user

        symbolInfo = {'_id': symbol}
        found = basicStockInfo.find_one({'_id': symbol})
        if (found is not None):
            continue

        print(symbol)
        for date in dates:
            if (date.strftime('%m/%d/%Y') not in allTweets[symbol]):
                continue
            tweets = allTweets[symbol][date.strftime('%m/%d/%Y')]
            sentiment = newCalculateSentiment(tweets, symbol, userAccDict)
            if ('countRatio' not in symbolInfo):
                for k in sentiment:
                    symbolInfo[k] = [sentiment[k]]
            else:
                for k in sentiment:
                    symbolInfo[k].append(sentiment[k])

        for k in symbolInfo:
            if (k != '_id'):
                vals = symbolInfo[k]
                symbolInfo[k] = {}
                symbolInfo[k]['mean'] = statistics.mean(vals)
                symbolInfo[k]['stdev'] = statistics.stdev(vals)
        basicStockInfo.insert_one(symbolInfo)



# Finds the returns based on predictions made from topStocks
def calcReturnBasedResults(date, result):
    totalsReturns = []
    afterDate = datetime.datetime(date.year, date.month, date.day, 9, 30)
    afterDate += datetime.timedelta(1)
    while (helpers.isTradingDay(afterDate) == False):
        afterDate += datetime.timedelta(1)

    for i in range(5):
        if (i % 5 == 0):
            totalReturn = 0
            pos = 0
            neg = 0
            res = []

            for x in result:
                symbol = x[0]
                priceBefore = x[1]
                shares = x[3]
                totalBefore = priceBefore * shares
                diff = 0
                priceAfter = savedPricesStocks(afterDate, symbol)

                totalAfter = priceAfter * shares
                diff = totalAfter - totalBefore
                if (diff >= 0):
                    pos += 1
                else:
                    neg += 1

                # print(symbol, diff, priceBefore, priceAfter)
                totalReturn += diff
                res.append([symbol, diff])

            totalReturn = round(totalReturn, 2)
            totalsReturns.append([totalReturn, afterDate])
            return (totalReturn, pos, neg, res)

        afterDate = afterDate + datetime.timedelta(minutes = 1)



# Want to scale between the top cutoff with > 0 return and bottom cutoff with < 0 return
def createDictUsers():
    global dictAccuracy
    global dictPredictions

    users = readMultiList('userInfo.csv')
    users = list(filter(lambda x: len(x) >= 4, users))

    cutoff = 0.98
    topPercent = list(filter(lambda x: float(x[3]) > 0, users))
    topPercentIndex = int(len(topPercent) * (cutoff))
    maxPercent = float(topPercent[len(topPercent) - topPercentIndex][3])

    bottomPercent = list(filter(lambda x: float(x[3]) < 0, users))
    bottomPercentIndex = int(len(bottomPercent) * (cutoff))
    minPercent = float(bottomPercent[bottomPercentIndex][3])

    totalPredictionsList = list(map(lambda x: int(float(x[1]) + float(x[2])), users))
    maxNumPredictionsLog = math.log(max(totalPredictionsList))

    # Find user's accuracy scaled by max and min percent as well as number of prediction
    for user in users:
        username = user[0]
        percent = float(user[3])
        numPredictions = int(float(user[1]) + float(user[2]))
        dictPredictions[username] = (math.log(numPredictions) / maxNumPredictionsLog) - 0.5
        if (percent > 0):
            percent = maxPercent if (percent >= maxPercent) else percent
            dictAccuracy[username] = percent / maxPercent
        else:
            percent = minPercent if (percent <= minPercent) else percent
            dictAccuracy[username] = percent / minPercent
    return


# Save the current day's stock price at 4pm and next day's prices at 9 am for all stocks
def saveStockPricesDay(date, stocks, afterDate):
    # Time at 4pm for current date
    path = date.strftime("stocksResults/%m-%d-%y-%I_savedStocks.csv")
    if (os.path.isfile(path) == False): 	# create empty file
        with open(path, "w") as my_empty_csv:
            pass
    else:
        return

    stockList = []
    for s in stocks:
        (historical, dateTimeAdjusted) = stockPriceAPI.findHistoricalData(date, s, False)

        print(s, len(historical))
        for i in range(6):
            date = datetime.datetime(date.year, date.month, date.day, 9, (i * 5) + 30)
            dateString = date.strftime("%m-%d-%y-%I:%M_") + s
            priceAtPost = stockPriceAPI.priceAtTime(date, historical) # Price at the time of posting
            stockList.append([dateString, priceAtPost])
            print(priceAtPost)

    stockList.sort(key = lambda x: x[0])
    writeSingleList(path, stockList)

    return


# Save all the stock prices at 4 pm and 9 am the next day
def savePricesToFile(date, stocks):
    # Time at 4pm for current date
    beforeDate = datetime.datetime(date.year, date.month, date.day, 15, 59)
    saveStockPricesDay(beforeDate, stocks, False)

    # Time at 9:30 for next day
    afterDate = datetime.datetime(date.year, date.month, date.day, 9, 30)
    afterDate += datetime.timedelta(1)
    while (helpers.isTradingDay(afterDate) == False):
        afterDate += datetime.timedelta(1)

    saveStockPricesDay(afterDate, stocks, True)




# Ideal when enough user information collected

# Current weightings for predictions
# 1. Number of stocks to pick from (higher means lower risk)
# 2. Accuracy for that user overall
# 3. Accuracy for that user for that specific stock
# 4. How many predictions this user has made relative to everyone else
# 5. How many predictions this user has made relative to people predicting this stock

# Other weights to add
# 6. Number of likes/comments for a prediction
# 7. Number of followers (If in thousands, remove k and multiply by 1,000)
# 8. How old of a member he/she is

# TODO
# 8. Find weight of a particular sector/industry


def topStocks(date, money, weights):

    # path = date.strftime("stocksResults/%m-%d-%y/")
    pathWeighted = date.strftime("stocksResults/%m-%d-%y_weighted.csv")
    folderPath = date.strftime("stocksResults/%m-%d-%y/")

    # if not created yet
    if ((not os.path.exists(folderPath))):
        return

    stocks = [f for f in os.listdir(folderPath) if os.path.isfile(os.path.join(folderPath, f))]
    stocks = list(map(lambda x: x[:len(x) - 4], stocks))
    stocks = list(filter(lambda x: '.DS_S' not in x, stocks))

    # Save all the stock prices at 4 pm and 9 am the next day
    savePricesToFile(date, stocks)


    users = readMultiList('userInfo.csv')
    users = list(filter(lambda x: len(x) >= 4, users))
    mappedUsers = set(list(map(lambda x: x[0], users)))
    result = []


    numStocks = weights[0]
    uAccW = weights[1]
    uStockAccW = weights[2]
    uPredW = weights[3]
    uStockPredW = weights[4]

    global CREATED_DICT_USERS
    if (CREATED_DICT_USERS == False):
        createDictUsers()
        CREATED_DICT_USERS = True

    totalUsers = 0
    totalHits = 0

    # Find weight for each stock
    for symbol in stocks:
        resPath = folderPath + symbol + ".csv"
        resSymbol = readMultiList(resPath)
        total = 0

        # scale based on how accurate that user is
        topUsersForStock = readMultiList('templists/' + symbol + '.csv')

        # safety check cuz len(topUsersForStock) must be  > 1
        if (len(topUsersForStock) < 2):
            continue

        try:
            maxPercent = math.log(abs(float(topUsersForStock[0][1])))
        except:
            maxPercent = 0.1

        try:
            minPercent = -1 * math.log(abs(float(topUsersForStock[len(topUsersForStock) - 1][1])))
        except:
            minPercent = -0.1

        if (maxPercent == 0.0):
            maxPercent = 0.1
        if (minPercent == 0.0):
            minPercent = 0.1


        dictUserStockAccuracy = {}
        dictUserStockPredictions = {}
        for u in topUsersForStock:
            user = u[0]
            percent = float(u[1])
            dictUserStockPredictions[user] = (float(u[2]) / 100.0) - 0.5
            if (percent == 0.0):
                dictUserStockAccuracy[user] = 0
                continue

            percentLog = math.log(abs(percent))
            if (percent > 0):
                dictUserStockAccuracy[user] = percentLog / maxPercent
            else:
                dictUserStockAccuracy[user] = -1 * percentLog / minPercent

        for r in resSymbol:
            user = r[0]
            if (r[1] == ''):
                continue
            isBull = bool(r[1])

            totalUsers += 1
            # Only based no user info's that's been collected
            if (user in mappedUsers):
                totalHits += 1
                userAccuracy = dictAccuracy[user] # How much return the user had overall
                userPredictions = dictPredictions[user] # Number of predictions user made overall

                totalWeight = 0
                if (user in dictUserStockAccuracy):
                    userStockAccuracy = dictUserStockAccuracy[user]
                    userStockPredictions = dictUserStockPredictions[user]
                    totalWeight = (uAccW * userAccuracy) + (uStockAccW * userStockAccuracy) + (uPredW * userPredictions) + (uStockPredW * userStockPredictions)
                else:
                    totalWeight = (uAccW * userAccuracy) + (uPredW * userPredictions)

                if (isBull):
                    total += totalWeight
                else:
                    total -= totalWeight

        if (symbol in symbolsIgnored):
            continue
        result.append([symbol, total])

    result.sort(key = lambda x: x[1], reverse = True)
    res = recommendStocks(result, date, money, numStocks)
    writeSingleList(pathWeighted, result)
    hitPrecent = totalHits * 100.0 / totalUsers

    return (res, round(hitPrecent, 2))
