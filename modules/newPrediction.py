import datetime
import statistics
import math
import pickle
import os
import csv
import copy
import json
import time
import matplotlib. pyplot as plt
from scipy.optimize import minimize
from functools import reduce
from .hyperparameters import constants
from .userAnalysis import (getStatsPerUser, initializeResult, updateUserFeatures)
from .stockAnalysis import (findDateString, getTopStocksforWeek, findPageStock, parseStockData,
                            updateLastMessageTime, updateLastParsedTime, getTopStocksCached)
from .stockPriceAPI import (findCloseOpenCached, isTradingDay)
from .helpers import (calcRatio, findWeight, readPickleObject, findAllDays, insertResults,
                    readCachedTweets, writeCachedTweets, writePickleObject,
                    findTradingDays, findAverageTime, convertToEST)


def parseStock(symbol, date, hours):
    date_string = date.strftime("%Y-%m-%d")
    db = constants['stocktweets_client'].get_database('stocks_data_db')
    (soup, errorMsg, timeElapsed) = findPageStock(symbol, hours)

    if (soup == ''):
        stockError = {'date': date_string, 'symbol': symbol,
                        'error': errorMsg, 'timeElapsed': timeElapsed}
        db.stock_tweets_errors.insert_one(stockError)
        return

    try:
        result = parseStockData(symbol, soup)
    except Exception as e:
        stockError = {'date': date_string, 'symbol': symbol,
                        'error': str(e), 'timeElapsed': -1}
        db.stock_tweets_errors.insert_one(stockError)
        print(e)
        return

    if (len(result) == 0):
        stockError = {'date': date_string, 'symbol': symbol,
                        'error': 'Result length is 0??', 'timeElapsed': -1}
        db.stock_tweets_errors.insert_one(stockError)
        print(stockError)
        return

    results = updateLastMessageTime(db, symbol, result)

    # No new messages
    if (len(results) != 0):
        insertResults(results)

    updateLastParsedTime(db, symbol)



def dailyPrediction(date):
    num_top_stocks = 15
    stocks = getTopStocksforWeek(date, num_top_stocks)
    last_parsed = constants['stocktweets_client'].get_database('stocks_data_db').last_parsed
    curr_time = convertToEST(datetime.datetime.now())
    for symbol in stocks:
        cursor = last_parsed.find_one({'_id': symbol})
        last_time = cursor['time']
        hours_back = (curr_time - last_time).total_seconds() / 3600.0
        print(symbol, hours_back)
        if (hours_back > 0.5):
            parseStock(symbol, curr_time, hours_back)
    writeTweets(date, date, num_top_stocks, overwrite=True)
    all_features = findFeatures(date, date, num_top_stocks, 'newPickled/daily.pkl', True)
    weightings = {
        'bull': 3,
        'bear': 1
    }
    prediction(date, date, all_features, num_top_stocks, weightings, True)



def optimizeFN(params):
    weightings = {
        'bull_w': params[0],
        'bear_w': params[1],
        'bull_w_return_w1': params[2],
        'bear_w_return_w1': params[3],
        # 'count_ratio_w': params[4],
        # 'return_ratio_w': params[5],
    }
    start_date = datetime.datetime(2019, 6, 2, 15, 30)
    end_date = datetime.datetime(2020, 7, 1, 9, 30)
    path = 'newPickled/stock_features.pkl'
    num_top_stocks = 25
    all_features = findFeatures(start_date, end_date, num_top_stocks, path, False)
    result = prediction(start_date, end_date, all_features, num_top_stocks, weightings, False)
    param_res = list(map(lambda x: round(x, 2), params))
    print(param_res, result)
    return -result


# result['total'] = result['bull'] - result['bear']
# result['total_w'] = result['bull_w'] - result['bear_w']
# result['return'] = result['bull_return'] - result['bear_return']
# result['return_w'] = result['bull_w_return'] - result['bear_w_return']
# result['return_log'] = result['bull_return_log'] - result['bear_return_log']
# result['return_log_w'] = result['bull_w_return_log'] - result['bear_w_return_log']
# result['return_s'] = result['bull_return_s'] - result['bear_return_s']
# result['return_s_w'] = result['bull_w_return_s'] - result['bear_w_return_s']
# result['return_log_s'] = result['bull_return_log_s'] - result['bear_return_log_s']
# result['return_log_s_w'] = result['bull_w_return_log_s'] - result['bear_w_return_log_s']
# result['return_w1'] = result['bull_w_return_w1'] - result['bear_w_return_w1']
# result['return_w1_s'] = result['bull_w_return_w1_s'] - result['bear_w_return_w1_s']

# result['count_ratio'] = calcRatio(result['bull'], result['bear'])
# result['count_ratio_w'] = calcRatio(result['bull_w'], result['bear_w'])
# result['return_ratio'] = calcRatio(result['bull_return'], result['bear_return'])
# result['return_ratio_w'] = calcRatio(result['bull_w_return'], result['bear_w_return'])
# result['return_log_ratio'] = calcRatio(result['bull_return_log'], result['bear_return_log'])
# result['return_log_ratio_w'] = calcRatio(result['bull_w_return_log'], result['bear_w_return_log'])
# result['return_s_ratio'] = calcRatio(result['bull_return_s'], result['bear_return_s'])
# result['return_s_ratio_w'] = calcRatio(result['bull_w_return_s'], result['bear_w_return_s'])
# result['return_log_s_ratio'] = calcRatio(result['bull_return_log_s'], result['bear_return_log_s'])
# result['return_log_s_ratio_w'] = calcRatio(result['bull_w_return_log_s'], result['bear_w_return_log_s'])
# result['return_w1_ratio'] = calcRatio(result['bull_w_return_w1'], result['bear_w_return_w1'])
# result['return_w1_s_ratio'] = calcRatio(result['bull_w_return_w1_s'], result['bear_w_return_w1_s'])



# bad
# return_ratio_w
# return_log_s_ratio_w
# return_ratio
# count_ratio
# return_w1_s_ratio


# count_ratio_w
# return_s_ratio_w
# total_w
# return_log_s_w
# return_log_ratio_w



def optimizeParams():
    params = {
        # 'total_w': [8, (0, 30)],
        # 'return_log_s_w': [2, (0, 30)],
        # 'return_s_w': [2, (0, 30)],
        'bull_w': [3, (0, 5)],
        'bear_w': [0.8, (0, 5)],
        'bull_w_return_w1': [1.2, (0, 3)],
        'bear_w_return_w1': [0.5, (0, 3)],
        # 'count_ratio_w': [0.5, (0, 30)],
        # 'return_ratio_w': [0.5, (0, 30)],
        # 'bear_w_return': [0., (0, 30)],
        # 'bear_w_return_log_s': [0, (0, 30)],
        # 'bear_w_return': [1.09, (0, 30)],
        # 'bull_w_return': [2.74, (0, 30)],
        # 'return_w1_ratio': [1.9, (0, 30)],
        # 'bear_return_s': [2.8, (0, 30)],
        # 'bear': [7.7, (0, 30)],
        # 'bear_return': [4.1, (0, 30)],
        # 'count_ratio': [1, (0, 30)],
    }

    initial_values = list(map(lambda key: params[key][0], list(params.keys())))
    bounds = list(map(lambda key: params[key][1], list(params.keys())))
    result = minimize(optimizeFN, initial_values, method='SLSQP', options={'maxiter': 100, 'eps': 0.2}, 
                    bounds=(bounds[0],bounds[1],bounds[2],bounds[3]))
    print(result)


# Find all usernames from folder
def findUserList():
    users = []
    arr = os.listdir('user_tweets/')
    for u in arr:
        username = u[:-4]
        users.append(username)
    users.sort()
    return users


# Find all usernames from folder
def findValidUsers():
    users = []
    arr = os.listdir('user_pickle_files_new/')
    for u in arr:
        username = u[:-4]
        users.append(username)
    users.sort()
    return users


def cutoffUser(user_info):
    num_tweets = findFeature(user_info, '', 'num_predictions', None)
    num_tweets_unique = findFeature(user_info, '', 'unique_num_predictions', None)

    # Filter by number of tweets
    if (num_tweets <= 50 or num_tweets_unique <= 10):
        return False

    bull_res_n = user_info['unique_correct_predictions']['bull']
    bear_res_n = user_info['unique_correct_predictions']['bear']
    bull_res_d = user_info['unique_num_predictions']['bull']
    bear_res_d = user_info['unique_num_predictions']['bear']
    # If never tweeted about this stock
    if (bull_res_d == 0 and bear_res_d == 0):
        return False

    if (bull_res_d == 0):
        bull_res_d = 1
    
    if (bear_res_d == 0):
        bear_res_d = 1

    accuracy_unique_bull = bull_res_n / bull_res_d
    accuracy_unique_bear = bear_res_n / bear_res_d
    bull_return = user_info['unique_return']['bull']
    bear_return = user_info['unique_return']['bear']
    return_unique = max(bull_return, bear_return)
    accuracy_unique = max(accuracy_unique_bull, accuracy_unique_bear)
    # Filter by accuracy
    if (accuracy_unique < 0.35):
        return False

    # Filter by return
    if (return_unique < 1):
        return False

    return True


# Generate features from users historical tweets
# Return stock specific user features and general user features
def pregenerateUserFeatures(username):
    day_increment = datetime.timedelta(days=1)
    cached_tweets = cachedUserTweets(username) # Tweets from user
    if (cached_tweets == None):
        return {'general': {}}

    dates = set([])
    # Extract the unique dates that the user tweeted
    for tweet in cached_tweets:
        time = tweet['time']

        # Find the trading day the tweet corresponds to
        if (time.hour >= 16):
            time += day_increment
        while (isTradingDay(time) == False):
            time += day_increment

        time = datetime.datetime(time.year, time.month, time.day, 16)
        if (time not in dates):
            dates.add(time)

    # Go from past to present
    dates = sorted(list(dates))
    result_general = {}
    result_perstock = {}
    buildup_result = {} # cached result that is being built up
    prev_day = {}
    for date in dates:
        day_res = calculateUserFeatures(username, date, buildup_result, cached_tweets)
        if (cutoffUser(day_res) == False):
            continue

        copied_res = copy.deepcopy(day_res)
        del copied_res['_id']
        del copied_res['last_updated']
        if (prev_day == copied_res):
            continue
        prev_day = copied_res

        # Store as user features at next trading day
        date += day_increment
        while (isTradingDay(date) == False):
            date += day_increment
        date_string = '%d-%02d-%02d' % (date.year, date.month, date.day)
        per_stock = copied_res['perStock']
        for symbol in per_stock:
            if (symbol not in result_perstock):
                result_perstock[symbol] = {}
                result_perstock[symbol][date_string] = per_stock[symbol]
                continue

            prev_dates = sorted(result_perstock[symbol].keys(), reverse=True)
            last_date = prev_dates[0]
            if (result_perstock[symbol][last_date] != per_stock[symbol]):
                result_perstock[symbol][date_string] = per_stock[symbol]

        del copied_res['perStock']
        result_general[date_string] = copied_res

    return {'general': result_general, 'per_stock': result_perstock}


def insertUser():
    valid_users = findValidUsers()
    # user_info_collection = constants['local_client']['user_info_db']['user_info']
    user_info_collection = constants['stocktweets_client'].get_database('user_info_db').user_info

    i = 0
    for username in valid_users:
        i += 1
        path = 'user_pickle_files/' + username + '.pkl'
        user_feature = readPickleObject(path)
        user_feature['_id'] = username
        user_info_collection.insert_one(user_feature)
        if (i % 1000 == 0):
            print(i)


# Pregenerate all user features based off tweets
# Extract GENEARL and STOCK specific user return, accuracy, tweet count, etc.
def pregenerateAllUserFeatures():
    users = findUserList() # Based off of users in the user_tweets/ folder
    result = {}
    not_found = 0
    for i in range(len(users)):
        if (i % 1000 == 0): # Log progress
            print(not_found)
            print(i)

        username = users[i]
        pregenerated = pregenerateUserFeatures(username) # Find user features

        # If no dates/features were found or doesn't meet minimum user requirements
        if (len(pregenerated['general']) == 0):
            not_found += 1
            continue

        # Remove unnecessary data from users before a given date
        prev_dates = sorted(list(pregenerated['general'].keys()))
        last_date_feature = None
        last_date = prev_dates[0]
        for date in prev_dates:
            if (date < '2019-06-01'): # Temp cutoff for dates not to keep
                last_date_feature = pregenerated['general'][date]
                last_date = date
                del pregenerated['general'][date]

        # If all dates deleted, use the latest date/feature
        if (len(pregenerated['general']) == 0):
            pregenerated['last_tweet_date'] = datetime.datetime.strptime(last_date, '%Y-%m-%d')
            pregenerated['general_dates'] = [last_date]
            pregenerated['general'][last_date] = last_date_feature
            result[username] = pregenerated
            continue

        # Sorted from most recent to most historical
        all_general_dates = sorted(list(pregenerated['general'].keys()), reverse=True)
        last_date = all_general_dates[-1] # Date of last tweet
        pregenerated['last_tweet_date'] = datetime.datetime.strptime(last_date, '%Y-%m-%d')
        pregenerated['general_dates'] = all_general_dates
        result[username] = pregenerated

    path = 'newPickled/user_features_1.pickle'
    writePickleObject(path, result)



# Find average stock count over d trading days back
def findStockCounts(all_features, days_back):
    stock_counts = {}
    all_dates = sorted(list(all_features.keys()))
    for i in range(len(all_dates)):
        date_string = all_dates[i]
        stock_counts[date_string] = {}
        for s in all_features[date_string]:
            total_count = 0
            index = i
            total_bull = 0
            total_bear = 0
            # Add all stock counts d trading days before the current day and find average count
            while (index >= 0 and total_count < days_back):
                new_date_string = all_dates[index]
                if (s in all_features[new_date_string]):
                    total_bull += all_features[new_date_string][s]['bull_count']
                    total_bear += all_features[new_date_string][s]['bear_count']
                    total_count += 1
                index -= 1
            stock_counts[date_string][s] = {
                'bull_count': total_bull / total_count,
                'bear_count': total_bear / total_count
            }
    return stock_counts


# Standardize all features by average stock count for bull/bear
def editFeatures(start_date, end_date, all_features, weights):
    # Find counts of bear/bull per stock averaged over last n number of trading days
    stock_counts = findStockCounts(all_features, 10)

    data = []
    data1 = []
    for d in all_features:
        for s in all_features[d]:
            # standardize all features before using
            result = all_features[d][s]
            for f in all_features[d][s]:
                if (stock_counts[d][s]['bear_count'] == 0 or stock_counts[d][s]['bull_count'] == 0):
                    continue
                if ('bull' in f):
                    result[f] /= ((all_features[d][s]['bull_count'] + stock_counts[d][s]['bull_count']) / 2)
                else:
                    result[f] /= ((all_features[d][s]['bear_count'] + stock_counts[d][s]['bear_count']) / 2)

            if (s == 'SPY'):
                data.append((3 * result['bull']) - result['bear'])
                data1.append(d)
            result['total'] = result['bull'] - result['bear']
            result['total_w'] = result['bull_w'] - result['bear_w']
            result['return'] = result['bull_return'] - result['bear_return']
            result['return_w'] = result['bull_w_return'] - result['bear_w_return']
            result['return_log'] = result['bull_return_log'] - result['bear_return_log']
            result['return_log_w'] = result['bull_w_return_log'] - result['bear_w_return_log']
            result['return_s'] = result['bull_return_s'] - result['bear_return_s']
            result['return_s_w'] = result['bull_w_return_s'] - result['bear_w_return_s']
            result['return_log_s'] = result['bull_return_log_s'] - result['bear_return_log_s']
            result['return_log_s_w'] = result['bull_w_return_log_s'] - result['bear_w_return_log_s']
            result['return_w1'] = result['bull_w_return_w1'] - result['bear_w_return_w1']
            result['return_w1_s'] = result['bull_w_return_w1_s'] - result['bear_w_return_w1_s']

            result['count_ratio'] = calcRatio(result['bull'], result['bear'])
            result['count_ratio_w'] = calcRatio(result['bull_w'], result['bear_w'])
            result['return_ratio'] = calcRatio(result['bull_return'], result['bear_return'])
            result['return_ratio_w'] = calcRatio(result['bull_w_return'], result['bear_w_return'])
            result['return_log_ratio'] = calcRatio(result['bull_return_log'], result['bear_return_log'])
            result['return_log_ratio_w'] = calcRatio(result['bull_w_return_log'], result['bear_w_return_log'])
            result['return_s_ratio'] = calcRatio(result['bull_return_s'], result['bear_return_s'])
            result['return_s_ratio_w'] = calcRatio(result['bull_w_return_s'], result['bear_w_return_s'])
            result['return_log_s_ratio'] = calcRatio(result['bull_return_log_s'], result['bear_return_log_s'])
            result['return_log_s_ratio_w'] = calcRatio(result['bull_w_return_log_s'], result['bear_w_return_log_s'])
            result['return_w1_ratio'] = calcRatio(result['bull_w_return_w1'], result['bear_w_return_w1'])
            result['return_w1_s_ratio'] = calcRatio(result['bull_w_return_w1_s'], result['bear_w_return_w1_s'])

            # Make all bear features negative
            for f in all_features[d][s]:
                if ('bear' in f):
                    all_features[d][s][f] = -all_features[d][s][f]


    # fig, axs = plt.subplots(2)
    # print(data1[230:])
    # print(data[230:])
    # plt.plot(data[230:])
    # plt.show()
    # print(data1)
    # axs[0].hist(data, density=False, bins=150)
    # axs[1].hist(data1, density=False, bins=150)
    # plt.show()
    return all_features


def calculateReturn(date, daily_features, choose_top_n, accuracies):
    # cached closeopen prices
    cached_prices = constants['cached_prices']

    stock_weightings = list(daily_features.items())
    stock_weightings.sort(key=lambda x: abs(x[1]), reverse=True)
    stock_weightings = stock_weightings[:choose_top_n]
    sum_weights = reduce(lambda a, b: a + b, list(map(lambda x: abs(x[1]), stock_weightings)))

    return_today = 0
    selected_stocks = []
    for stock_obj in stock_weightings:
        symbol = stock_obj[0]
        weighting = stock_obj[1]
        close_open = findCloseOpenCached(symbol, date, cached_prices)
        # Make sure close opens are always updated
        if (close_open == None):
            selected_stocks.append([symbol, round(weighting / sum_weights * 100, 2)])
            continue
        
        percent_change = close_open[2]
        percent_weight = (weighting / sum_weights)
        return_today += (percent_weight * percent_change)

        selected_stocks.append([symbol, round(weighting / sum_weights * 100, 2), round(percent_change, 2)])

        if (symbol not in accuracies):
            accuracies[symbol] = {}
            accuracies[symbol]['correct'] = 0
            accuracies[symbol]['total'] = 0
        
        if ((close_open[2] < 0 and stock_obj[1] < 0) or (stock_obj[1] > 0 and close_open[2] > 0)):
            accuracies[symbol]['correct'] += 1
        accuracies[symbol]['total'] += 1

    return (return_today, selected_stocks)



# Make prediction by chooosing top n stocks to buy per day
# Features are generated before hand per stock per day
def prediction(start_date, end_date, all_features, num_top_stocks, weightings, print_info):

    # Standardize all features by their historical counts
    all_features = editFeatures(start_date, end_date, all_features, weightings)

    # trading days 
    dates = findTradingDays(start_date, end_date)
    accuracies = {}
    total_return = 0
    strong_return = 0
    strong_correct = 0
    strong_total = 0
    negative_correct = 0
    negative_total = 0
    negative_return = 0
    positive_days = 0
    cash = 1000

    # Find top n stock features for each day 
    for date in dates:
        daily_features = {}
        date_string = date.strftime("%Y-%m-%d")

        # Find features for each stock
        for symbol in all_features[date_string]:
            stock_features = all_features[date_string][symbol]

            # Weight each feature based on weight param
            result_weight = 0
            total_weight = 0
            for w in weightings:
                if (w == 'day_weight' or w == 'stock_weight'):
                    continue
                result_weight += (weightings[w] * stock_features[w])
                total_weight += weightings[w]
            daily_features[symbol] = result_weight / total_weight

        # Find percent of each stock to buy (pick top x)
        choose_top_n = 3
        (return_today, selected_stocks) = calculateReturn(date, daily_features, choose_top_n, accuracies)
        total_return += return_today
        cash *= (1 + (return_today / 100))
        
        if (return_today > 0):
            positive_days += 1

        # Print stocks that are picked
        if (print_info):
            if (return_today == 0):
                print(date, selected_stocks)
                continue
            print(date_string, cash, return_today, selected_stocks)
            for s in selected_stocks:
                if (s[1] < 0):
                    if (s[2] < 0):
                        negative_correct += 1
                        negative_return += abs(s[2])
                    negative_total += 1
            # if (abs(selected_stocks[0][1]) > 80):
            #     print(selected_stocks)
            #     val = -1 if selected_stocks[0][1] < 0 else 1
            #     ret = val * selected_stocks[0][2]
            #     if (ret >= 0):
            #         strong_correct += 1
            #     strong_total += 1
            #     strong_return += ret

    total_correct = 0
    total_total = 0
    for s in accuracies:
        total_correct += accuracies[s]['correct']
        total_total += accuracies[s]['total']
        if (print_info):
            print(s, accuracies[s]['correct'], accuracies[s]['total'])

    if (print_info):
        if (total_total > 0):
            print(strong_correct, strong_total, strong_return, ' ', negative_correct, negative_total, negative_return)
            print(total_correct/total_total, total_return, cash, positive_days / len(dates))
            print(total_correct/total_total)
    return total_return
    return total_correct/total_total



# Find features of tweets per day of each stock
# INVARIANT: user feature are built up as time increases (TIME MUST ALWAYS INCREASE)
# ^^ Done to reduce calls to close open / unecessary calculations
def findFeatures(start_date, end_date, num_top_stocks, path, update=False):
    if (update == False):
        return readPickleObject(path)

    dates = findTradingDays(start_date, end_date)
    all_stock_tweets = {} # store tweets locally for each stock
    all_user_features = readPickleObject('newPickled/user_features_1.pickle')
    cached_stockcounts = readPickleObject('newPickled/stock_counts_14.pkl')
    result = {}

    for date in dates:
        date_str = date.strftime("%Y-%m-%d")
        result[date_str] = {}
        found = 0
        stocks = getTopStocksCached(date, num_top_stocks, cached_stockcounts) # top stocks for the week
        # stocks = ['B', 'SPY', 'PTN', 'TSLA', 'AMD', 'MU', 'VBIV', 'NIO', 'FB', 'SLS', 'OSTK', 'ROKU', 'WKHS', 'DPW', 'AMZN', 'SHOP', 'AAPL', 'WORK', 'JNUG', 'FCEL', 'BA', 'CEI', 'TRNX', 'DIS', 'AMRN', 'CHK', 'ACB', 'TBLT', 'NFLX', 'UGAZ', 'BABA', 'SNAP', 'TVIX', 'SQ', 'NVDA', 'GE', 'BIOC', 'XSPA', 'SRNE', 'MSFT']
        for symbol in stocks:
            tweets_per_stock = {}
            if (symbol not in all_stock_tweets):
                stock_path = 'stock_files/' + symbol + '.pkl'
                tweets_per_stock = readPickleObject(stock_path)
                all_stock_tweets[symbol] = tweets_per_stock
            else:
                tweets_per_stock = all_stock_tweets[symbol]
            tweets = findTweets(date, tweets_per_stock, symbol) # Find tweets used for predicting for this date

            # ignore all stock with less than 200 tweets
            if (len(tweets) < 50):
                continue
            found += 1
            print(symbol, len(tweets))
            features = stockFeatures(tweets, symbol, all_user_features) # calc features based on tweets/day
            result[date_str][symbol] = features
        print(date_str, found)

    writePickleObject(path, result)
    return result


# Find top stocks given the date (updated per week)
# Use those stocks to find features based on tweets from those day
# date_str_1 = datetime.datetime(2020, 6, 24, 9, 30).strftime("%Y-%m-%d")
# date_str_2 = datetime.datetime(2020, 6, 25, 9, 30).strftime("%Y-%m-%d")
# del all_features[date_str_1]
# del all_features[date_str_2]

def modifyTweets():
    stocks = []
    stocks = os.listdir('stock_files/')
    for symbol_path in stocks:
        print(symbol_path)
        if (symbol_path[-3:] != 'pkl'):
            continue
        path = 'stock_files/' + symbol_path
        tweets_per_stock = readPickleObject(path)
        for date in tweets_per_stock:
            tweets = tweets_per_stock[date]
            new_tweets = list(map(lambda t: {'user': t['user'], 'time': t['time'], 'w': findWeight(t['time'], 'log(x)'), 'isBull': t['isBull']}, tweets))
            new_tweets.sort(key=lambda tweet: tweet['time'], reverse=True)
            tweets_per_stock[date] = new_tweets
        writePickleObject(path, tweets_per_stock)


# Find all tweets on this given day from database
def findTweets(date, tweets_per_stock, symbol):
    # Find start end and end dates for the given date
    day_increment = datetime.timedelta(days=1)
    date_end = datetime.datetime(date.year, date.month, date.day, 16)
    date_start = date_end - day_increment
    dates = [date_end, date_start]
    while (isTradingDay(date_start) == False):
        date_start -= day_increment
        dates.append(date_start)

    tweets = []
    for date in dates:
        date_string = date.strftime("%Y-%m-%d")
        # Why would this happen ??
        if (date_string not in tweets_per_stock):
            print(date_string, symbol, "fetching tweets")
            path = 'stock_files/' + symbol + '.pkl'
            tweets_per_stock = readPickleObject(path)

            # Find all tweets for the given day
            date_start = datetime.datetime(date.year, date.month, date.day, 0, 0)
            date_end = datetime.datetime(date.year, date.month, date.day) + day_increment
            fetched_tweets = fetchTweets(date_start, date_end, symbol)
            tweets_per_stock[date_string] = fetched_tweets
            tweets.extend(fetched_tweets)

            # Write to the stock pickled object
            writePickleObject(path, tweets_per_stock)
            continue
        found_tweets = tweets_per_stock[date_string]
        tweets.extend(found_tweets)

    start_index = len(tweets) - 1
    end_index = 0
    found_start = False
    found_end = False
    for i in range(len(tweets)):
        tweet_time = tweets[i]['time']
        if (found_end == False and tweet_time <= date_end):
            end_index = i
            found_end = True

        if (found_start == False and tweet_time <= date_start):
            start_index = i
            found_start = True

    return tweets[end_index:start_index]


# Averages and std for features per stock
def findAverageStd(start_date, end_date, all_features):
    # Setup result to have list of features per stock
    # Loop through each date and find feature per stock
    per_stock_features = {}
    for date_str in all_features:
        for symbol in all_features[date_str]:
            if (symbol not in per_stock_features):
                per_stock_features[symbol] = {}
                for f in all_features[date_str][symbol]:
                    per_stock_features[symbol][f] = []
            for f in all_features[date_str][symbol]:
                stock_feature = all_features[date_str][symbol][f]
                per_stock_features[symbol][f].append(stock_feature)

    # Find avg/std for all stocks
    result = {}
    for symbol in per_stock_features:
        features = per_stock_features[symbol]
        result[symbol] = {}
        for f in features:
            # Edge case 1
            if (len(features[f]) == 1):
                res = {
                    'std': 1,
                    'avg': statistics.mean(features[f])
                }
                result[symbol][f] = res
                continue
            # Edge case 2
            if (statistics.mean(features[f]) == 0):
                res = {
                    'std': 1,
                    'avg': 0
                }
                result[symbol][f] = res
                continue
            res = {
                'std': statistics.stdev(features[f]),
                'avg': statistics.mean(features[f])
            }
            result[symbol][f] = res

    return result


# Save user tweets locally (only save symbol, time, isBull)
def saveUserTweets():
    print("Saving all user tweets")
    analyzedUsers = constants['db_user_client'].get_database('user_data_db').users
    time = datetime.datetime(2020, 6, 1)
    query = {"$and": [{'error': ''}, 
                      {'last_updated': {'$exists': True}},
                      {'last_updated': {'$gte': time}}]}
    cursor = analyzedUsers.find(query)
    users = list(map(lambda document: document['_id'], cursor))
    print(len(users))
    count = 0

    for username in users:
        count += 1
        if (count % 1000 == 0): # log progress
            print(count)
        path = 'user_tweets/' + username + '.csv'
        if (os.path.exists(path)):
            continue

        tweets_collection = constants['stocktweets_client'].get_database('tweets_db').tweets
        query = {'$and': [{'user': username}, { "$or": [{'isBull': True}, {'isBull': False}] }]}
        tweets = list(tweets_collection.find(query).sort('time', -1))
        tweets = list(map(lambda t: [t['time'], t['symbol'], t['isBull']], tweets))
        if (len(tweets) < 20):
            continue

        with open(path, "a") as user_file:
            csvWriter = csv.writer(user_file, delimiter=',')
            csvWriter.writerows(tweets)


def editCachedTweets(username):
    path = 'user_tweets/' + username + '.csv'
    if (os.path.exists(path) == False):
        return None

    with open(path) as csv_file:
        csv_reader = csv.reader(csv_file, delimiter=',')
        result = []
        for row in csv_reader:
            if (len(row) == 0):
                continue
            date_string = row[0][:19]
            (year, month, day) = (int(date_string[:4]), int(date_string[5:7]), int(date_string[8:10]))
            (hour, minute, second) = (int(date_string[11:13]), int(date_string[14:16]), int(date_string[17:19]))
            date_parsed = datetime.datetime(year, month, day, hour, minute, second)
            is_bull = True if (row[2] == 'True') else False
            tweet = {'time': date_parsed, 
                    'isBull': is_bull,
                    'symbol': row[1]}
            result.append(tweet)
    
        tweets = list(map(lambda t: [t['time'], t['symbol'], t['isBull']], result))
        with open(path, "w") as user_file:
            csvWriter = csv.writer(user_file, delimiter=',')
            csvWriter.writerows(tweets)


# Fetch user tweets from local disk
def cachedUserTweets(username):
    path = 'user_tweets/' + username + '.csv'
    if (os.path.exists(path) == False):
        return None

    with open(path) as csv_file:
        csv_reader = csv.reader(csv_file, delimiter=',')
        result = []
        for row in csv_reader:
            date_string = row[0][:19]
            (year, month, day) = (int(date_string[:4]), int(date_string[5:7]), int(date_string[8:10]))
            (hour, minute, second) = (int(date_string[11:13]), int(date_string[14:16]), int(date_string[17:19]))
            date_parsed = datetime.datetime(year, month, day, hour, minute, second)
            is_bull = True if (row[2] == 'True') else False
            tweet = {'time': date_parsed, 
                    'isBull': is_bull,
                    'symbol': row[1]}
            result.append(tweet)
    return result


# Initialize user features 
def initializeUserFeatures(user):
    result = {}
    result['_id'] = user
    keys = ['correct_predictions', 'num_predictions',
            'unique_correct_predictions', 'unique_num_predictions', 
            'unique_return', 'unique_return_log', 'unique_return_w1']

    for k in keys:
        result[k] = {}
        result[k]['bull'] = 0
        result[k]['bear'] = 0

    result['perStock'] = {}
    return result


# Calculate user's features based on tweets before this date
# Loop through all tweets made by user and feature extract per user
def calculateUserFeatures(username, date, all_user_features, tweets):
    # date = date - datetime.timedelta(days=3) # Find all tweet/predictions before this date
    unique_stocks = {} # Keep track of unique tweets per day/stock
    result = {} # Resulting user features

    if (username in all_user_features):
        result = all_user_features[username]
        last_updated = result['last_updated'] # last time that was parsed

        # Filter by tweets before the current date and after last updated date
        for tweet in tweets:
            # if (tweet['time'] >= last_updated and tweet['time'] < date and tweet['symbol'] in constants['top_stocks']):
            if (tweet['time'] >= last_updated and tweet['time'] < date):
                updateUserFeatures(result, tweet, unique_stocks)
    else:
        result = initializeUserFeatures(username) # initialize user features for first time
        # Only filter by all tweets before current date
        for tweet in tweets:
            # if (tweet['time'] < date and tweet['symbol'] in constants['top_stocks']):
            if (tweet['time'] < date):
                updateUserFeatures(result, tweet, unique_stocks)

    result['last_updated'] = date # update time it was parsed so dont have to reparse

    # Update unique predictions per day features
    for time_string in unique_stocks:
        tweeted_date = unique_stocks[time_string]['time']
        w = findWeight(tweeted_date, 'log(x)') # weighted based on time of tweet
        symbol = unique_stocks[time_string]['symbol']

        # Find whether tweet was bull or bear based on last tweet prediction
        label = 'bull' if unique_stocks[time_string]['last_prediction'] else 'bear'

        percent_change = unique_stocks[time_string]['percent_change']
        correct_prediction = (label == 'bull' and percent_change >= 0) or (label == 'bear' and percent_change <= 0)
        correct_prediction_num = 1 if correct_prediction else 0
        percent_return = abs(percent_change) if correct_prediction else -abs(percent_change)

        result['unique_return_w1'][label] += w * percent_return
        result['unique_correct_predictions'][label] += correct_prediction_num
        result['unique_num_predictions'][label] += 1
        result['unique_return'][label] += percent_return

        # return unique (log) Weighted by number of times posted that day
        num_labels = unique_stocks[time_string]['count']
        val = percent_return * (math.log10(num_labels) + 1)
        result['unique_return_log'][label] += val

        if (symbol in constants['top_stocks']):
            result['perStock'][symbol]['unique_return_log'][label] += val
            result['perStock'][symbol]['unique_return_w1'][label] += w * percent_return
            result['perStock'][symbol]['unique_correct_predictions'][label] += correct_prediction_num
            result['perStock'][symbol]['unique_num_predictions'][label] += 1
            result['perStock'][symbol]['unique_return'][label] += percent_return

    all_user_features[username] = result
    return result


# Finds tweets for the given date range and stores them locally to be cached
def writeTweets(start_date, end_date, num_top_stocks, overwrite=False):
    print("Setting up tweets")
    day_increment = datetime.timedelta(days=1)
    all_dates = findAllDays(start_date, end_date)

    # Find stocks to parse per day
    for date in all_dates:
        date_string = date.strftime("%Y-%m-%d")
        stocks = getTopStocksforWeek(date, num_top_stocks) # top stocks for the week
        for symbol in stocks:
            path = 'stock_files/' + symbol + '.pkl'
            tweets_per_stock = readPickleObject(path)
            if (overwrite == False and date_string in tweets_per_stock):
                print(symbol, date_string, len(tweets_per_stock[date_string]), "EXISTS")
                continue

            # Find all tweets for the given day
            date_start = datetime.datetime(date.year, date.month, date.day, 0, 0)
            date_end = datetime.datetime(date.year, date.month, date.day) + day_increment
            tweets = fetchTweets(date_start, date_end, symbol)
            tweets_per_stock[date_string] = tweets

            # Write to the stock pickled object
            writePickleObject(path, tweets_per_stock)
            print(symbol, date_string, len(tweets_per_stock[date_string]))


# Fetch tweets from mongodb tweets collection
def fetchTweets(date_start, date_end, symbol):
    tweets_collection = constants['stocktweets_client'].get_database('tweets_db').tweets
    query = {"$and": [{'symbol': symbol},
                        {"$or": [
                                {'isBull': True},
                                {'isBull': False}
                        ]},
                        {'time': {'$gte': date_start,
                                    '$lt': date_end}}]}
    tweets = list(tweets_collection.find(query))
    tweets = list(map(lambda t: {'user': t['user'], 'time': t['time'], 'w': findWeight(t['time'], 'log(x)'), 'isBull': t['isBull']}, tweets))
    tweets.sort(key=lambda tweet: tweet['time'], reverse=True)
    return tweets


def buildStockFeatures():
    result = {}
    labels = ['bull', 'bear', 'bull_w', 'bear_w']
    features = ['return_w1', 'return_w1_s', 'return', 'return_log', 'return_s', 'return_log_s']
    for l in labels:
        result[l] = 0
        for f in features:
            result[l + '_' + f] = 0
    return result



# Retrieve cached pregenerated user features
def newCalculateUserFeatures(username, symbol, date, all_user_features):
    if (username not in all_user_features): # Check that user features are generated
        return None

    features = all_user_features[username]
    last_tweet_date = features['last_tweet_date']

    # If last tweet is after current date, there is no previous data
    if (date < last_tweet_date):
        return None

    # Find general stats
    result = {}
    general_features = features['general']
    general_dates = features['general_dates']
    curr_date_str = '%d-%02d-%02d' % (date.year, date.month, date.day)
    for date_str in general_dates: # Find first date feature that is less than the current date
        if (date_str > curr_date_str):
            continue
        else:
            result = general_features[date_str]
            break

    # Find stock specific stats
    stock_features = features['per_stock']
    if (symbol not in stock_features):
        return result

    dates_tweeted = sorted(stock_features[symbol].keys(), reverse=True)
    for date_str in dates_tweeted:
        if (date_str <= curr_date_str):
            result[symbol] = stock_features[symbol][date_str]
            break

    return result



# Return feature parameters based on tweets for a given trading day/s
# Builds user features as more information is seen about that user
def stockFeatures(tweets, symbol, all_user_features):
    result = buildStockFeatures()
    bull_count = 0
    bear_count = 0
    seen_users = {}

    # Assume tweets sorted from new to old
    # Find all last predictions and counts
    for tweet in tweets:
        username = tweet['user']
        # Don't analyze if not an expert user
        if (username not in all_user_features):
            continue
        isBull = tweet['isBull']
        tweeted_date = tweet['time']
        w = tweet['w']
        # Only look at the most recent prediction by user
        if (username in seen_users):
            # If previous prediction was the same as last prediction, add to weighting
            prev_prediction = seen_users[username]['isBull']
            if (isBull == prev_prediction):
                seen_users[username]['count'] += w
            continue
        seen_users[username] = {
            'user': tweet['user'],
            'time': tweet['time'],
            'isBull': isBull,
            'count': w,
            'tweeted_weight': w
        }

    # Look at all unique predictions and their counts
    for user in seen_users:
        username = seen_users[user]['user']
        tweeted_date = seen_users[user]['time']
        w = seen_users[user]['tweeted_weight'] # weighted based on time of tweet
        label = 'bull' if seen_users[user]['isBull'] else 'bear'

        # Find user features (return, accuracy, etc.) before tweeted date
        user_info = newCalculateUserFeatures(username, symbol, tweeted_date, all_user_features)
        if (user_info == None):
            continue

        accuracy_unique = findFeature(user_info, '', 'accuracy', label)
        accuracy_unique_s = findFeature(user_info, symbol, 'accuracy', label)

        # Filter by accuracy
        if (accuracy_unique < 0.49 or accuracy_unique_s < 0.4):
            continue

        num_tweets = user_info['num_predictions']['bull'] + user_info['num_predictions']['bear']
        num_tweets_unique = user_info['unique_num_predictions']['bull'] + user_info['unique_num_predictions']['bear']
        num_tweets_s = findFeature(user_info, symbol, 'num_predictions', None)
        num_tweets_s_unique = findFeature(user_info, symbol, 'unique_num_predictions', None)

        # Filter by number of tweets
        if (num_tweets <= 50 or num_tweets_s <= 10 or num_tweets_unique <= 10 or num_tweets_s_unique <= 5):
            continue

        return_unique = (user_info['unique_return']['bear'] + user_info['unique_return']['bull']) / 2
        return_unique_log = (user_info['unique_return_log']['bear'] + user_info['unique_return_log']['bull']) / 2
        return_unique_w1 = (user_info['unique_return_w1']['bear'] + user_info['unique_return_w1']['bull']) / 2
        return_unique_s = findFeature(user_info, symbol, 'unique_return', None) / 2
        return_unique_log_s = findFeature(user_info, symbol, 'unique_return_log', None) / 2
        return_unique_w1_s = findFeature(user_info, symbol, 'unique_return_w1', None) / 2

        # Filter by return
        if (return_unique < 30 or return_unique_s < 1 or return_unique_log < 1 or
            return_unique_log_s < 1 or return_unique_w1 < 1 or return_unique_w1_s < 1):
            continue

        user_values = {
            'accuracy_unique': accuracy_unique,
            'accuracy_unique_s': accuracy_unique_s,
            'num_tweets': num_tweets,
            'num_tweets_s': num_tweets_s,
            'return_unique': return_unique,
            'return_unique_s': return_unique_s,
        }

        # Give user a weight between 0 and 1 and apply to all features
        user_weight = weightedUserPrediction(user_info, symbol, label, user_values)
        tweet_value = user_weight * w

        # if (symbol == 'XSPA'):
        #     print(tweeted_date, user, w, seen_users[user]['count'], round(num_tweets_unique, 2), round(num_tweets_s_unique, 2), round(accuracy_unique, 2), round(return_unique, 2), round(return_unique_s, 2))
        # print(username, num_tweets, num_tweets_s, accuracy_unique, accuracy_unique_s)

        if (seen_users[user]['isBull']):
            bull_count += 1
        else:
            bear_count += 1
        # print(user, user_info)
        return_unique = math.log10(return_unique) + 1
        return_unique_s = math.log10(return_unique_s) + 1
        return_unique_log = math.log10(return_unique_log) + 1
        return_unique_log_s = math.log10(return_unique_log_s) + 1
        return_unique_w1 = math.log10(return_unique_w1) + 1
        return_unique_w1_s = math.log10(return_unique_w1_s) + 1

        result[label] += tweet_value
        result[label + '_return_w1'] += tweet_value * return_unique_w1
        result[label + '_return_w1_s'] += tweet_value * return_unique_w1_s
        result[label + '_return'] += tweet_value * return_unique
        result[label + '_return_log'] += tweet_value * return_unique_log
        result[label + '_return_s'] += tweet_value * return_unique_s
        result[label + '_return_log_s'] += tweet_value * return_unique_log_s

        # return unique (log) Weighted by number of times posted that day
        num_prediction_log = math.log10(seen_users[user]['count']) + 1
        result[label + '_w'] += tweet_value * num_prediction_log
        result[label + '_w_return_w1'] += tweet_value * return_unique_w1 * num_prediction_log
        result[label + '_w_return_w1_s'] += tweet_value * return_unique_w1_s * num_prediction_log
        result[label + '_w_return'] += tweet_value * return_unique * num_prediction_log
        result[label + '_w_return_log'] += tweet_value * return_unique_log * num_prediction_log
        result[label + '_w_return_s'] += tweet_value * return_unique_s * num_prediction_log
        result[label + '_w_return_log_s'] += tweet_value * return_unique_log_s * num_prediction_log
        # bucket.append([num_tweets, num_tweets_unique, num_tweets_s, num_tweets_s_unique, accuracy_unique, accuracy_unique_s, return_unique, return_unique_s])

    result['bull_count'] = bull_count
    result['bear_count'] = bear_count
    # print(result['bull_count'], result['bear_count'])
    return result



##
# All per stocks featuers are weighted by (x(1 + tweets per stock))
##

# unique accuracy (0 - 1) x return per stock (0 - 1) x number of tweets = if - - make negative
# unique accuracy x return x number of tweets = if - - make negative

# unique return per stock = -150 - 150 -> -1 - 1
# unique return = -150 - 150 -> -1 - 1

# accuracy per stock with # tweets = accuracy * # min number of tweets per stock 
# accuracy in general with # tweets =  accuracy * # min number of tweets 

# unique accuracy per stock = 0 - 1 -> -1 - 1
# unique accuracy in general = 0 - 1 -> -1 - 1

# min number of tweets per stock (0) = log(# tweets) -> 1 - 100 -> 0 - 2 -> 0 - 1 
# min number of tweets (bull/bear) in general (75) = log(# tweets) -> 75 - 600 -> 2 - 4 -> 0 - 1

# negative weight for below accuracy

# Return a number based on how reliable the users prediction is (0 - 1)
# TODO: Ideally use features such as join date, follower following ratio etc
# TODO: instead of log, use distribution of the data
# TODO: use return_uniquelog instead of returnUnique

def weightedUserPrediction(user, symbol, label, user_values):
    num_tweets = user_values['num_tweets']
    num_tweets_s = user_values['num_tweets_s']

    # Scale between 800 / 400
    scaled_num_tweets = math.sqrt(num_tweets) / math.sqrt(800)
    scaled_num_tweets_s = math.sqrt(num_tweets_s) / math.sqrt(400)
    if (scaled_num_tweets > 1):
        scaled_num_tweets = 1
    if (scaled_num_tweets_s > 1):
        scaled_num_tweets_s = 1

    return_unique = user_values['return_unique']
    return_unique_s = user_values['return_unique_s']


    # (2) scale between 0 and 1
    scaled_return_unique = math.sqrt(return_unique) / math.sqrt(300)
    scaled_return_unique_s = math.sqrt(return_unique_s) / math.sqrt(150)
    if (scaled_return_unique > 1):
        scaled_return_unique = 1
    if (scaled_return_unique_s > 1):
        scaled_return_unique_s = 1


    # (3) all features combined (scale accuracy from 0.5 - 1 to between 0.7 - 1.2)
    accuracy_unique = user_values['accuracy_unique'] + 0.2
    accuracy_unique_s = user_values['accuracy_unique_s'] + 0.2

    all_features = 2 * accuracy_unique * scaled_num_tweets * scaled_return_unique
    all_features_s = 2 * accuracy_unique_s * scaled_num_tweets_s * scaled_return_unique_s

    return (scaled_num_tweets + scaled_num_tweets_s + scaled_return_unique +
            scaled_return_unique_s + all_features + all_features_s) / 8


# Find feature for given user based on symbol and feature name
def findFeature(feature_info, symbol, feature_name, bull_bear):
    # If finding stock specific feature, check if data exists, else just use general data
    if (symbol in feature_info):
        feature_info = feature_info[symbol]

    # Not bull or bear specific feature
    if (bull_bear == None):
        if (feature_name == 'accuracy'): # looking for a fraction
            bull_res_n = feature_info['unique_correct_predictions']['bull']
            bear_res_n = feature_info['unique_correct_predictions']['bear']
            bull_res_d = feature_info['unique_num_predictions']['bull']
            bear_res_d = feature_info['unique_num_predictions']['bear']
            total_nums = bull_res_d + bear_res_d
            # If never tweeted about this stock
            if (total_nums == 0):
                return 0
            return (bull_res_n + bear_res_n) / total_nums
        else: # only looking for one value
            bull_res = feature_info[feature_name]['bull']
            bear_res = feature_info[feature_name]['bear']
            return bull_res + bear_res
    else:
        if (feature_name == 'accuracy'): # looking for a fraction
            correct = feature_info['unique_correct_predictions'][bull_bear]
            total_nums = feature_info['unique_num_predictions'][bull_bear]
            if (total_nums == 0): # If never tweeted about this stock
                return 0
            spec_acc = correct / total_nums # bull/bear specific accuracy

            # General accuracy
            bull_res_n = feature_info['unique_correct_predictions']['bull']
            bear_res_n = feature_info['unique_correct_predictions']['bear']
            bull_res_d = feature_info['unique_num_predictions']['bull']
            bear_res_d = feature_info['unique_num_predictions']['bear']
            total_nums = bull_res_d + bear_res_d
            general_acc = (bull_res_n + bear_res_n) / total_nums
            return (general_acc + spec_acc) / 2
        else: # only looking for one value
            res = feature_info[feature_name][bull_bear]
            return res
