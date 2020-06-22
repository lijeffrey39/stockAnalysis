import os
import datetime
import numpy as np
import copy
import math
from .hyperparameters import constants
from .stockAnalysis import getTopStocksforWeek
from .stockPriceAPI import (findCloseOpenCached, isTradingDay, findDateString)
from .helpers import (readPickleObject, writePickleObject, findTradingDays)
from .newPrediction import (cachedUserTweets, calculateUserFeatures, findTweets)


def pregenerateAllUserFeatures():
    arr = os.listdir('user_tweets/')
    count = 0
    result = {}
    for u in arr:
        username = u[:-4]
        pregenerated = pregenerateUserFeatures(username)
        features = list(pregenerated.keys())
        if (len(features) == 0):
            continue
        last_date = features[0]
        # for date in pregenerated:
        #     del pregenerated[date]['perStock']
        pregenerated['last_tweet_date'] = datetime.datetime.strptime(last_date, '%Y-%m-%d')
        count += 1
        if (count % 1000 == 0):
            print(count)
        result[username] = pregenerated
    writePickleObject('newPickled/user_features_stock.pkl', result)


def pregenerateUserFeatures(username):
    day_increment = datetime.timedelta(days=1)
    cached_tweets = cachedUserTweets(username)
    if (cached_tweets == None):
        return
    cached_prices = constants['cached_prices']
    top_stocks = constants['top_stocks']
    dates = []

    for tweet in cached_tweets:
        time = tweet['time']
        symbol = tweet['symbol']
        if (symbol not in top_stocks):
            continue
        if (time.hour >= 16):
            time += day_increment
        while (isTradingDay(time) == False):
            time += day_increment

        time = datetime.datetime(time.year, time.month, time.day, 16)
        if (time not in dates):
            dates.append(time)

    # Go from past to present
    dates.sort()
    buildup_result = {}
    result = {}
    for date in dates:
        day_res = calculateUserFeatures(username, date, cached_prices, buildup_result, cached_tweets)
        date += day_increment
        while (isTradingDay(date) == False):
            date += day_increment
        date_string = '%d-%02d-%02d' % (date.year, date.month, date.day)
        copied_res = copy.deepcopy(day_res)
        del copied_res['_id']
        del copied_res['last_updated']
        result[date_string] = copied_res['perStock']
        if ('AAPL' in result[date_string]):
            print(date_string, result[date_string]['AAPL'])

    return result

def findUserFeatures(username, user_features, date):
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
            return features[date_str]
    return None


def generateUserFeatureMatrix(users, user_features, date):
    result = np.zeros(shape=(len(users), 3))
    for i in range(len(users)):
        username = users[i]
        features = findUserFeatures(username, user_features, date)
        if (features == None):
            continue
        total_tweets = features['unique_num_predictions']['bull'] + features['unique_num_predictions']['bear']
        if (total_tweets == 0):
            continue
        correct_tweets = features['unique_correct_predictions']['bull'] + features['unique_correct_predictions']['bear']
        accuracy = correct_tweets / total_tweets
        return_percent = features['unique_return']['bull'] + features['unique_return']['bear']
        feature_array = [total_tweets, accuracy, return_percent]
        result[i] = feature_array
    return result


def generateUserMatrices(start_date, end_date, user_features):
    users = []
    arr = os.listdir('user_tweets/')
    for u in arr:
        username = u[:-4]
        users.append(username)
    users.sort()
    dates = findTradingDays(start_date, end_date)
    result = np.zeros(shape=(len(dates), len(users), 3))

    # For each user, fill in 3d matrix by date
    for i in range(len(dates)):
        date = dates[i]
        print(date)
        user_matrix = generateUserFeatureMatrix(users, user_features, date)
        result[i] = user_matrix
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


def generateUserStockFeatureMatrix(top_stocks, users, user_features, date):
    result = np.zeros(shape=(len(top_stocks), len(users), 3))
    for i in range(len(top_stocks)):
        symbol = top_stocks[i]
        for j in range(len(users)):
            username = users[j]
            features = findUserStockFeatures(username, symbol, user_features, date)
            if (features == None):
                continue
            total_tweets = features['unique_num_predictions']['bull'] + features['unique_num_predictions']['bear']
            if (total_tweets == 0):
                continue
            correct_tweets = features['unique_correct_predictions']['bull'] + features['unique_correct_predictions']['bear']
            accuracy = correct_tweets / total_tweets
            return_percent = features['unique_return']['bull'] + features['unique_return']['bear']
            feature_array = [total_tweets, accuracy, return_percent]
            result[i][j] = feature_array
    return result


def generateUserStockMatrices(start_date, end_date, user_features):
    top_stocks = list(constants['top_stocks'])
    top_stocks.sort()
    users = []
    arr = os.listdir('user_tweets/')
    for u in arr:
        username = u[:-4]
        users.append(username)
    users.sort()

    dates = findTradingDays(start_date, end_date)
    result = np.zeros(shape=(len(dates), len(top_stocks), len(users), 3))

    # For each user, fill in 4d matrix by date
    for i in range(len(dates)):
        date = dates[i]
        print(date)
        user_matrix = generateUserStockFeatureMatrix(top_stocks, users, user_features, date)
        result[i] = user_matrix

    np.save('user_stock_matrice.npy', result)



def findStockUserWeightings(start_date, end_date, user_matrice):
    # Scale tweet number between 0 and 1 based off of each stock's distribution
    # Look at most recent date to find individual stock distribution
    print("Standardizing Tweet Count")
    most_recent = user_matrice[-1]
    mean_std = np.ma.masked_equal(most_recent,0)

    # Sum for each stock
    summed = mean_std[:,:,0].sum(axis=1)

    # Number of non-zero user counts
    non_zero_count = np.count_nonzero(mean_std[:,:,0], axis=1)
    mean = summed / non_zero_count # avg tweet number per user
    std = np.std(mean_std[:,:,0], axis=1) # std of tweets per user

    # Use z-score to scale user from -3 - 3 => 0 - 6 => 0 - 1
    user_matrice[:,:,:,0] = (user_matrice[:,:,:,0] - mean[:,None]) / std[:,None]
    user_matrice[:,:,:,0] = np.add(user_matrice[:,:,:,0], 3)
    user_matrice[user_matrice[:,:,:,0] <= 0] = 0
    user_matrice[user_matrice[:,:,:,0] > 6] = 6
    user_matrice[:,:,:,0] = np.divide(user_matrice[:,:,:,0], 6)


    # Do the same for user returns
    # Sum of returns for each stock
    print("Standardizing Return")
    summed_return = mean_std[:,:,2].sum(axis=1)
    count_return = np.count_nonzero(mean_std[:,:,2], axis=1)
    mean_return = summed_return / count_return # avg return per stock
    std_return = np.std(mean_std[:,:,2], axis=1) # std of tweets per user

    user_matrice[:,:,:,2] = (user_matrice[:,:,:,2] - mean_return[:,None]) / std_return[:,None]
    user_matrice[:,:,:,2] = np.add(user_matrice[:,:,:,2], 3)
    user_matrice[user_matrice[:,:,:,2] <= 0] = 0
    user_matrice[user_matrice[:,:,:,2] > 6] = 6
    user_matrice[:,:,:,2] = np.divide(user_matrice[:,:,:,2], 6)


    # Remove all users that are below 30%
    print("Adjust Accuracy")
    min_accuracy = 0.3
    user_matrice[user_matrice[:,:,:,1] <= min_accuracy] = 0


    np.save('user_stock_matrice_filtered.npy', user_matrice)
    # result = np.dot(user_matrice, weightings) #100 x 79 x 50000 x 3 * 3 x 1 = 100 x 79 x 50000
    print(user_matrice.shape)


def findUserWeightings(start_date, end_date, user_matrice, weightings):
    # print(user_matrice[0][:10])
    # Remove all users that are below certain number of tweets
    # Set cap at 500 tweets
    # Standardize between 0 - 1 from 0 - 500 using sqrt function
    min_num_tweets = 20
    max_num_tweets = 500
    user_matrice[user_matrice[:,:,0] <= min_num_tweets] = 0
    user_matrice[user_matrice[:,:,0] > max_num_tweets] = max_num_tweets
    user_matrice[:,:,0] = np.power(user_matrice[:,:,0], 0.5) # sqrt tweets
    user_matrice[:,:,0] = np.divide(user_matrice[:,:,0], math.sqrt(max_num_tweets)) # divide by sqrt(500)

    # Remove all users that are below certain accuracy
    min_accuracy = 0.3
    user_matrice[user_matrice[:,:,1] <= min_accuracy] = 0

    # Remove all users that are below certain return
    # Set cap at 500% return
    min_return = 0
    max_return = 150
    user_matrice[user_matrice[:,:,2] <= min_return] = 0
    user_matrice[user_matrice[:,:,2] > max_return] = max_return
    user_matrice[:,:,2] = np.divide(user_matrice[:,:,2], max_return)

    np.save('user_matrice_filtered.npy', user_matrice)


def generateStockPredictions(start_date, end_date):
    dates = findTradingDays(start_date, end_date)
    cached_prices = constants['cached_prices']
    top_stocks = list(constants['top_stocks'])
    top_stocks.sort()

    users = []
    user_index = {}
    arr = os.listdir('user_tweets/')
    i = 0
    for u in arr:
        username = u[:-4]
        users.append(username)
        user_index[username] = i
        i += 1
    users.sort()

    all_stock_tweets = {}
    for symbol in top_stocks:
        stock_path = 'new_stock_files/' + symbol + '.pkl'
        tweets_per_stock = readPickleObject(stock_path)
        all_stock_tweets[symbol] = tweets_per_stock
    

    result = np.zeros(shape=(len(dates), len(users), len(top_stocks)))

    for i in range(len(dates)):
        date = dates[i]
        print(date)
        users_seen = set([])
        for j in range(len(top_stocks)):
            symbol = top_stocks[j]
            tweets_per_stock = all_stock_tweets[symbol]
            tweets = findTweets(date, tweets_per_stock, cached_prices, symbol)
            print(symbol, len(tweets))
            for tweet in tweets:
                username = tweet['user']
                isBull = tweet['isBull']

                if (username in users_seen or username not in user_index):
                    continue
                users_seen.add(username)
                user_i = user_index[username]
                label = 1 if isBull else -1
                result[i][user_i][j] = label

    np.save('user_predictions.npy', result)


def generateCloseOpenMatrice(start_date, end_date):
    dates = findTradingDays(start_date, end_date)
    cached_prices = constants['cached_prices']
    top_stocks = list(constants['top_stocks'])
    top_stocks.sort()

    # 100 days x 78 stocks
    result = np.zeros(shape=(len(dates), len(top_stocks)))

    for i in range(len(dates)):
        date = dates[i]
        print(date)
        # Only choose top 20 stocks for the week
        top_for_week = getTopStocksforWeek(date, 20)
        for j in range(len(top_stocks)):
            symbol = top_stocks[j]
            if (symbol not in top_for_week):
                continue
            close_open = findCloseOpenCached(symbol, date, cached_prices)
            if (close_open == None):
                print(symbol, date)
                continue
            result[i][j] = close_open[2]

    np.save('close_open_matrice.npy', result)



def findTotalUserWeightings(start_date, end_date, user_matrice, user_stock_matrice, weightings):
    top_stocks = list(constants['top_stocks'])
    top_stocks.sort()

    # Match dimensions of user_stock matrics
    user_weighted = np.dot(user_matrice, weightings) # 104 x 57000
    repeated_user_weights = np.repeat(user_weighted[:,None], len(top_stocks), axis=1) # 104 x 78 x 57000

    # Calculate user stock weights
    user_stock_weighted = np.dot(user_stock_matrice, weightings) # 104 x 78 x 57000

    total_user_weight = repeated_user_weights + user_stock_weighted # 104 x 78 x 57000

    return total_user_weight
    # print(total_user_weight.shape)


def calculateReturn(start_date, end_date):
    np.seterr(divide='ignore', invalid='ignore')
    top_stocks = list(constants['top_stocks'])
    top_stocks.sort()
    user_matrice = np.load('user_matrice_filtered.npy') # 104 days x 57000 users x 3 weightings
    user_stock_matrice = np.load('user_stock_matrice_filtered.npy') # 104 days x 78 stocks x 57000 users x 3 weightings
    user_predictions = np.load('user_predictions.npy') # 104 days x 57000 users x 78 stocks
    close_open_matrice = np.load('close_open_matrice.npy') # 104 x 78
    weightings = np.array([1, 1, 1])

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
