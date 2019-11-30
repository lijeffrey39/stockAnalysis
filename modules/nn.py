import numpy as np
import torch
import datetime
from operator import itemgetter
import time
import csv
from torch.utils.data import TensorDataset, DataLoader
import torch.nn.functional as F

from .helpers import findTradingDays
from .stockAnalysis import getTopStocks
from .hyperparameters import constants
from .stockPriceAPI import getUpdatedCloseOpen
from .userAnalysis import getAllUserInfo


def testing():
    stocks = getTopStocks(100)
    stocks = ['TSLA']
    dateStart = datetime.datetime(2019, 9, 11, 9, 30)
    dateEnd = datetime.datetime(2019, 11, 27, 16, 0)
    dates = findTradingDays(dateStart, dateEnd)

    analyzedUsersDB = constants['db_user_client'].get_database('user_data_db')
    userAccuracy = analyzedUsersDB.new_user_accuracy

    data = []
    with open('new_file.csv') as csv_file:
        csv_reader = csv.reader(csv_file, delimiter=',')
        for row in csv_reader:
            if ((int(row[0]) == 1 and float(row[24]) > 0) or
                (int(row[0]) == 0 and float(row[24]) < 0)):
                row[9] = float(row[9])
                if (row[0] == 0):
                    row[0] = -1
                else:
                    row[0] = 1
                row[24] = float(row[24]) * 5
                data.append(row)
    allData = np.array(data, dtype='float32')
    inputs = torch.from_numpy(allData[:, [9, 16, 18]])
    targets = torch.from_numpy(allData[:, 24])

    print(inputs)
    print(targets)

    w = torch.randn(1, 3, requires_grad=True)
    b = torch.randn(1, requires_grad=True)

    def model(x):
        return x @ w.t() + b

    def mse(t1, t2):
        diff = t1 - t2
        return torch.sum(diff * diff) / diff.numel()

    # Train for 100 epochs
    for i in range(20):
        preds = model(inputs)
        loss = mse(preds, targets)
        loss.backward()
        with torch.no_grad():
            w -= w.grad * 1e-5
            b -= b.grad * 1e-5
            w.grad.zero_()
            b.grad.zero_()
        print(loss)

    preds = model(inputs)
    print(inputs)
    print(preds)
    print(targets)
    return


    for s in stocks:
        for date in dates:
            dateStart = datetime.datetime(date.year,
                                        date.month, date.day, 9, 30)
            dateEnd = datetime.datetime(date.year,
                                        date.month, date.day, 16, 0)
            tweets = constants['stocktweets_client'].get_database('tweets_db').tweets.find(
                                    {"$and": [{'symbol': s},
                                    {"$or": [
                                        {'isBull': True},
                                        {'isBull': False}
                                    ]},
                                    {'time': {'$gte': dateStart,
                                    '$lt': dateEnd}}]})
            tweets = list(tweets)
            closeOpen = getUpdatedCloseOpen(s, date)
            if (closeOpen is None):
                continue

            count = 0
            data = []
            for tweet in tweets:
                user = tweet['user']
                uData = getAllUserInfo(user)
                if (len(uData) == 0):
                    continue
                count += 1
                isBull = 1 if tweet['isBull'] else 0

                dataPoint = [isBull, tweet['commentCount'], tweet['likeCount'],
                            uData['totalTweets'], uData['bullReturnCloseOpen'],
                            uData['bullReturnTimePrice'], uData['bullNumCloseOpen'],
                            uData['bullNumTimePrice'], uData['bullPredictions'],
                            uData['bullReturnUnique'], uData['bullNumUnique'],
                            uData['bullNumUnique'], uData['bearReturnTimePrice'],
                            uData['bearNumCloseOpen'], uData['bearNumTimePrice'],
                            uData['bearPredictions'], uData['bearReturnUnique'],
                            uData['bearNumUnique'], uData['accuracy'],
                            uData['followers'], uData['following'], uData['ideas'],
                            uData['like_count'], uData['user_status'], closeOpen[2]]
                data.append(dataPoint)

            with open("new_file.csv", "a") as my_csv:
                csvWriter = csv.writer(my_csv, delimiter=',')
                csvWriter.writerows(data)
            print(date, len(tweets), closeOpen, count)

