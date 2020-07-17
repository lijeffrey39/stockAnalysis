import statistics
import math
import copy
import datetime
from functools import reduce
from scipy.optimize import minimize
from .hyperparameters import constants
from .helpers import (findAllDays, readPickleObject, findTradingDays, writePickleObject)
from .stockPriceAPI import (findCloseOpenCached, exportCloseOpen, isTradingDay)
from .newPrediction import (writeTweets, saveUserTweets, pregenerateAllUserFeatures, 
                        stockFeatures, findTweets, fetchTweets)
from .stockAnalysis import getTopStockDailyCached


# Used to store a circular buffer for sliding window mean/stdev
class CircularBuffer:
    def __init__(self, size):
        self.size = size
        self.index = 0
        self.buffer = [0] * size
        self.found = 0
    
    def append(self, value):
        popped_value = None
        if (self.found == self.size):
            popped_value = self.buffer[self.index]
        else:
            self.found += 1
        self.buffer[self.index] = value
        self.index = (self.index + 1) % self.size

        return popped_value

    def length(self):
        return self.found


class SlidingWindowCalc:
    def __init__(self, size, features):
        self.all_buffers = {}
        for f in features:
            self.all_buffers[f] = {}
            self.all_buffers[f]['buffer'] = CircularBuffer(size)
            self.all_buffers[f]['mean'] = 0
            self.all_buffers[f]['d_squared'] = 0

    def update(self, feature, value):
        popped_value = self.all_buffers[feature]['buffer'].append(value)

        old_mean = self.all_buffers[feature]['mean']
        old_dsquared = self.all_buffers[feature]['d_squared']
        buffer_length = self.all_buffers[feature]['buffer'].length()

        if (buffer_length == 1 and popped_value == None): # First value
            self.all_buffers[feature]['mean'] = value
        elif (popped_value == None): # Not full yet
            mean_increment = (value - old_mean) / buffer_length
            new_mean = old_mean + mean_increment

            d_squared_increment = (value - new_mean) * (value - old_mean)
            new_d_squared = old_dsquared + d_squared_increment
            if (new_d_squared < 0):
                new_d_squared = 0

            self.all_buffers[feature]['mean'] = new_mean
            self.all_buffers[feature]['d_squared'] = new_d_squared
        else: # It's full
            mean_increment = (value - popped_value) / buffer_length
            new_mean = old_mean + mean_increment

            d_squared_increment = (value - popped_value) * (value - old_mean + popped_value - new_mean)
            new_d_squared = old_dsquared + d_squared_increment
            if (new_d_squared < 0):
                new_d_squared = 0

            self.all_buffers[feature]['mean'] = new_mean
            self.all_buffers[feature]['d_squared'] = new_d_squared

    def getMean(self, feature):
        return self.all_buffers[feature]['mean']
    
    def variance(self, feature):
        if (self.all_buffers[feature]['buffer'].length() > 1):
            return self.all_buffers[feature]['d_squared'] / (self.all_buffers[feature]['buffer'].length() - 1)
        return 1

    def getStddev(self, feature):
        return math.sqrt(self.variance(feature))




def userWeight(user_values, feature_avg_std, weightings, params):
    num_tweets = user_values['num_tweets']
    num_tweets_s = user_values['num_tweets_s']

    # (1) Scale Tweet Number
    max_value = feature_avg_std['num_tweets'][ 'avg'] + (3 * feature_avg_std['num_tweets']['std'])
    scaled_num_tweets = (num_tweets) / math.log10(max_value)
    scaled_num_tweets = (scaled_num_tweets / 1.5) + 0.33

    if (scaled_num_tweets > 1):
        scaled_num_tweets = 1

    max_value = feature_avg_std['num_tweets_s'][ 'avg'] + (3 * feature_avg_std['num_tweets_s']['std'])
    scaled_num_tweets_s = (num_tweets_s) / math.log10(max_value)
    scaled_num_tweets_s = (scaled_num_tweets_s / 1.5) + 0.33

    if (scaled_num_tweets_s > 1):
        scaled_num_tweets_s = 1

    # (2) Scale user returns
    return_unique = user_values['return_unique']
    return_unique_w1 = user_values['return_unique_w1']
    return_unique_s = user_values['return_unique_s']

    max_value = feature_avg_std['return_unique']['avg'] + (3 * feature_avg_std['return_unique']['std'])
    scaled_return_unique = (math.log10(return_unique)) / math.log10(max_value)
    scaled_return_unique = (scaled_return_unique / 1.5) + 0.33

    max_value = feature_avg_std['return_unique_w1']['avg'] + (3 * feature_avg_std['return_unique_w1']['std'])
    scaled_return_unique_label = 0
    if (return_unique_w1 > 1 and max_value > 1):
        scaled_return_unique_label = (math.log10(return_unique_w1)) / math.log10(max_value)
        scaled_return_unique_label = (scaled_return_unique_label / 1.5) + 0.33

    max_value = feature_avg_std['return_unique_s']['avg'] + (3 * feature_avg_std['return_unique_s']['std'])
    scaled_return_unique_s = (math.log10(return_unique_s - 4)) / math.log10(max_value)
    scaled_return_unique_s = (scaled_return_unique_s / 1.5) + 0.33

    if (scaled_return_unique > 1):
        scaled_return_unique = 1
    if (scaled_return_unique_s > 1):
        scaled_return_unique_s = 1

    # (3) all features combined (scale accuracy from 0.5 - 1 to between 0.7 - 1.2)
    accuracy_unique = user_values['accuracy_unique']
    accuracy_unique_s = user_values['accuracy_unique_s']
    all_features = accuracy_unique * scaled_num_tweets * scaled_return_unique
    all_features_s = accuracy_unique_s * scaled_num_tweets_s * scaled_return_unique_s

    return ((weightings[0] * scaled_return_unique) + (weightings[1] * accuracy_unique) + 
        (weightings[2] * accuracy_unique_s) + (weightings[3] * scaled_return_unique_s) + 
        (weightings[4] * scaled_return_unique_label) + (weightings[5] * all_features) + (weightings[6] * all_features_s)) / sum(weightings)



def sigmoidFn(date, mode, params):
    day_increment = datetime.timedelta(days=1)
    start_date = date
    end_date = start_date - day_increment

    # 4pm cutoff
    cutoff = datetime.datetime(date.year, date.month, date.day, 16)
    if (mode == 3):
        cutoff = datetime.datetime(date.year, date.month, date.day, 9, 30)
    if (start_date > cutoff or isTradingDay(start_date) == False):
        end_date = start_date
        start_date += day_increment
        while (isTradingDay(start_date) == False):
            start_date += day_increment

    while (isTradingDay(end_date) == False):
        end_date -= day_increment

    start_date = datetime.datetime(start_date.year, start_date.month, start_date.day, 16)
    end_date = datetime.datetime(end_date.year, end_date.month, end_date.day, 16)
    difference = (date - end_date).total_seconds()
    total_seconds = (start_date - end_date).total_seconds()

    new_difference = difference - total_seconds # set difference from 0 to be all negative
    new_difference = new_difference + (60 * 60 * 5.2) # add 4 hours to the time...any time > 0 has y value > 0.5
    new_x = new_difference / total_seconds
    new_x *= 23

    return 1 / (1 + math.exp(-new_x))


def findStockStd(symbol, stock_features, weightings, mode, params):
    days_back = 8 # Days to look back for generated daily stock features
    bull_weight = 1
    bear_weight = 5

    features = ['accuracy_unique', 'accuracy_unique_s', 'num_tweets', 'num_tweets_s', 
        'return_unique', 'return_unique_s', 'return_unique_log', 
        'return_unique_log_s', 'return_unique_w1']
    feature_avgstd = SlidingWindowCalc(14, features)

    result_features = ['total_w']
    result_feature_avgstd = SlidingWindowCalc(days_back, result_features)
    result = {}

    # tweet_count = SlidingWindowCalc(param1, ['tweet_count'])

    # Look at each day's experts for this stock
    for date_str in stock_features:
        day_features = stock_features[date_str] # Users that tweeted that day
        bull_count = 0
        bear_count = 0

        # Update stock's user feature avg and std
        for username in day_features:
            user_features = day_features[username]
            if (user_features['return_unique'] < 20 or 
                user_features['return_unique_s'] < 5 or 
                user_features['num_tweets'] <= 52 or 
                user_features['num_tweets_s'] < 12):
                continue
            for feature in features:
                if (feature == 'times' or feature == 'prediction'):
                    continue
                feature_avgstd.update(feature, user_features[feature])

            if (day_features[username]['prediction']):
                bull_count += 1
            else:
                bear_count += 1

        # Calculate each feature's avg and std
        weightings_avgstd = {}
        for feature in features:
            weightings_avgstd[feature] = {}
            weightings_avgstd[feature]['avg'] = feature_avgstd.getMean(feature)
            weightings_avgstd[feature]['std'] = feature_avgstd.getStddev(feature)

        bull_w = 0
        bear_w = 0
        tweet_total_w = 0
        for username in day_features:
            if (day_features[username]['return_unique'] < 20 or
                day_features[username]['return_unique_s'] < 5 or 
                day_features[username]['num_tweets'] <= 52 or 
                day_features[username]['num_tweets_s'] < 12):
                continue

            user_w = userWeight(day_features[username], weightings_avgstd, weightings, params)
            tweet_w = sigmoidFn(day_features[username]['times'][0], mode, params) # Most recent posted time
            tweet_total_w += tweet_w
            # for time in day_features[username]['times']:
            #     tweet_w += sigmoidFn(time)
            if (day_features[username]['prediction']):
                bull_w += (user_w * tweet_w)
            else:
                bear_w += (user_w * tweet_w)

            # if (symbol == 'AMD' or symbol == 'DIS' or symbol == 'MSFT'):
            #     print(symbol, date_str, day_features[username]['times'][0], username, day_features[username]['prediction'], 
            #         round(day_features[username]['accuracy_unique'], 2), round(day_features[username]['accuracy_unique_s'], 2), 
            #         round(day_features[username]['return_unique'], 2), round(day_features[username]['return_unique_s'], 2), 
            #         round(user_w, 2), round(tweet_w, 2))

        total_w = (bull_weight * bull_w) - (bear_weight * bear_w)

        result_feature_avgstd.update('total_w', total_w)
        feature_avg_std = {}
        feature_avg_std['total_w'] = {}
        feature_avg_std['total_w']['val'] = total_w
        feature_avg_std['total_w']['avg'] = result_feature_avgstd.getMean('total_w')
        feature_avg_std['total_w']['std'] = result_feature_avgstd.getStddev('total_w')

        feature_avg_std['bull_count'] = bull_count
        feature_avg_std['bear_count'] = bear_count
        feature_avg_std['total_tweet_w'] = tweet_total_w

        result[date_str] = feature_avg_std

    return result


# Find features of tweets per day of each stock
def findAllStockFeatures(start_date, end_date, all_user_features, path, update=False, mode=1):
    if (update == False):
        return readPickleObject(path)

    daily_object = readPickleObject('newPickled/daily_stocks_cached.pickle')
    trading_dates = findTradingDays(start_date, end_date)
    all_stock_tweets = {} # store tweets locally for each stock
    feature_stats = {} # Avg/Std for features perstock
    preprocessed_features = {}

    for date in trading_dates:
        date_str = date.strftime("%Y-%m-%d")
        print(date_str)
        stocks = getTopStockDailyCached(date, 80, daily_object)
        for symbol in stocks:
            tweets_per_stock = {}
            if (symbol not in all_stock_tweets):
                stock_path = 'stock_files/' + symbol + '.pkl'
                tweets_per_stock = readPickleObject(stock_path)
                all_stock_tweets[symbol] = tweets_per_stock
            else:
                tweets_per_stock = all_stock_tweets[symbol]
            tweets = findTweets(date, tweets_per_stock, symbol, mode) # Find tweets used for predicting for this date

            if (symbol not in preprocessed_features):
                preprocessed_features[symbol] = {}
            preprocessed_features[symbol][date_str] = {}
            stockFeatures(tweets, date_str, symbol, all_user_features, feature_stats, preprocessed_features)


    writePickleObject(path, preprocessed_features)
    return preprocessed_features


def calculateAccuracy(picked_stocks, top_n_stocks, print_info):
    correct_overall = 0 # Overall accuracy
    total_overall = 0
    correct_top = 0 # Top n stocks accuracy
    total_top = 0

    for date_str in sorted(picked_stocks.keys()):
        stock_list = sorted(picked_stocks[date_str], key=lambda x: abs(x[1]), reverse=True)
        n_stocks = 0
        for x in stock_list:
            total_overall += 1
            n_stocks += 1
            if ((x[1] > 0 and x[2] > 0) or (x[1] < 0 and x[2] < 0)):
                correct_overall += 1

            # If viewed less than n stocks, keep adding
            if (n_stocks <= top_n_stocks):
                if ((x[1] > 0 and x[2] > 0) or (x[1] < 0 and x[2] < 0)):
                    correct_top += 1
                total_top += 1

        if (print_info):
            print_result = list(map(lambda x: [x[0], round(x[1], 2), round(x[2], 2)], stock_list))
            print(date_str, print_result[:top_n_stocks], len(print_result))

    return ([correct_overall, total_overall], [correct_top, total_top])


def calculateReturns(picked_stocks, top_n_stocks, print_info):
    correct_sum = 0
    total_sum = 0

    return_overall = 0
    return_top = 0

    for date_str in sorted(picked_stocks.keys()):
        stock_list = sorted(picked_stocks[date_str], key=lambda x: abs(x[1]), reverse=True)
        sum_weights = reduce(lambda a, b: a + b, list(map(lambda x: abs(x[1]), stock_list)))
        return_today = 0
        n_stocks = 0
        for stock_obj in stock_list:
            symbol = stock_obj[0]
            weighting = stock_obj[1]
            percent_change = stock_obj[2]
            percent_weight = (weighting / sum_weights)
            returns = (percent_weight * percent_change)
            return_overall += returns
            n_stocks += 1
            if (n_stocks <= top_n_stocks):
                return_top += returns

        if (return_today >= 0):
            correct_sum += 1
        total_sum += 1

        if (print_info):
            print(date_str, round(return_today, 3), stock_list[:top_n_stocks])

    return (return_overall, return_top)



def makePrediction(preprocessed_user_features, stock_close_opens, weightings, params, print_info, mode=1):
    picked_stocks = {}
    top_n_stocks = 3
    non_close_open = {}

    # Find each stocks std per day
    for symbol in constants['good_stocks']:
        if (symbol not in preprocessed_user_features):
            continue

        stock_features = preprocessed_user_features[symbol]
        stock_std = findStockStd(symbol, stock_features, weightings, mode, params)

        for date_str in stock_std: # For each day, look at deviation and close open for the day
            date_real = datetime.datetime.strptime(date_str, '%Y-%m-%d')
            stock_day_std = stock_std[date_str]
            if (stock_day_std['total_w']['std'] == 0 or stock_day_std['total_tweet_w'] <= 3.3):
                continue
            deviation = (stock_day_std['total_w']['val'] - stock_day_std['total_w']['avg']) / stock_day_std['total_w']['std']

            if (date_str not in non_close_open):
                non_close_open[date_str] = []
            non_close_open[date_str].append([symbol, deviation, stock_day_std['bull_count'], stock_day_std['bear_count']])

            close_open = findCloseOpenCached(symbol, date_real, stock_close_opens, mode)
            if (close_open == None):
                continue

            # print(symbol, date_str, round(stock_day_std['total_w']['val'] , 2), round(deviation, 2), round(close_open[2], 2))
            if (deviation > 1.82 or deviation < -2.3):
                if (date_str not in picked_stocks):
                    picked_stocks[date_str] = []
                picked_stocks[date_str].append([symbol, deviation, close_open[2]])
                # print(symbol, date_str, round(stock_day_std['total_w']['val'] , 2), deviation, close_open[2])

    (accuracy_overall, accuracy_top) = calculateAccuracy(picked_stocks, top_n_stocks, print_info)
    (returns_overall, returns_top) = calculateReturns(picked_stocks, top_n_stocks, False)

    overall = accuracy_overall[0] / (accuracy_overall[1] or not accuracy_overall[1])
    top = accuracy_top[0] / (accuracy_top[1] or not accuracy_top[1])

    if (print_info):
        print(accuracy_overall, accuracy_top)
        print(returns_overall, returns_top)

        for date_str in sorted(non_close_open.keys()):
            res = sorted(non_close_open[date_str], key=lambda x: x[1], reverse=True)
            res = list(map(lambda x: [x[0], round(x[1], 2), x[2], x[3]], res))
            print(date_str, res[:6])

    return (round(overall, 4), round(top, 4), accuracy_overall, accuracy_top, returns_overall)


def saveLocalTweets(start_date, end_date):
    all_dates = findAllDays(start_date, end_date)
    for date in all_dates:
        daily_object = readPickleObject('newPickled/daily_stocks_cached.pickle')
        stocks = getTopStockDailyCached(date, 80, daily_object)
        print(date)
        for symbol in stocks:
            writeTweets(date, date, symbol, True)



def newDailyPrediction(date):
    end_date = date
    start_date = end_date - datetime.timedelta(days=80)
    mode = 1

    # Re-save tweets to local
    saveLocalTweets(date, date)

    # Use pregenerated user features
    user_features = pregenerateAllUserFeatures(update=False, path='newPickled/user_features.pickle')

    # Fetch stock features per day
    path = 'newPickled/preprocessed_daily_user_features.pickle'
    preprocessed_user_features = findAllStockFeatures(start_date, end_date, user_features, path, update=True)
    weightings = [0.5, 1.5, 1, 3, 0.4, 1.3, 0.9]
    non_close_open = {}
    params=[]

    # Find each stocks std per day
    for symbol in constants['good_stocks']:
        if (symbol not in preprocessed_user_features):
            continue

        stock_features = preprocessed_user_features[symbol]
        stock_std = findStockStd(symbol, stock_features, weightings, mode, params)

        for date_str in stock_std: # For each day, look at deviation and close open for the day
            stock_day_std = stock_std[date_str]
            if (stock_day_std['total_w']['std'] == 0 or stock_day_std['total_tweet_w'] <= 3.1):
                continue
            deviation = (stock_day_std['total_w']['val'] - stock_day_std['total_w']['avg']) / stock_day_std['total_w']['std']

            if (date_str not in non_close_open):
                non_close_open[date_str] = {}

            non_close_open[date_str][symbol] = [symbol, round(deviation, 2), round(stock_day_std['total_w']['val'], 2), stock_day_std['bull_count'], stock_day_std['bear_count']]

    # Sort by std
    for date_str in non_close_open:
        symbols = list(non_close_open[date_str].keys())
        non_close_open[date_str]['stocks_found'] = sorted(symbols, key=lambda symbol: non_close_open[date_str][symbol][1], reverse=True)

    # Display past info about the top stocks
    current_date_str = date.strftime("%Y-%m-%d")
    stocks_today = non_close_open[current_date_str]['stocks_found'][:12] # Top 6 for the day
    result_details = {}
    for symbol in stocks_today:
        for date_str in non_close_open:
            if (date_str not in result_details):
                result_details[date_str] = []
            if (symbol not in non_close_open[date_str]):
                result_details[date_str].append([symbol, 0, 0, 0, 0])
                continue
            vals = non_close_open[date_str][symbol]
            result_details[date_str].append(vals)

    for date_str in sorted(result_details.keys()):
        print(date_str, result_details[date_str])

    print(stocks_today)


"""
                              -- Prediction Algo (v3) --
    Based on "expert" user predictions per day, pick stocks that have the highest rating
    by these selected users. Stocks each day are ranked based on deviation of ratings from previous
    trading days to now. Ratings per stock, per day are calculated based on linear combination of
    "expert" user predictions. Users are differentiated and ranked based on historical prediction
    accuracy, return, etc. Certain thresholds must be met such as total tweet weight and deviation
    per stock per day.

    Steps required to setup project for prediction
    1. Saving all user tweets to disk (Must have min of 20 tweets to be saved)
    2. Generate user features based on each user's bull/bear tweets
        a. Features are stored on a daily changing basis so that when predicting, we only look
           at user features before a given date
        b. User features are saved in this structure:
            {
                'general': {
                    '2020-02-13': {
                        'unique_correct_predictions': {
                            'bull': 5,
                            'bear': 3
                        }
                        'unique_num_predictions': {
                            'bull': 10,
                            'bear': 2
                        } ...
                    } ...
                },
                'perStock': {
                    'AAPL': {
                        '2020-02-13': {
                            ...
                        } ...
                    } ...
                }
            }

        c. They are split up into these general and stock specific features and each have a 
           bear/bull attribute
            i.   unique_correct_predictions
            ii.  unique_num_predictions
            iii. unique_return - sum of returns made from 4:00 PM to 9:30 AM
            iv.  unique_return_log - sum of returns weighted by number of times posted that day
            v.   unique_return_w - sum of returns weighted by time of last post that day

        d. Sigmoid Function - used to determine weight (0 - 1) based on time of tweet from 4:00 PM
            i.  1 / (1 + e^-x)
            ii. Center point of function is -5.5 hours back so at point, the weight is 0.5
    3. Save all stock tweets for given dates
        a. Stocks for each day are based top 80 popular stocks from the previous day
    4. Save close open stock data
    5. Store top user features per stock per day
        1. Time of tweet
        2. Bull/bear
        3. User features NOTE: every feature has corresponding stock specific feature
            - accuracy_unique: weighted accuracy between bull/bear and total accuracy
            - num_tweets: total bull and bear tweets
            - return_unique: sum of returns (average of bull/bear)
            - return_unique_log: 
            - return_unique_w1
            - return_unique_label
    6. Prediction - 
    
    
"""

def predictionV3():
    start_date = datetime.datetime(2019, 6, 3) # Prediction start date
    end_date = datetime.datetime(2020, 7, 16) # Prediction end date
    mode = 1 # 4:00 PM to 9:30 AM next trading day

    # STEP 1: Fetch all user tweets
    # saveUserTweets()

    # STEP 2: Calculate and save individual user features
    # user_features = pregenerateAllUserFeatures(update=False, path='newPickled/user_features.pickle', mode=mode)

    # STEP 3: Fetch all stock tweets
    # writeAllTweets(start_date, end_date)

    # STEP 4: Fetch all stock close opens
    close_opens = exportCloseOpen(update=False)

    # STEP 5: Calculate stock features per day
    path = 'newPickled/preprocessed_stock_user_features.pickle'
    preprocessed_user_features = findAllStockFeatures(start_date, end_date, {}, path, update=False, mode=mode)

    # STEP 6: Make prediction
    # 6, 8, 3.1, 1.8
    weightings = [0.8, 1.7, 0.9, 2.8, 0.4, 1.3, 0.9]
    # params=[]
    # (overall, top, accuracy_overall, accuracy_top, returns) = makePrediction(preprocessed_user_features, close_opens, weightings, params, print_info=True, mode=mode)
    # print(overall, top, accuracy_overall, accuracy_top, returns)


    # 5.4 - 5.6
    # 8
    # 3.2-3.5
    # 1.8-1.84
    # res = []
    # for i in range(0, 11): # 5
    #     i = 4 + (i / 5)
    #     for j in range(7, 11): # 8
    #         for k in range(29, 36): # 3.1
    #             k = k / 10
    #             for l in range(0, 9): # 1.8
    #                 l = 1.76 + (l / 50)
    #                 params = [i, j, k, l]
    #                 (overall, top, accuracy_overall, accuracy_top, returns) = makePrediction(preprocessed_user_features, close_opens, weightings, params, print_info=False, mode=mode)
    #                 print(params, overall, top, accuracy_overall, accuracy_top, returns)
    #                 res.append([params, overall, top, returns, accuracy_overall, accuracy_top])

    # res = []
    # for i in range(45, 60): # 5
    #     i = i / 10
    #     for j in range(21, 25): # 11
    #         j = j / 10
    #         params = [i, j]
    #         (overall, top, accuracy_overall, accuracy_top, returns) = makePrediction(preprocessed_user_features, close_opens, weightings, params, print_info=False, mode=mode)
    #         if (accuracy_top[0] < 200):
    #             continue
    #         print(params, overall, top, accuracy_overall, accuracy_top, returns)
    #         res.append([params, overall, top, returns, accuracy_overall, accuracy_top])

    # res.sort(key=lambda x: x[1] + x[2])
    # for x in res:
    #     print(x)


    # weightings = [0.5, 1.5, 1, 3, 0.4, 1.3, 0.9]

    res = []
    for i in range(0, 10):
        i = i / 10
        for j in range(0, 10):
            j = 1 + (j / 10)
            for k in range(0, 10):
                k = 0.5 + (k / 10)
                weightings = [0.8, 1.7, 0.9, 2.8, i, j, k]
                (overall, top, accuracy_overall, accuracy_top, returns) = makePrediction(preprocessed_user_features, close_opens, weightings, [], print_info=False)
                if (accuracy_top[0] < 200):
                    continue
                print(weightings, overall, top, accuracy_overall, accuracy_top, returns)
                res.append([weightings, overall, top, returns, accuracy_overall, accuracy_top])

    # res.sort(key=lambda x: x[1] + x[2])
    # for x in res:
    #     print(x)

    # STEP FINAL - DAILY PREDICTION
    # dailyPrediction()


# def optimizeFN(params, user_features, close_opens, preprocessed_user_features):
#     (overall, top, accuracy_overall, accuracy_top ,returns_overall) = makePrediction(preprocessed_user_features, close_opens, params, 1, 1, print_info=False)
#     param_res = list(map(lambda x: round(x, 2), params))
#     print(param_res, returns_overall)
#     return -returns_overall



# def optimizeParamsNew():
#     params = {
#         'scaled_return_unique': [1, (0, 5)],
#         'accuracy_unique': [1, (0, 5)],
#         'accuracy_unique_s': [1, (0, 5)],
#         'scaled_return_unique_s': [3.8, (0, 6)],
#         'scaled_return_unique_label': [0.2, (0, 3)],
#         'all_features': [1.6, (0, 3)],
#         'all_features_s': [1, (0, 3)],
#     }

#     start_date = datetime.datetime(2019, 6, 3) # Prediction start date
#     end_date = datetime.datetime(2020, 7, 14) # Prediction end date
#     user_features = pregenerateAllUserFeatures(update=False)
#     close_opens = exportCloseOpen(update=False)
#     path = 'newPickled/preprocessed_stock_user_features.pickle'
#     preprocessed_user_features = findAllStockFeatures(start_date, end_date, user_features, path, update=False)

#     initial_values = list(map(lambda key: params[key][0], list(params.keys())))
#     bounds = list(map(lambda key: params[key][1], list(params.keys())))
#     result = minimize(optimizeFN, initial_values, method='SLSQP', options={'maxiter': 100, 'eps': 0.2}, 
#                     bounds=(bounds[0],bounds[1],bounds[2],bounds[3],bounds[4],bounds[5],bounds[6]),
#                     args=(user_features, close_opens, preprocessed_user_features))
#     print(result)




def writeAllTweets(start_date, end_date):
    all_stocks = constants['top_stocks']
    for symbol in all_stocks:
        writeTweets(start_date, end_date, symbol, False)



def fetchStockTweets():
    daily_count = constants['db_user_client'].get_database('user_data_db').daily_stockcount
    cursor = daily_count.find()
    result = {}
    for count_obj in cursor:
        result[count_obj['_id']] = count_obj['stocks']

    start_date = datetime.datetime(2019, 12, 1)
    end_date = datetime.datetime(2020, 7, 1)
    all_dates = findAllDays(start_date, end_date)

    # symbols = ['ROKU']
    all_counts = {}
    for date in all_dates:
        date_string = date.strftime("%Y%m%d")
        stocks = result[date_string]
        # filtered = list(filter(lambda x: x['_id'] in symbols, stocks))
        stocks.sort(key=lambda x: x['count'], reverse=True)
        # mapped = list(map(lambda x: x['_id'], stocks))
        # print(date, stocks[:3], filtered)
        # print(date, mapped[:10])

        for stock in stocks:
            if (stock['_id'] not in all_counts):
                all_counts[stock['_id']] = []

            all_counts[stock['_id']].append(stock['count'])

    result = []
    for symbol in all_counts:
        mean = statistics.mean(all_counts[symbol])
        std = 1
        if (len(all_counts[symbol]) > 1):
            std = statistics.stdev(all_counts[symbol])
        result.append([symbol, round(mean, 2), round(std, 2)])

    result.sort(key=lambda x: x[1], reverse=True)
    for x in result[:600]:
        print(x)

    print(list(map(lambda x: x[0], result[:600])))