import os
import copy
import math
import datetime
import numpy as np
import statistics
from functools import reduce
from .hyperparameters import constants
from .stockAnalysis import getTopStocksforWeek
from scipy.optimize import minimize
from .stockPriceAPI import (findCloseOpenCached, isTradingDay, findDateString)
from .helpers import (readPickleObject, writePickleObject, findTradingDays)
from .newPrediction import (cachedUserTweets, initializeUserFeatures, findTweets)
from .userAnalysis import updateUserFeatures


# Find all usernames from folder
def findUserList():
    users = []
    arr = os.listdir('user_tweets/')
    for u in arr:
        username = u[:-4]
        users.append(username)
    users.sort()
    return users


# Pregenerate all user features based off tweets
# Extract GENEARL or STOCK specific user return, accuracy, tweet count, etc.
def pregenerateAllUserFeatures(general=True):
    users = findUserList()
    result = {}
    not_found = 0
    for i in range(len(users)):
        username = users[i]
        # Find user features 
        pregenerated = pregenerateUserFeatures(username, general)
        features = list(pregenerated.keys())

        # If no dates/features were found
        if (len(features) == 0):
            not_found += 1
            continue
        last_date = features[0] # Date of last tweet

        pregenerated['last_tweet_date'] = datetime.datetime.strptime(last_date, '%Y-%m-%d')
        if (i % 1000 == 0):
            print(not_found)
            print(i)
        result[username] = pregenerated

    result_path = 'newPickled/user_features.pkl'
    if (general == False):
        result_path = 'newPickled/user_features_stock.pkl'
    writePickleObject(result_path, result)


# Generate features from users historical tweets
# Either return stock specific user features or general user features
def pregenerateUserFeatures(username, general=True):
    day_increment = datetime.timedelta(days=1)
    cached_tweets = cachedUserTweets(username) # Tweets from user
    if (cached_tweets == None):
        return
    cached_prices = constants['cached_prices']
    top_stocks = constants['top_stocks']

    dates = []
    # Extract the unique dates that the user tweeted
    for tweet in cached_tweets:
        time = tweet['time']
        symbol = tweet['symbol']

        # Only look at user features that are in the top stocks to save space
        # if (general == False and symbol not in top_stocks):
        #     continue

        if (symbol not in top_stocks):
            continue
        
        # Find the trading day the tweet corresponds to
        if (time.hour >= 16):
            time += day_increment
        while (isTradingDay(time) == False):
            time += day_increment

        time = datetime.datetime(time.year, time.month, time.day, 16)
        if (time not in dates):
            dates.append(time)

    # Go from past to present
    dates.sort()
    result = {}
    buildup_result = {} # cached result that is being built up
    for date in dates:
        day_res = calculateUserFeatures(username, date, cached_prices, general,
                                        buildup_result, cached_tweets)
        
        # Set as the next trading day's user feature
        date += day_increment
        while (isTradingDay(date) == False):
            date += day_increment
        date_string = '%d-%02d-%02d' % (date.year, date.month, date.day)
        copied_res = copy.deepcopy(day_res)

        # print(date_string)
        # print('num_predictions', copied_res['num_predictions']['bull'] + copied_res['num_predictions']['bear'])
        # print('return_unique', copied_res['unique_return']['bull'] + copied_res['unique_return']['bear'])
        # print('\n')
        # Remove stock specific data for general user stats
        if (general):
            del copied_res['perStock']
            del copied_res['_id']
            del copied_res['last_updated']
            result[date_string] = copied_res
        else:
            result[date_string] = copied_res['perStock']

    return result



# Calculate user's features based on tweets before this date
# Loop through all tweets made by user and feature extract per user
def calculateUserFeatures(username, date, cached_prices, general, all_user_features, tweets):
    unique_stocks = {} # Keep track of unique tweets per day/stock
    result = {} # Resulting user features

    if (username in all_user_features):
        result = all_user_features[username]
        last_updated = result['last_updated'] # last time that was parsed

        # Filter by tweets before the current date and after last updated date
        for tweet in tweets:
            # Only look at user features that are in the top stocks to save space
            # if (general == False and tweet['symbol'] not in constants['top_stocks']):
            #     continue
            if (tweet['symbol'] not in constants['top_stocks']):
                continue
            if (tweet['time'] >= last_updated and tweet['time'] < date):
                updateUserFeatures(username, result, tweet, unique_stocks, cached_prices)
    else:
        result = initializeUserFeatures(username) # initialize user features for first time
        # Only filter by all tweets before current date
        for tweet in tweets:
            # Only look at user features that are in the top stocks to save space
            # if (general == False and tweet['symbol'] not in constants['top_stocks']):
            #     continue
            if (tweet['symbol'] not in constants['top_stocks']):
                continue
            if (tweet['time'] < date):
                updateUserFeatures(username, result, tweet, unique_stocks, cached_prices)

    result['last_updated'] = date # update time it was parsed so dont have to reparse

    # Update unique predictions per day features
    for time_string in unique_stocks:
        symbol = unique_stocks[time_string]['symbol']
        # times = unique_stocks[time_string]['times']
        # average_time = findAverageTime(times)

        # Find whether tweet was bull or bear based on majority
        label = 'bull'
        if (unique_stocks[time_string]['bear'] > unique_stocks[time_string]['bull']):
            label = 'bear'
        if (unique_stocks[time_string]['bear'] == unique_stocks[time_string]['bull']):
            label = 'bull' if unique_stocks[time_string]['last_prediction'] else 'bear'

        percent_change = unique_stocks[time_string]['percent_change']
        correct_prediction = (label == 'bull' and percent_change >= 0) or (label == 'bear' and percent_change <= 0)
        correct_prediction_num = 1 if correct_prediction else 0
        percent_return = abs(percent_change) if correct_prediction else -abs(percent_change)

        result['unique_correct_predictions'][label] += correct_prediction_num
        result['perStock'][symbol]['unique_correct_predictions'][label] += correct_prediction_num
        result['unique_num_predictions'][label] += 1
        result['perStock'][symbol]['unique_num_predictions'][label] += 1
        result['unique_return'][label] += percent_return
        result['perStock'][symbol]['unique_return'][label] += percent_return

        # return unique (log) Weighted by number of times posted that day
        num_labels = unique_stocks[time_string][label]
        val = percent_return * (math.log10(num_labels) + 1)
        result['unique_return_log'][label] += val
        result['perStock'][symbol]['unique_return_log'][label] += val

    all_user_features[username] = result
    return result


# Find user features up to or before a given date
def findUserFeatures(username, user_features, date):
    if (username not in user_features):
        return None
    features = user_features[username]
    last_tweet_date = features['last_tweet_date']
    # If user hasn't tweeted anything yet
    if (date < last_tweet_date):
        return None
    del features['last_tweet_date']
    keys = sorted(features, reverse=True)
    features['last_tweet_date'] = last_tweet_date
    curr_date_str = '%d-%02d-%02d' % (date.year, date.month, date.day)
    for date_str in keys:
        if (date_str <= curr_date_str):
            return features[date_str]
    return None


# Generate user features matrice
# Result = d(days) x u(users) x n(features)
def generateUserMatrix(start_date, end_date):
    user_features = readPickleObject('newPickled/user_features.pkl')
    users_actual = sorted(list(user_features.keys()))
    dates = findTradingDays(start_date, end_date)
    result = np.zeros(shape=(2, len(dates), len(users_actual), 3))

    # For each user, fill in 3d matrix by date
    for i in range(len(dates)):
        date = dates[i]
        print(date)
        for j in range(len(users_actual)):
            username = users_actual[j]
            features = findUserFeatures(username, user_features, date)
            if (features == None):
                continue
            total_tweets_bull = features['unique_num_predictions']['bull']
            total_tweets_bear = features['unique_num_predictions']['bear']
            if (total_tweets_bull + total_tweets_bear == 0):
                continue
            correct_tweets_bull = features['unique_correct_predictions']['bull']
            correct_tweets_bear = features['unique_correct_predictions']['bear']
            accuracy_bull = 0
            accuracy_bear = 0
            if (total_tweets_bull != 0):
                accuracy_bull = correct_tweets_bull / total_tweets_bull
            if (total_tweets_bear != 0):
                accuracy_bear = correct_tweets_bear / total_tweets_bear
            return_percent_bull = features['unique_return']['bull']
            return_percent_bear = features['unique_return']['bear']
            result[0][i][j] = [total_tweets_bull, accuracy_bull, return_percent_bull]
            result[1][i][j] = [total_tweets_bear, accuracy_bear, return_percent_bear]

    np.save('user_matrice.npy', result)




def findUserStockFeatures(username, symbol, user_features, date):
    if (username not in user_features):
        return None
    features = user_features[username]
    last_tweet_date = features['last_tweet_date']
    if (date < last_tweet_date):
        return None
    del features['last_tweet_date']
    keys = sorted(features, reverse=True)
    features['last_tweet_date'] = last_tweet_date
    curr_date_str = '%d-%02d-%02d' % (date.year, date.month, date.day)
    for date_str in keys:
        if (date_str <= curr_date_str):
            if (symbol in features[date_str]):
                return features[date_str][symbol]
            else:
                return None
    return None


# Generate stock specific user features matrice
# Result = d(days) x s(stocks) x u(users) x n(features)
def generateUserStockMatrix(start_date, end_date):
    user_stock_features = readPickleObject('newPickled/user_features_stock.pkl')
    users = sorted(list(user_stock_features.keys()))
    top_stocks = list(constants['top_stocks'])
    top_stocks.sort()
    dates = findTradingDays(start_date, end_date)
    result = np.zeros(shape=(2, len(dates), len(top_stocks), len(users), 3))

    # For each user, fill in 4d matrix by date
    for i in range(len(dates)):
        date = dates[i]
        for j in range(len(top_stocks)):
            symbol = top_stocks[j]
            for k in range(len(users)):
                username = users[k]
                features = findUserStockFeatures(username, symbol, user_stock_features, date)
                if (features == None):
                    continue
                total_tweets_bull = features['unique_num_predictions']['bull']
                total_tweets_bear = features['unique_num_predictions']['bear']
                if (total_tweets_bull + total_tweets_bear == 0):
                    continue
                correct_tweets_bull = features['unique_correct_predictions']['bull']
                correct_tweets_bear = features['unique_correct_predictions']['bear']
                accuracy_bull = 0
                accuracy_bear = 0
                if (total_tweets_bull != 0):
                    accuracy_bull = correct_tweets_bull / total_tweets_bull
                if (total_tweets_bear != 0):
                    accuracy_bear = correct_tweets_bear / total_tweets_bear
                return_percent_bull = features['unique_return']['bull']
                return_percent_bear = features['unique_return']['bear']
                result[0][i][j][k] = [total_tweets_bull, accuracy_bull, return_percent_bull]
                result[1][i][j][k] = [total_tweets_bear, accuracy_bear, return_percent_bear]
                
                # username = users[k]
                # features = findUserStockFeatures(username, symbol, user_stock_features, date)
                # if (features == None):
                #     continue
                # total_tweets = features['unique_num_predictions']['bull'] + features['unique_num_predictions']['bear']
                # if (total_tweets == 0):
                #     continue
                # correct_tweets = features['unique_correct_predictions']['bull'] + features['unique_correct_predictions']['bear']
                # accuracy = correct_tweets / total_tweets
                # return_percent = features['unique_return']['bull'] + features['unique_return']['bear']
                # result[i][j][k] = [total_tweets, accuracy, return_percent]

    np.save('user_stock_matrice.npy', result)


# Preprocess user matrice by adding cutoffs and standardizing
def preprocessUserMatrix():
    user_matrice = np.load('user_matrice.npy')

    bull_matrice = user_matrice[0]
    bull_matrice[:,:,0][bull_matrice[:,:,0] <= 20] = 0
    bull_matrice = np.ma.masked_equal(bull_matrice, 0)
    non_zero_count = np.count_nonzero(bull_matrice[:,:,0], axis=1)
    summed = bull_matrice[:,:,0].sum(axis=1)
    mean = summed / non_zero_count
    std = np.std(bull_matrice[:,:,0], axis=1)

    bull_matrice[:,:,0] = (bull_matrice[:,:,0] - mean[:,None]) / std[:,None]
    bull_matrice[:,:,0] = np.add(bull_matrice[:,:,0], 2)
    bull_matrice[:,:,0][bull_matrice[:,:,0] <= 0] = 0
    bull_matrice[:,:,0][bull_matrice[:,:,0] > 4] = 4
    bull_matrice[:,:,0] = np.divide(bull_matrice[:,:,0], 4)
    bull_matrice[bull_matrice.mask] = 0
    user_matrice[0] = bull_matrice

    bear_matrice = user_matrice[1]
    bear_matrice[:,:,0][bear_matrice[:,:,0] <= 10] = 0
    bear_matrice = np.ma.masked_equal(bear_matrice, 0)
    non_zero_count = np.count_nonzero(bear_matrice[:,:,0], axis=1)
    summed = bear_matrice[:,:,0].sum(axis=1)
    mean = summed / non_zero_count
    std = np.std(bear_matrice[:,:,0], axis=1)

    bear_matrice[:,:,0] = (bear_matrice[:,:,0] - mean[:,None]) / std[:,None]
    bear_matrice[:,:,0] = np.add(bear_matrice[:,:,0], 2)
    bear_matrice[:,:,0][bear_matrice[:,:,0] <= 0] = 0
    bear_matrice[:,:,0][bear_matrice[:,:,0] > 4] = 4
    bear_matrice[:,:,0] = np.divide(bear_matrice[:,:,0], 4)
    bear_matrice[bear_matrice.mask] = 0
    user_matrice[1] = bear_matrice


    min_accuracy = 0.5
    user_matrice[:,:,:,1][user_matrice[:,:,:,1] <= min_accuracy] = 0
        

    min_return = -50
    max_return = 250
    diff = max_return - min_return
    user_matrice[:,:,:,2][user_matrice[:,:,:,2] <= min_return] = min_return
    user_matrice[:,:,:,2][user_matrice[:,:,:,2] > max_return] = max_return
    user_matrice[:,:,:,2] = np.add(user_matrice[:,:,:,2], -min_return)
    user_matrice[:,:,:,2] = np.divide(user_matrice[:,:,:,2], diff)
    # print(np.round(user_matrice[0,25,:20],2))
    np.save('user_matrice_filtered.npy', user_matrice)



def preprocessUserStockMatrix():
    user_stock_matrice = np.load('user_stock_matrice.npy')
    # Scale tweet number between 0 and 1 based off of each stock's distribution
    # Look at most recent date to find individual stock distribution
    print("Standardizing Tweet Count")
    bull_matrice = user_stock_matrice[0]
    bull_matrice[:,:,:,0][bull_matrice[:,:,:,0] <= 5] = 0
    bull_matrice = np.ma.masked_equal(bull_matrice, 0)
    non_zero_count = np.count_nonzero(bull_matrice[:,:,:,0], axis=2)
    summed = bull_matrice[:,:,:,0].sum(axis=2)
    mean = summed / non_zero_count
    std = np.std(bull_matrice[:,:,:,0], axis=2)

    bull_matrice[:,:,:,0] = (bull_matrice[:,:,:,0] - mean[:,:,None]) / std[:,:,None]
    bull_matrice[:,:,:,0] = np.add(bull_matrice[:,:,:,0], 2)
    bull_matrice[:,:,:,0][bull_matrice[:,:,:,0] <= 0] = 0
    bull_matrice[:,:,:,0][bull_matrice[:,:,:,0] > 4] = 4
    bull_matrice[:,:,:,0] = np.divide(bull_matrice[:,:,:,0], 4)
    bull_matrice[bull_matrice.mask] = 0
    user_stock_matrice[0] = bull_matrice

    bear_matrice = user_stock_matrice[1]
    bear_matrice[:,:,:,0][bear_matrice[:,:,:,0] <= 5] = 0
    bear_matrice = np.ma.masked_equal(bear_matrice, 0)
    non_zero_count = np.count_nonzero(bear_matrice[:,:,:,0], axis=2)
    summed = bear_matrice[:,:,:,0].sum(axis=2)
    mean = summed / non_zero_count
    std = np.std(bear_matrice[:,:,:,0], axis=2)

    bear_matrice[:,:,:,0] = (bear_matrice[:,:,:,0] - mean[:,:,None]) / std[:,:,None]
    bear_matrice[:,:,:,0] = np.add(bear_matrice[:,:,:,0], 2)
    bear_matrice[:,:,:,0][bear_matrice[:,:,:,0] <= 0] = 0
    bear_matrice[:,:,:,0][bear_matrice[:,:,:,0] > 4] = 4
    bear_matrice[:,:,:,0] = np.divide(bear_matrice[:,:,:,0], 4)
    bear_matrice[bear_matrice.mask] = 0
    user_stock_matrice[1] = bear_matrice


    # Do the same for user returns
    # Sum of returns for each stock
    print("Standardizing Return")
    min_return = -50
    max_return = 250
    diff = max_return - min_return
    user_stock_matrice[:,:,:,:,2][user_stock_matrice[:,:,:,:,2] <= min_return] = min_return
    user_stock_matrice[:,:,:,:,2][user_stock_matrice[:,:,:,:,2] > max_return] = max_return
    user_stock_matrice[:,:,:,:,2] = np.add(user_stock_matrice[:,:,:,:,2], -min_return)
    user_stock_matrice[:,:,:,:,2] = np.divide(user_stock_matrice[:,:,:,:,2], diff)


    # Remove all users that are below 30%
    print("Adjust Accuracy")
    min_accuracy = 0.3
    user_stock_matrice[user_stock_matrice[:,:,:,:,1] <= min_accuracy] = 0

    np.save('user_stock_matrice_filtered.npy', user_stock_matrice)


# Convert user predictions to an array of 
#  0 (no prediction)
#  1 (bull prediction)
# -1 (bear prediction)
# Result = d(days) x u(users) x s(stocks)
def generateStockPredictions(start_date, end_date, write=False):
    dates = findTradingDays(start_date, end_date)
    top_stocks = list(constants['top_stocks'])
    top_stocks.sort()
    user_features = readPickleObject('newPickled/user_features.pkl')
    users = sorted(list(user_features.keys()))

    # user indexes for inserting predictions
    user_index = {}
    for i in range(len(users)):
        username = users[i]
        user_index[username] = i

    # Cache all user tweets for quick access
    all_stock_tweets = {}
    for symbol in top_stocks:
        stock_path = 'new_stock_files/' + symbol + '.pkl'
        tweets_per_stock = readPickleObject(stock_path)
        all_stock_tweets[symbol] = tweets_per_stock

    result = np.zeros(shape=(len(dates), len(users), len(top_stocks)))

    # Loop through all dates and fill in user predictions for all d dates and s stocks
    for i in range(len(dates)):
        date = dates[i]
        print(date)
        top_for_week = getTopStocksforWeek(date, 20)
        for j in range(len(top_stocks)):
            users_seen = set([]) # use the most recent prediction per stock
            symbol = top_stocks[j]
            if (symbol not in top_for_week):
                continue
            cached_tweets = all_stock_tweets[symbol] # cached tweets
            tweets = findTweets(date, cached_tweets, symbol)
            for tweet in tweets:
                username = tweet['user']
                isBull = tweet['isBull']
                if (username in users_seen or username not in user_index):
                    continue
                users_seen.add(username)
                user_i = user_index[username]
                label = 1 if isBull else -1
                result[i][user_i][j] = label

    if (write):
        np.save('user_predictions.npy', result)
    return result


# Close open price matrix for top s stocks
# Result = d(days) x s(stocks)
def generateCloseOpenMatrix(start_date, end_date):
    dates = findTradingDays(start_date, end_date)
    cached_prices = constants['cached_prices']
    top_stocks = list(constants['top_stocks'])
    top_stocks.sort()
    result = np.zeros(shape=(len(dates), len(top_stocks)))

    for i in range(len(dates)):
        date = dates[i]
        print(date)
        # Only choose top 20 stocks for the week
        for j in range(len(top_stocks)):
            symbol = top_stocks[j]
            close_open = findCloseOpenCached(symbol, date, cached_prices)
            if (close_open == None):
                continue
            result[i][j] = close_open[2]

    np.save('close_open_matrice.npy', result)



# Find user weightings based on general user weightings and per stock user weightings
# Result = d(days) x s(stocks) x u(users)
def findTotalUserWeightings(start_date, end_date, user_matrice, user_stock_matrice, weightings):
    top_stocks = list(constants['top_stocks'])

    # Match dimensions of user_stock matrics by converting 
    # d(days) x u(users) => d(days) x s(stocks) x u(users)
    user_weighted = np.dot(user_matrice, weightings) # 104 x 57000
    repeated_user_weights = np.repeat(user_weighted[:,None], len(top_stocks), axis=1) # 104 x 78 x 57000

    # Calculate user stock weights
    user_stock_weighted = np.dot(user_stock_matrice, weightings) # 104 x 78 x 57000

    # Add user and user-stock weightings together
    total_user_weight = repeated_user_weights + user_stock_weighted # 104 x 78 x 57000

    return total_user_weight


def calculateReturn(start_date, end_date, weightings):
    np.seterr(divide='ignore', invalid='ignore')
    top_stocks = list(constants['top_stocks'])
    top_stocks.sort()
    user_matrice = np.load('user_matrice_filtered.npy') # 104 days x 57000 users x 3 weightings
    user_stock_matrice = np.load('user_stock_matrice_filtered.npy') # 104 days x 78 stocks x 57000 users x 3 weightings
    user_predictions = np.load('user_predictions.npy') # 104 days x 57000 users x 78 stocks
    close_open_matrice = np.load('close_open_matrice.npy') # 104 x 78

    # 104 days x 78 stocks x 57000 users
    total_user_weight = findTotalUserWeightings(start_date, end_date, user_matrice, user_stock_matrice, weightings)

    # normalize user predictions
    count_total = np.count_nonzero(user_predictions, axis=1) # counts per day per stock
    standardize_prediction = user_predictions / count_total[:,None]
    standardize_prediction[np.isnan(standardize_prediction)] = 0
    
    # Multiply user weights with user predictions
    diagonal_weights = np.einsum('ijk,ikj->ij', total_user_weight, standardize_prediction) # 104 x 78
    diagonal_weights[close_open_matrice<=0] = 0 # only keep top 20 stocks

    # Find top n stocks to look at
    top_n_stocks = 3
    sorted_index = np.argsort(-abs(diagonal_weights),axis=1)
    range_i = np.arange(diagonal_weights.shape[0])

    # Find top stocks and corresponding close open
    top_weights = diagonal_weights[range_i[:,None], sorted_index][:,:top_n_stocks]
    top_close_open = close_open_matrice[range_i[:,None], sorted_index][:,:top_n_stocks]
    total_weights = np.sum(abs(top_weights), axis=1)[:,None]
    relative_weight = top_weights / total_weights
    relative_weight[np.isnan(relative_weight)] = 0

    weighted_returns_perstock = np.multiply(relative_weight, top_close_open)
    weighted_returns = np.sum(weighted_returns_perstock, axis=1)

    for x in weighted_returns:
        print(x)

    total_sum = np.sum(weighted_returns)
    print(total_sum)
    return total_sum



def generateBullPredictions(user_predictions):
    masked_bull_predictions = np.array(user_predictions, copy=True)
    masked_bull_predictions[masked_bull_predictions<0] = 0
    count_total_bull = np.count_nonzero(masked_bull_predictions, axis=1) # counts per day per stock
    standardize_bull_prediction = masked_bull_predictions / count_total_bull[:,None]
    standardize_bull_prediction[np.isnan(standardize_bull_prediction)] = 0
    return standardize_bull_prediction


def generateBearPredictions(user_predictions):
    masked_bear_predictions = np.array(user_predictions, copy=True)
    masked_bear_predictions[masked_bear_predictions>0] = 0
    count_total_bear = np.count_nonzero(masked_bear_predictions, axis=1) # counts per day per stock
    standardize_bear_prediction = masked_bear_predictions / count_total_bear[:,None]
    standardize_bear_prediction[np.isnan(standardize_bear_prediction)] = 0
    return standardize_bear_prediction



def generateRatio(bull, bear, weightBull, weightBear):
    copy_bull = np.array(bull, copy=True)
    copy_bear = np.array(bear, copy=True)

    copy_bull *= weightBull
    copy_bear *= weightBear

    for i in range(len(copy_bull)):
        for j in range(len(copy_bull[i])):
            if (abs(copy_bear[i][j]) > copy_bull[i][j]):
                temp = copy_bull[i][j]
                copy_bull[i][j] = copy_bear[i][j]
                copy_bear[i][j] = temp
            else:
                copy_bear[i][j] = abs(copy_bear[i][j])

    res = copy_bull / copy_bear
    res[res > 0] -= 1
    res[res < 0] += 1
    res[np.isnan(res)] = 0
    res[np.isinf(res)] = 1
    return res



def generateWeightedMatrix(weightings, bull_predictions, bear_predictions, user_matrice, user_stock_matrice):
    weightings = np.array(weightings)
    user_weighted_bull = np.dot(user_matrice[0], weightings[:3]) # 104 x 57000
    all_weighted_bull = np.repeat(user_weighted_bull[:,None], 48, axis=1) # 104 x 78 x 57000
    user_weighted_bear = np.dot(user_matrice[1], weightings[:3]) # 104 x 57000
    all_weighted_bear = np.repeat(user_weighted_bear[:,None], 48, axis=1) # 104 x 78 x 57000

    user_stock_weighted_bull = np.dot(user_stock_matrice[0], weightings[:3]) # 104 x 57000
    user_stock_weighted_bear = np.dot(user_stock_matrice[1], weightings[:3]) # 104 x 57000

    diagonal_weights_bull_stock = np.einsum('ijk,ikj->ij', user_stock_weighted_bull, bull_predictions, optimize=True) # 104 x 78
    diagonal_weights_bear_stock = np.einsum('ijk,ikj->ij', user_stock_weighted_bear, bear_predictions, optimize=True) # 104 x 78
    diagonal_weights_bull = np.einsum('ijk,ikj->ij', all_weighted_bull, bull_predictions, optimize=True) # 104 x 78
    diagonal_weights_bear = np.einsum('ijk,ikj->ij', all_weighted_bear, bear_predictions, optimize=True) # 104 x 78
    # count_ratio_s = generateRatio(diagonal_weights_bull_stock, diagonal_weights_bear_stock)
    # count_ratio = generateRatio(diagonal_weights_bull, diagonal_weights_bear)

    result = {
        'bull_s': diagonal_weights_bull_stock,
        'bear_s': diagonal_weights_bear_stock,
        'bull': diagonal_weights_bull,
        'bear': diagonal_weights_bear,
        # 'ratio': count_ratio,
        # 'ratio_s': count_ratio_s,
    }


    return result


def jankCalculateReturn(weightings, diagonal_weights_all, close_open_matrice):
    a = weightings['ratio_params'][0]
    b = weightings['ratio_params'][1]
    c = weightings['ratio_params'][2]
    d = weightings['ratio_params'][3]
    ratio = generateRatio(diagonal_weights_all['bull'], diagonal_weights_all['bear'], a, b)
    ratio_s = generateRatio(diagonal_weights_all['bull_s'], diagonal_weights_all['bear_s'], c, d)

    diagonal_weights_all['ratio'] = ratio
    diagonal_weights_all['ratio_s'] = ratio_s

    stocks = list(constants['top_stocks'])
    stocks.sort()
    per_stock_features = {}
    for feature in diagonal_weights_all:
        for i in range(len(diagonal_weights_all[feature])): # dates
            for j in range(len(diagonal_weights_all[feature][i])): # symbols
                weight = diagonal_weights_all[feature][i][j]
                symbol = stocks[j]
                if (symbol not in per_stock_features):
                    per_stock_features[symbol] = {}
                if (feature not in per_stock_features[symbol]):
                    per_stock_features[symbol][feature] = []
                per_stock_features[symbol][feature].append(weight)

    # Find avg/std for all stocks
    avg_std = {}
    for symbol in per_stock_features:
        features = per_stock_features[symbol]
        avg_std[symbol] = {}
        for f in features:
            # Edge case 1
            if (len(features[f]) == 1):
                res = {
                    'std': 1,
                    'avg': statistics.mean(features[f])
                }
                avg_std[symbol][f] = res
                continue
            # Edge case 2
            if (statistics.mean(features[f]) == 0):
                res = {
                    'std': 1,
                    'avg': 0
                }
                avg_std[symbol][f] = res
                continue
            res = {
                'std': statistics.stdev(features[f]),
                'avg': statistics.mean(features[f])
            }
            avg_std[symbol][f] = res

    total_return = 0
    for i in range(len(diagonal_weights_all['bull'])): # dates
        all_features_day = {}
        for j in range(len(diagonal_weights_all['bull'][i])): # symbols
            symbol = stocks[j]
            stock_avgstd = avg_std[symbol]
            stock_features_calibrated = {}
            for feature in diagonal_weights_all:
                feature_weight = diagonal_weights_all[feature][i][j]
                stdDev = (feature_weight - stock_avgstd[feature]['avg']) / stock_avgstd[feature]['std']
                stock_features_calibrated[feature] = stdDev

            # Weight each feature based on weight param
            result_weight = 0
            total_weight = 0
            for w in weightings:
                if (w == 'ratio_params'):
                    continue
                result_weight += (weightings[w] * stock_features_calibrated[w])
                total_weight += weightings[w]
            all_features_day[symbol] = result_weight / total_weight


        # Find percent of each stock to buy (pick top x)
        choose_top_n = 3
        stock_weightings = list(all_features_day.items())
        stock_weightings.sort(key=lambda x: abs(x[1]), reverse=True)
        stock_weightings = stock_weightings[:choose_top_n]
        sum_weights = reduce(lambda a, b: a + b, list(map(lambda x: abs(x[1]), stock_weightings)))

        return_today = 0
        for stock_obj in stock_weightings:
            symbol = stock_obj[0]
            weighting = stock_obj[1]
            index_symbol = list(stocks).index(symbol)
            close_open = close_open_matrice[i][index_symbol]
            percent_today = (weighting / sum_weights)
            return_today += (percent_today * close_open)

        total_return += return_today

    return total_return


# def optimizeFN(params, bull_predictions, bear_predictions, user_matrice, close_open_matrice, user_stock_matrice):
#     (diagonal_weights_bull_stock, diagonal_weights_bear_stock, diagonal_weights_bull, diagonal_weights_bear) = generateWeightedMatrix(params, bull_predictions, bear_predictions, user_matrice, user_stock_matrice)
#     result = jankCalculateReturn([2, 0.2, 1, 3], diagonal_weights_bull_stock, diagonal_weights_bear_stock, diagonal_weights_bull, diagonal_weights_bear, close_open_matrice)
#     param_res = list(map(lambda x: round(x, 2), params))
#     print(param_res, result)
#     return -result



def optimizeFN(params, diagonal_weights, close_open_matrice):

    weightings = {
        'ratio': params[0],
        'ratio_s': params[1],
        # 'bull_ratio': params[2],
        # 'bull_ratio_s': params[3],
        # 'bear_ratio': params[4],
        # 'bear_ratio_s': params[5],
        'bull': params[2],
        'ratio_params': [params[3], params[4], params[5], params[6]]
        # 'bull_s': params[3],
        # 'bear': params[4],
        # 'bear_s': params[5],
    }

    result = jankCalculateReturn(weightings, diagonal_weights, close_open_matrice)
    param_res = list(map(lambda x: round(x, 2), params))
    print(param_res, result)
    return -result



def optimize(start_date, end_date, user_predictions, user_matrice, user_stock_matrice, close_open_matrice):
    bull_predictions = generateBullPredictions(user_predictions)
    bear_predictions = generateBearPredictions(user_predictions)

    # weightings = [1, 3, 1]
    # (diagonal_weights_bull_stock, diagonal_weights_bear_stock, diagonal_weights_bull, diagonal_weights_bear) = generateWeightedMatrix(weightings, bull_predictions, bear_predictions, user_matrice, user_stock_matrice)

    diagonal_weights = generateWeightedMatrix([1, 1, 3], bull_predictions, bear_predictions, user_matrice, user_stock_matrice)

    initial_values = [2, 4, 3, 5, 7, 10, 3]
    bounds = [(0, 20), (0, 20), (0, 20), (0, 20), (0, 20), (0, 20), (0, 20)]
    result = minimize(optimizeFN,
                    initial_values,
                    method='SLSQP', 
                    options={'maxiter': 30, 'eps': 1}, 
                    args=(diagonal_weights, close_open_matrice),
                    bounds=(bounds[0],bounds[1],bounds[2],bounds[3],bounds[4],bounds[5],bounds[6]))
    print(result)



def makePrediction(start_date, end_date):
    print(findUserList()[:20])
    # np.seterr(divide='ignore', invalid='ignore')
    # weightings = np.array([1, 1, 1]) 
    # top_stocks = list(constants['top_stocks'])
    # top_stocks.sort()

    # dates = findTradingDays(datetime.datetime(2020, 1, 9), datetime.datetime(2020, 6, 9))
    # new_dates = findTradingDays(start_date, end_date)
    # diff = len(new_dates) - len(dates)

    # # extend current user matrices
    # user_matrice = np.load('user_matrice_filtered.npy') # 104 days x 57000 users x 3 weightings
    # last = np.repeat([user_matrice[-1]],repeats=diff ,axis=0)
    # user_matrice = np.vstack([user_matrice, last])

    # user_predictions = generateStockPredictions(start_date, end_date, True) # 104 days x 57000 users x 78 stocks

    # Match dimensions of user_stock matrics by converting 
    # d(days) x u(users) => d(days) x s(stocks) x u(users)
    # user_weighted = np.dot(user_matrice, weightings) # 104 x 57000
    # repeated_user_weights = np.repeat(user_weighted[:,None], len(top_stocks), axis=1) # 104 x 78 x 57000

    # # Calculate user stock weights
    # user_stock_weighted = np.dot(user_stock_matrice, weightings) # 104 x 78 x 57000

    # # Add user and user-stock weightings together
    # total_user_weight = repeated_user_weights  # 114 x 78 x 57000
    # print(total_user_weight.shape)