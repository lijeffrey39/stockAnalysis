import statistics
import math
import copy
import datetime
from functools import reduce
from .hyperparameters import constants
from .helpers import (findAllDays, readPickleObject, findTradingDays, writePickleObject)
from .stockPriceAPI import (findCloseOpenCached, exportCloseOpen, isTradingDay)
from .newPrediction import (writeTweets, saveUserTweets, pregenerateAllUserFeatures, 
                        stockFeatures, findTweets)


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
    def __init__(self, size):
        self.circular_buffer = CircularBuffer(size)
        self.mean = 0
        self.d_squared = 0

    def update(self, value):
        popped_value = self.circular_buffer.append(value)
        if (self.circular_buffer.length() == 1 and popped_value == None): # First value
            self.mean = value
        elif (popped_value == None): # Not full yet
            mean_increment = (value - self.mean) / self.circular_buffer.length()
            new_mean = self.mean + mean_increment

            d_squared_increment = (value - new_mean) * (value - self.mean)
            new_d_squared = self.d_squared + d_squared_increment
            
            self.mean = new_mean
            self.d_squared = new_d_squared
        else: # It's full
            mean_increment = (value - popped_value) / self.circular_buffer.length()
            new_mean = self.mean + mean_increment

            d_squared_increment = (value - popped_value) * (value - self.mean + popped_value - new_mean)
            new_d_squared = self.d_squared + d_squared_increment

            self.mean = new_mean
            self.d_squared = new_d_squared

    def getMean(self):
        return self.mean
    
    def variance(self):
        if (self.circular_buffer.length() > 1):
            return self.d_squared / (self.circular_buffer.length() - 1)
        return 1

    def getStddev(self):
        return math.sqrt(self.variance())




def userWeight(user_values, feature_avg_std, weightings):
    num_tweets = user_values['num_tweets']

    # (1) Scale Tweet Number
    max_value = feature_avg_std['num_tweets']['avg'] + (3 * feature_avg_std['num_tweets']['std'])
    scaled_num_tweets = (num_tweets) / math.log10(max_value)
    scaled_num_tweets = (scaled_num_tweets / 1.5) + 0.33

    if (scaled_num_tweets > 1):
        scaled_num_tweets = 1

    # (2) Scale user returns
    return_unique = user_values['return_unique']
    return_unique_s = user_values['return_unique_s']

    max_value = feature_avg_std['return_unique']['avg'] + (3 * feature_avg_std['return_unique']['std'])
    scaled_return_unique = (math.log10(return_unique - 19)) / math.log10(max_value)
    scaled_return_unique = (scaled_return_unique / 1.5) + 0.33
    
    max_value = feature_avg_std['return_unique_s']['avg'] + (3 * feature_avg_std['return_unique_s']['std'])
    scaled_return_unique_s = (math.log10(return_unique_s - 4)) / math.log10(max_value)
    scaled_return_unique_s = (scaled_return_unique_s / 1.5) + 0.33

    if (scaled_return_unique > 1):
        scaled_return_unique = 1
    if (scaled_return_unique_s > 1):
        scaled_return_unique_s = 1

    # (3) all features combined (scale accuracy from 0.5 - 1 to between 0.7 - 1.2)
    accuracy_unique = user_values['accuracy_unique'] + 0.3
    all_features = accuracy_unique * scaled_num_tweets * scaled_return_unique
    # return (scaled_return_unique + (2 * scaled_num_tweets) + (1 * scaled_return_unique_s) + (2 * all_features)) / 5
    return (weightings[0] * scaled_return_unique + (weightings[1] * scaled_num_tweets) + 
        (weightings[2] * scaled_return_unique_s) + (weightings[3] * all_features) + 
        (weightings[4] * accuracy_unique)) / sum(weightings)



def sigmoidFn(date):
    day_increment = datetime.timedelta(days=1)
    start_date = date
    end_date = start_date - day_increment

    # 4pm cutoff
    cutoff = datetime.datetime(date.year, date.month, date.day, 16)
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
    x = difference / total_seconds

    new_difference = difference - total_seconds # set difference from 0 to be all negative
    new_difference = new_difference + (60 * 60 * 5) # add 4 hours to the time...any time > 0 has y value > 0.5
    new_x = new_difference / total_seconds
    new_x *= 20

    return 1 / (1 + math.exp(-new_x))


def findStockStd(symbol, stock_features, weightings, param):
    days_back = 7
    bull_weight = 1
    bear_weight = 1
    avg_std_historical = {}
    result = {}

    avg_std_historical = SlidingWindowCalc(days_back)

    for date_str in stock_features:
        day_features = stock_features[date_str]
        weightings_avgstd = day_features['avg_std'] # TODO: Calculate stock avg_std on the spot based on history used for user weighitng
        # bull_count = day_features['bull_count']
        # bear_count = day_features['bear_count']

        bull_w = 0
        bear_w = 0
        for username in day_features:
            if (username == 'avg_std' or username == 'bull_count' or username == 'bear_count'):
                continue

            user_w = userWeight(day_features[username], weightings_avgstd, weightings)
            # tweet_w = day_features[username]['w']
            tweet_w = sigmoidFn(day_features[username]['times'][0])
            # for time in day_features[username]['times']:
            #     tweet_w += sigmoidFn(time)
            if (day_features[username]['prediction']):
                bull_w += (user_w * tweet_w)
            else:
                bear_w += (user_w * tweet_w)

            # print(date_str, username, day_features[username]['prediction'], round(day_features[username]['accuracy_unique'], 2),
            #     round(day_features[username]['accuracy_unique_s'], 2), round(day_features[username]['return_unique'], 2),
            #     round(day_features[username]['return_unique_s'], 2), day_features[username]['times'][0], user_w)

        total_w = (bull_weight * bull_w) - (bear_weight * bear_w)
        if (total_w == 0):
            continue

        avg_std_historical.update(total_w)
        feature_avg_std = {}
        feature_avg_std['total_w'] = {}
        feature_avg_std['total_w']['val'] = total_w
        feature_avg_std['total_w']['avg'] = avg_std_historical.getMean()
        feature_avg_std['total_w']['std'] = avg_std_historical.getStddev()

        result[date_str] = feature_avg_std
    return result



# Find features of tweets per day of each stock
def findAllStockFeatures(start_date, end_date, all_user_features, update=False):
    path = 'newPickled/preprocessed_stock_user_features.pickle'
    if (update == False):
        return readPickleObject(path)

    all_stocks = list(constants['top_stocks'])
    trading_dates = findTradingDays(start_date, end_date)
    all_stock_tweets = {} # store tweets locally for each stock
    feature_stats = {} # Avg/Std for features perstock
    preprocessed_features = {}

    for date in trading_dates:
        date_str = date.strftime("%Y-%m-%d")
        found = 0 # Number of stocks with enough tweets
        for symbol in all_stocks:
            tweets_per_stock = {}
            # print(symbol)
            if (symbol not in all_stock_tweets):
                stock_path = 'stock_files/' + symbol + '.pkl'
                tweets_per_stock = readPickleObject(stock_path)
                all_stock_tweets[symbol] = tweets_per_stock
            else:
                tweets_per_stock = all_stock_tweets[symbol]
            tweets = findTweets(date, tweets_per_stock, symbol) # Find tweets used for predicting for this date

            # ignore all stock with less than 200 tweets
            if (len(tweets) < 20):
                continue
            found += 1
            stockFeatures(tweets, date_str, symbol, all_user_features, feature_stats, preprocessed_features)
        print(date_str, 'Found:', found)

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
            print(date_str, print_result[:top_n_stocks])
        
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



def makePrediction(preprocessed_user_features, stock_close_opens, weightings, param, print_info):
    all_stocks = constants['top_stocks']
    picked_stocks = {}
    top_n_stocks = 3
    non_close_open = {}

    all_stocks=['SPCE']
    # Find each stocks std per day
    for symbol in all_stocks:
        if (symbol not in preprocessed_user_features):
            continue

        stock_features = preprocessed_user_features[symbol]
        stock_std = findStockStd(symbol, stock_features, weightings, param)

        for date_str in stock_std: # For each day, look at deviation and close open for the day
            date_real = datetime.datetime.strptime(date_str, '%Y-%m-%d')
            stock_day_std = stock_std[date_str]
            deviation = (stock_day_std['total_w']['val'] - stock_day_std['total_w']['avg']) / stock_day_std['total_w']['std']

            if (date_str not in non_close_open):
                non_close_open[date_str] = []
            non_close_open[date_str].append([symbol, deviation, round(stock_day_std['total_w']['val'] , 2)])

            close_open = findCloseOpenCached(symbol, date_real, stock_close_opens)
            if (close_open == None):
                continue

            # print(symbol, date_str, round(stock_day_std['total_w']['val'] , 2), round(deviation, 2), round(close_open[2], 2))
            if (deviation > 1.9 or deviation < -2.1):
                if (date_str not in picked_stocks):
                    picked_stocks[date_str] = []
                picked_stocks[date_str].append([symbol, deviation, close_open[2]])
                # print(symbol, date_str, round(stock_day_std['total_w']['val'] , 2), deviation, close_open[2])


    (accuracy_overall, accuracy_top) = calculateAccuracy(picked_stocks, top_n_stocks, print_info)
    (returns_overall, returns_top) = calculateReturns(picked_stocks, top_n_stocks, False)

    overall = accuracy_overall[0] / accuracy_overall[1]
    top = accuracy_top[0] / accuracy_top[1]

    if (print_info):
        print(accuracy_overall, accuracy_top)
        print(returns_overall, returns_top)

        for date_str in sorted(non_close_open.keys()):
            res = sorted(non_close_open[date_str], key=lambda x: x[1], reverse=True)
            res = list(map(lambda x: [x[0], round(x[1], 2), x[2]], res))
            print(date_str, res[:6])

    return (round(overall, 4), round(top, 4))



def predictionV3():

    start_date = datetime.datetime(2019, 12, 1) # Prediction start date
    end_date = datetime.datetime(2020, 7, 8) # Prediction end date

    # STEP 1: Fetch all user tweets
    # saveUserTweets()

    # STEP 2: Calculate and save individual user features
    user_features = pregenerateAllUserFeatures(update=False)

    # STEP 3: Fetch all stock tweets
    # writeAllTweets(start_date, end_date)

    # STEP 4: Fetch all stock close opens
    close_opens = exportCloseOpen(update=False)

    # STEP 5: Calculate stock features per day
    preprocessed_user_features = findAllStockFeatures(start_date, end_date, user_features, update=False)

    # STEP 6: Make prediction
    weightings = [1,1,1,1,1]
    (overall, top) = makePrediction(preprocessed_user_features, close_opens, weightings, 1, print_info=True)
    print(overall, top)

    # res = []
    # for i in range(0, 3):
    #     for j in range(1, 3):
    #         for k in range(0, 2):
    #             for l in range(0, 2):
    #                 for m in range(0, 3):
    #                     weightings = [i, j, k, l, m]
    #                     (overall, top) = makePrediction(preprocessed_user_features, close_opens, weightings, print_info=False)
    #                     print(weightings, overall, top)
    #                     res.append([weightings, overall, top])
    # res.sort(key=lambda x: x[1])
    # for x in res:
    #     print(x)

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

    symbols = ['ROKU']
    all_counts = {}
    for date in all_dates:
        date_string = date.strftime("%Y%m%d")
        stocks = result[date_string]
        filtered = list(filter(lambda x: x['_id'] in symbols, stocks))
        stocks.sort(key=lambda x: x['count'], reverse=True)
        mapped = list(map(lambda x: x['_id'], stocks))
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
    for x in result[:100]:
        print(x)

    print(list(map(lambda x: x[0], result[:100])))