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

from .helpers import (calcRatio, findWeight, readCachedCloseOpen,
                      readCachedTweets, readPickleObject, recurse,
                      writeCachedCloseOpen, writeCachedTweets,
                      writePickleObject)
from .hyperparameters import constants
from .messageExtract import *
from .stockPriceAPI import getUpdatedCloseOpen, updateAllCloseOpen
from .userAnalysis import setupUserInfos


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


# Build empty feature object
def buildFeatures():
    features = {}
    functions = constants['functions']
    uniques = ['nonUnique', 'unique']
    infos = ['stock', 'user']
    bullBear = ['bull', 'bear']
    featureNames = ['return', 'returnWeights', 'count', 'totalReturnCloseOpen',
                    'totalReturnWeighted', 'returnUnique', 'returnWeightedUnique',
                    'countUnique', 'totalReturnUnique', 'totalReturnUniqueWeighted']
    for fx in functions:
        features[fx] = {}
        for fy in functions:
            features[fx][fy] = {}
            for u in uniques:
                features[fx][fy][u] = {}
                for infoName in infos:
                    features[fx][fy][u][infoName] = {}
                    for f in featureNames:
                        features[fx][fy][u][infoName][f] = {}
                        for b in bullBear:
                            features[fx][fy][u][infoName][f][b] = {}
    return features


# Tell whether the tweet is actually bull or bear based on historical predictions
def bearBull(isBull, returns):
    label = 'bull' if isBull else 'bear'
    if (returns < 0):
        label = 'bull' if (label == 'bear') else 'bear'
    return label


def findFeaturesFromTweet(isBull, userInfo, symbol, f):
    stockInfo = userInfo['perStock'][symbol]
    result = buildFeatures()['1']['1']['unique']
    result['totalLabeledTweet'] = 1
    infos = {'stock': stockInfo, 'user': userInfo}
    for infoName in infos:
        # If more accurate for this label, trust prediction, otherwise do opposite
        # Basically reverse what their prediction was
        info = infos[infoName]
        label = bearBull(isBull, info[f]['returnCloseOpen']['bull' if isBull else 'bear'])
        result[infoName]['return'][label] = info[f]['returnCloseOpen'][label]
        accuracy = info[f]['numCloseOpen'][label] / info[f]['numPredictions'][label]
        result[infoName]['returnWeighted'][label] = accuracy * info[f]['returnCloseOpen'][label]
        result[infoName]['count'][label] += 1

        totalReturn = info[f]['returnCloseOpen']['bull'] + info[f]['returnCloseOpen']['bear']
        labelTotal = bearBull(isBull, totalReturn)
        result[infoName]['totalReturnCloseOpen'][labelTotal] = totalReturn
        accuracy = (info[f]['numCloseOpen']['bull'] + info[f]['numCloseOpen']['bear']) / (info[f]['numPredictions']['bull'] + info[f]['numPredictions']['bear'])
        result[infoName]['totalReturnWeighted'][labelTotal] = accuracy * totalReturn

        labelUnique = bearBull(isBull, info[f]['returnUnique']['bull' if isBull else 'bear'])
        result[infoName]['returnUnique'][labelUnique] = info[f]['returnUnique'][labelUnique]
        accuracy = info[f]['numUnique'][labelUnique] / info[f]['numUniquePredictions'][labelUnique]
        result[infoName]['returnWeightedUnique'][labelUnique] = accuracy * info[f]['returnCloseOpen'][labelUnique]
        result[infoName]['countUnique'][labelUnique] += 1

        totalReturnUnique = info[f]['returnUnique']['bull'] + info[f]['returnUnique']['bear']
        labelTotalUnique = bearBull(isBull, totalReturnUnique)
        result[infoName]['totalReturnUnique'][labelTotalUnique] = totalReturnUnique
        accuracy = (info[f]['numUnique']['bull'] + info[f]['numUnique']['bear']) / (info[f]['numUniquePredictions']['bull'] + info[f]['numUniquePredictions']['bear'])
        result[infoName]['totalReturnUniqueWeighted'][labelTotalUnique] = accuracy * totalReturnUnique
    return result


# Update feature object per stock, per day
def updateSentimentFeatures(features, tweetFeatures, usersTweets, unique, w, f):
    for fs in tweetFeatures:
        for infoName in tweetFeatures[fs]:
            for features in tweetFeatures[fs][infoName]:
                for labels in tweetFeatures[fs][infoName][features]:
                    value = tweetFeatures[fs][infoName][features][labels]
                    features[f][fs][unique][infoName][features][labels] += (w * value)
                bullFeature = features[f][fs][unique][infoName][features]['bull']
                bearFeature = features[f][fs][unique][infoName][features]['bear']
                features[f][fs][unique][infoName][features]['ratio'] = calcRatio(bullFeature, bearFeature)


# Calculate features based on list of tweets
def newCalculateSentiment(tweets, symbol, userAccDict):
    usersTweeted = {'bull': set([]), 'bear': set([])}
    functions = constants['functions']
    features = buildFeatures()

    # Weight all values based on the function and time of posting
    for f in functions:
        for tweet in tweets:
            username = tweet['user']
            isBull = tweet['isBull']
            label = 'bull' if isBull else 'bear'
            w = findWeight(tweet['time'], f)
            if (username not in userAccDict or symbol not in userAccDict[username]['perStock']):
                continue

            tweetFeatures = {}
            for fs in functions:   
                tempResult = findFeaturesFromTweet(isBull, userAccDict[username], symbol, fs)
                tweetFeatures[fs] = tempResult

            updateSentimentFeatures(features, tweetFeatures, usersTweeted, 'nonUnique', w, f)
            if (username not in usersTweeted[label]):
                usersTweeted[label].add(username)
                updateSentimentFeatures(features, tweetFeatures, usersTweeted, 'unqiue', w, f)

    return features


def calculateSentiment(tweets, symbol, userAccDict):
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
    else:
        updateAllCloseOpen(stocks, dates)

    result = {}
    for symbol in stocks:
        if (symbol not in result):
            result[symbol] = {}

        cachedCloseOpen = readCachedCloseOpen(symbol)
        for date in dates:
            if (date not in result[symbol]):
                # Check if the date exists in the cached closeOpens
                if (date in cachedCloseOpen):
                    result[symbol][date] = cachedCloseOpen[date]
                    continue

                res = getUpdatedCloseOpen(symbol, date)
                if (res is None):
                    print(date, symbol)
                    continue

                writeCachedCloseOpen(symbol, date, res)
                result[symbol][date] = res

    writePickleObject(path, result)
    return result


# Stock Infos from saved file
def setupStockInfos(stocks, updateObject=False):
    print("Setup Stock Info")
    path = 'pickledObjects/stockInfos.pkl'
    result = readPickleObject(path)
    if (updateObject is False):
        return result

    basicStockInfo = constants['stocktweets_client'].get_database('stocks_data_db').training_stock_info_1216
    result = {}
    for symbol in stocks:
        symbolInfo = basicStockInfo.find_one({'_id': symbol})
        result[symbol] = symbolInfo
    writePickleObject(path, result)
    return result


# Find all tweets on this given day from database
def findTweets(date, symbol):
    tweetsDB = constants['stocktweets_client'].get_database('tweets_db')
    db = constants['db_client'].get_database('stocks_data_db').updated_close_open
    dayIncrement = datetime.timedelta(days=1)
    dateEnd = datetime.datetime(date.year, date.month, date.day, 16)
    dateStart = dateEnd - dayIncrement

    # find dateStart starting at dateEnd
    testDay = db.find_one({'_id': 'AAPL ' + dateStart.strftime("%Y-%m-%d")})
    count = 0
    while (testDay is None and count != 10):
        dateStart -= dayIncrement
        testDay = db.find_one({'_id': 'AAPL ' + dateStart.strftime("%Y-%m-%d")})
        count += 1

    query = {"$and": [{'symbol': symbol},
                      {"$or": [
                            {'isBull': True},
                            {'isBull': False}
                      ]},
                      {'time': {'$gte': dateStart,
                                '$lt': dateEnd}}]}
    tweets = list(tweetsDB.tweets.find(query))
    return tweets


# Find all tweets for each date
# Tweets for any given day is from the previous trading day to current day at 4:00 PM
def findAllTweets(stocks, dates, updateObject=False, dayPrediction=False):
    print("Setup Tweets")
    path = 'pickledObjects/allTweets.pkl'
    result = readPickleObject(path)
    if (updateObject is False and dayPrediction is False):
        return result

    if (dayPrediction):
        result = {}

    for symbol in stocks:
        print(symbol)
        if (symbol not in result):
            result[symbol] = {}

        cachedTweets = readCachedTweets(symbol)
        for date in dates:
            if (date not in result[symbol]):
                # Check if the date exists in the cached tweets
                if (date in cachedTweets):
                    result[symbol][date] = cachedTweets[date]
                    continue
                result[symbol][date] = []
                # Find all tweets from previous trading day to 4:00 PM this day
                tweets = findTweets(date, symbol)
                for tweet in tweets:
                    result[symbol][date].append(tweet)

                if (dayPrediction is False):
                    writeCachedTweets(symbol, tweets)
            print(date, len(result[symbol][date]))

    if (updateObject and dayPrediction is False):
        writePickleObject(path, result)
    return result


def simpleWeightPrediction(date, features, closeOpenInfo, paramWeightings):
    summedDict = {}
    for param in paramWeightings:
        paramWeight = paramWeightings[param]
        if (param == 'numStocks'):
            continue

        for stock in features:
            resultsForDay = features[stock][date][param]
            if (stock not in summedDict):
                summedDict[stock] = 0
            summedDict[stock] += (resultsForDay * paramWeight)

    resPerParam = list(summedDict.items())
    resPerParam.sort(key=lambda x: abs(x[1]), reverse=True)
    resPerParam = resPerParam[:paramWeightings['numStocks']]
    sumDiffs = reduce(lambda a, b: a + b,
                      list(map(lambda x: abs(x[1]), resPerParam)))

    returnToday = 0
    for stockObj in resPerParam:
        stock = stockObj[0]
        stdDev = stockObj[1]
        try:
            closeOpen = closeOpenInfo[stock][date][2]
            returnToday += ((stdDev / sumDiffs) * closeOpen)
        except Exception:
            continue

    try:
        mappedResult = list(map(lambda x: [x[0], 
                            round(x[1] / sumDiffs * 100, 2),
                            closeOpenInfo[x[0]][date][2]],
                            resPerParam))
    except Exception:
        mappedResult = list(map(lambda x: [x[0],
                            round(x[1] / sumDiffs * 100, 2)],
                            resPerParam))
    return (returnToday, mappedResult)


# Basic prediction algo
def basicPrediction(dates, stocks, updateObject=False, dayPrediction=False):
    userInfo = setupUserInfos(stocks)
    stockInfo = setupStockInfos(stocks, True)
    closeOpenInfo = setupCloseOpen(dates, stocks, updateObject)
    allTweets = findAllTweets(stocks, dates, updateObject, dayPrediction)
    features = generateFeatures(dates, stocks, allTweets,
                                stockInfo, userInfo,
                                True, dayPrediction=True)
    symbolReturns = {}
    symbolCounts = {}
    combinedResult = 0
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
                            'numStocks': 6}
        returns, listReturns = simpleWeightPrediction(date, features,
                                                      closeOpenInfo,
                                                      paramWeightings)
        print(date, round(returns, 3), listReturns)
        for s in listReturns:
            if (len(s) == 2):
                continue
            symbol = s[0]
            val = 0
            if ((s[1] < 0 and s[2] < 0) or (s[1] > 0 and s[2] > 0)):
                val = abs(s[2])
            else:
                val = -abs(s[2])
            if (symbol not in symbolReturns):
                symbolReturns[symbol] = 0
                symbolCounts[symbol] = {}
                symbolCounts[symbol]['y'] = 0
                symbolCounts[symbol]['x'] = 0

            symbolReturns[symbol] += val
            symbolCounts[symbol]['y'] += 1
            if (val > 0):
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


# Generate features for each stock on each day based on tweets for that given day
def generateFeatures(dates, stocks, allTweets, stockInfo,
                     userInfo, updateObject=False, dayPrediction=False):
    print("Generating Features")
    path = 'pickledObjects/features.pkl'
    if (updateObject is False and dayPrediction is False):
        features = readPickleObject(path)
        return features

    features = {}
    for symbol in stocks:
        print(symbol)
        features[symbol] = {}
        for date in dates:
            if (date not in allTweets[symbol]):
                continue
            features[symbol][date] = {}
            tweets = allTweets[symbol][date]
            print(len(tweets))
            sentiment = calculateSentiment(tweets, symbol, userInfo)
            for param in sentiment:
                paramVal = sentiment[param]
                paramMean = stockInfo[symbol][param]['mean']
                paramStd = stockInfo[symbol][param]['stdev']
                if (stockInfo[symbol][param]['stdev'] == 0.0):
                    features[symbol][date][param] = 0
                    print(param)
                    continue

                stdDev = round((paramVal - paramMean) / paramStd, 2)
                features[symbol][date][param] = stdDev

    if (updateObject):
        writePickleObject(path, features)
    return features


# Updates stock mean and standard deviation
def updateBasicStockInfo(dates, stocks, allTweets):
    basicStockInfo = constants['stocktweets_client'].get_database('stocks_data_db').training_stock_info_1216

    for symbol in stocks:
        accuracy = constants['db_user_client'].get_database('user_data_db').user_accuracy
        allUsersAccs = accuracy.find({'perStock.' + symbol: {'$exists': True}})
        userAccDict = {}
        print(symbol, allUsersAccs.count())
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
            sentiment = calculateSentiment(tweets, symbol, userAccDict)
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
