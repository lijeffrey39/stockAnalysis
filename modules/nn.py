import datetime
from functools import reduce

import matplotlib.pyplot as plt
import numpy as np
import torch
from torch import nn
from torch.autograd import Variable

from .hyperparameters import constants
from .prediction import (generateFeatures, readPickleObject, setupCloseOpen,
                         setupStockInfos, writePickleObject, findAllTweets, setupUserInfos)
from .stockAnalysis import getTopStocks


def calcReturns(e):
    net = torch.load('models/' + str(e) + '.pt')
    dates = [datetime.datetime(2019, 11, 19, 9, 30), datetime.datetime(2019, 10, 23, 9, 30), datetime.datetime(2019, 10, 4, 9, 30), datetime.datetime(2019, 9, 24, 9, 30), datetime.datetime(2019, 11, 15, 9, 30), datetime.datetime(2019, 11, 13, 9, 30), datetime.datetime(2019, 8, 1, 9, 30), datetime.datetime(2019, 7, 24, 9, 30), datetime.datetime(2019, 10, 8, 9, 30), datetime.datetime(2019, 10, 14, 9, 30), datetime.datetime(2019, 8, 27, 9, 30), datetime.datetime(2019, 10, 30, 9, 30), datetime.datetime(2019, 8, 7, 9, 30), datetime.datetime(2019, 8, 22, 9, 30), datetime.datetime(2019, 8, 2, 9, 30), datetime.datetime(2019, 10, 9, 9, 30), datetime.datetime(2019, 10, 16, 9, 30), datetime.datetime(2019, 9, 23, 9, 30)]
    features2 = {}
    stocks = getTopStocks(20)
    dates = [datetime.datetime(2019, 12, 12, 9, 30)]
    allTweets = findAllTweets(stocks, dates, True, True)
    stockInfo = setupStockInfos(stocks)
    userInfos = setupUserInfos(stocks)
    features = generateFeatures(dates, stocks, allTweets, stockInfo, userInfos, True, True)

    result = {}
    basicStockInfo = constants['stocktweets_client'].get_database('stocks_data_db').training_stock_info_svm
    featureList = ["UuserBullReturnUnique", "UstockBullReturnUnique", 
                   "userReturnRatio", "stockReturnRatio",
                   "userReturnUniqueRatio", "stockReturnUniqueRatio",
                   "UuserReturnRatio", "UstockReturnRatio",
                   "UstockReturnUniqueRatio", "countRatio",
                   "UCountRatio"]
    for symbol in stocks:
        symbolInfo = basicStockInfo.find_one({'_id': symbol})
        result[symbol] = symbolInfo

    for stock in stocks:
        features2[stock] = {}
        for date in dates:
            features2[stock][date] = {}
            for feature in features[stock][date]:
                mean = result[stock][feature]["mean"]
                stdev = result[stock][feature]["stdev"]
                if (feature in featureList):
                    features2[stock][date][feature] = (features[stock][date][feature] - mean) / stdev

    testingData = []
    for stock in stocks:
        for date in dates:
            label = 1
            testingData.append((np.asarray(list(features2[stock][date].values())), np.asarray(label)))

    testLoader = torch.utils.data.DataLoader(testingData, batch_size=1)
    result = {}
    for feature, labels in testLoader:
        prediction = net(feature.float())
        for stock in stocks:
            for date in dates:
                count = 0
                for f in features2[stock][date]:
                    if (f == 'UuserBullReturnUnique' or f == 'UstockBullReturnUnique'):
                        if (feature[0][0] == features2[stock][date][f] or feature[0][1] == features2[stock][date][f]):
                            count += 1
                if (count == 2):
                    if (date not in result):
                        result[date] = {}
                    result[date][stock] = float(prediction)

    res = result[dates[0]]
    bestParams = list(res.items())
    bestParams.sort(key=lambda x: x[1], reverse=True)
    for x in bestParams:
        print(x)
    return

    openClose = setupCloseOpen(dates, stocks)
    count = 0
    total = 0
    totalReturn = 0
    count1 = 0
    returns = [0] * 91
    returns1 = [0] * 91
    for i in range(len(dates)):
        newDict = {}
        for x in result[dates[i]]:
            if (x in stocks):
                newDict[x] = result[dates[i]][x]
        for j in range(1, 90):
            resPerParam = list(newDict.items())
            resPerParam.sort(key=lambda x: abs(x[1]), reverse=True)
            resPerParam = resPerParam[:j]
            if (j == 1):
                print(resPerParam, dates[i], openClose[resPerParam[0][0]][dates[i]][2])
            sumDiffs = reduce(lambda a, b: a + b,
                            list(map(lambda x: abs(x[1]), resPerParam)))
            returnToday = 0
            for symbolObj in resPerParam:
                symbol = symbolObj[0]
                stdDev = symbolObj[1]
                closeOpen = openClose[symbol][dates[i]][2]
                # print(stdDev, sumDiffs, closeOpen)
                returnToday += (float(stdDev / sumDiffs) * closeOpen)
                if (stdDev > 0):
                    count1 += 1
                if ((closeOpen > 0 and stdDev > 0) or (closeOpen < 0 and stdDev < 0)):
                    count += 1
                    returns[j] += 1
                # total += 1
                returns1[j] += 1
            mappedResult = list(map(lambda x: [x[0], round(x[1] / sumDiffs * 100, 2), openClose[x[0]][dates[i]]], resPerParam))
            # print(returnToday)
            # returns[j] += returnToday
            # totalReturn += returnToday
    # print(totalReturn, count/total, count1/total)
    for i in range(1, 90):
        returns[i] = returns[i] / returns1[i]

    xs = []
    for i in range(89):
        xs.append(i)

    plt.plot(xs, returns[1:90])
    plt.xlabel("Number of Stocks")
    plt.ylabel("Accuracy")
    plt.title("Neural Network Linear Regression (Top 91 Stocks)")
    plt.show()
    print(returns)


def testing(e):
    stocks = getTopStocks(100)
    basicStockInfo = constants['stocktweets_client'].get_database('stocks_data_db').training_stock_info_svm
    dates = [datetime.datetime(2019, 9, 11, 9, 30), datetime.datetime(2019, 11, 21, 9, 30), datetime.datetime(2019, 9, 9, 9, 30), datetime.datetime(2019, 8, 8, 9, 30), datetime.datetime(2019, 10, 25, 9, 30), datetime.datetime(2019, 7, 26, 9, 30), datetime.datetime(2019, 8, 29, 9, 30), datetime.datetime(2019, 8, 12, 9, 30), datetime.datetime(2019, 11, 18, 9, 30), datetime.datetime(2019, 7, 29, 9, 30), datetime.datetime(2019, 11, 22, 9, 30), datetime.datetime(2019, 8, 21, 9, 30), datetime.datetime(2019, 9, 26, 9, 30), datetime.datetime(2019, 10, 1, 9, 30), datetime.datetime(2019, 11, 27, 9, 30), datetime.datetime(2019, 8, 26, 9, 30), datetime.datetime(2019, 11, 11, 9, 30), datetime.datetime(2019, 8, 23, 9, 30), datetime.datetime(2019, 8, 16, 9, 30), datetime.datetime(2019, 9, 17, 9, 30), datetime.datetime(2019, 9, 5, 9, 30), datetime.datetime(2019, 11, 6, 9, 30), datetime.datetime(2019, 11, 26, 9, 30), datetime.datetime(2019, 11, 4, 9, 30), datetime.datetime(2019, 10, 17, 9, 30), datetime.datetime(2019, 10, 29, 9, 30), datetime.datetime(2019, 9, 20, 9, 30), datetime.datetime(2019, 10, 18, 9, 30), datetime.datetime(2019, 9, 18, 9, 30), datetime.datetime(2019, 8, 15, 9, 30), datetime.datetime(2019, 10, 15, 9, 30), datetime.datetime(2019, 9, 6, 9, 30), datetime.datetime(2019, 8, 14, 9, 30), datetime.datetime(2019, 9, 4, 9, 30), datetime.datetime(2019, 11, 5, 9, 30), datetime.datetime(2019, 8, 9, 9, 30), datetime.datetime(2019, 10, 21, 9, 30), datetime.datetime(2019, 9, 25, 9, 30), datetime.datetime(2019, 7, 31, 9, 30), datetime.datetime(2019, 11, 12, 9, 30), datetime.datetime(2019, 7, 30, 9, 30), datetime.datetime(2019, 8, 13, 9, 30), datetime.datetime(2019, 11, 8, 9, 30), datetime.datetime(2019, 10, 3, 9, 30), datetime.datetime(2019, 10, 28, 9, 30), datetime.datetime(2019, 10, 11, 9, 30), datetime.datetime(2019, 9, 30, 9, 30), datetime.datetime(2019, 10, 7, 9, 30), datetime.datetime(2019, 8, 20, 9, 30), datetime.datetime(2019, 11, 20, 9, 30), datetime.datetime(2019, 9, 13, 9, 30), datetime.datetime(2019, 9, 12, 9, 30), datetime.datetime(2019, 11, 7, 9, 30), datetime.datetime(2019, 8, 6, 9, 30), datetime.datetime(2019, 10, 31, 9, 30), datetime.datetime(2019, 9, 19, 9, 30), datetime.datetime(2019, 8, 5, 9, 30), datetime.datetime(2019, 11, 1, 9, 30), datetime.datetime(2019, 11, 14, 9, 30), datetime.datetime(2019, 10, 24, 9, 30), datetime.datetime(2019, 8, 28, 9, 30), datetime.datetime(2019, 9, 3, 9, 30), datetime.datetime(2019, 7, 25, 9, 30), datetime.datetime(2019, 10, 22, 9, 30), datetime.datetime(2019, 9, 16, 9, 30), datetime.datetime(2019, 7, 23, 9, 30), datetime.datetime(2019, 9, 27, 9, 30), datetime.datetime(2019, 11, 25, 9, 30), datetime.datetime(2019, 8, 30, 9, 30), datetime.datetime(2019, 10, 10, 9, 30), datetime.datetime(2019, 9, 10, 9, 30), datetime.datetime(2019, 10, 2, 9, 30), datetime.datetime(2019, 7, 22, 9, 30), datetime.datetime(2019, 8, 19, 9, 30)]

    result = {}
    for symbol in stocks:
        symbolInfo = basicStockInfo.find_one({'_id': symbol})
        result[symbol] = symbolInfo
    openClose = setupCloseOpen(dates, stocks)

    features = readPickleObject("pickledObjects/features.pkl")
    featureList = ["UuserBullReturnUnique", "UstockBullReturnUnique", 
                   "userReturnRatio", "stockReturnRatio",
                   "userReturnUniqueRatio", "stockReturnUniqueRatio",
                   "UuserReturnRatio", "UstockReturnRatio",
                   "UstockReturnUniqueRatio", "countRatio",
                   "UCountRatio"]
    features1 = {}
    for stock in stocks:
        features1[stock] = {}
        for date in dates:
            features1[stock][date] = {}
            for feature in features[stock][date]:
                mean = result[stock][feature]["mean"]
                stdev = result[stock][feature]["stdev"]
                features[stock][date][feature] = (features[stock][date][feature] - mean)/stdev
                if (feature in featureList):
                    features1[stock][date][feature] = (features[stock][date][feature] - mean) / stdev

    trainingData = []
    for stock in stocks:
        for date in dates:
            temp = openClose[stock][date]
            label = temp[2]
            trainingData.append((np.asarray(list(features1[stock][date].values())), np.asarray(label)))

    loader = torch.utils.data.DataLoader(trainingData, batch_size=1, shuffle=True)

    net = nn.Sequential(nn.Linear(11, 128),
                          nn.ReLU(),
                          nn.Linear(128, 64),
                          nn.ReLU(),
                          nn.Linear(64, 2),
                          nn.LogSoftmax(dim=1))

    net = torch.nn.Sequential(
        torch.nn.Linear(11, 128),
        torch.nn.ReLU(),
        torch.nn.Linear(128, 64),
        torch.nn.ReLU(),
        torch.nn.Linear(64, 1)
    )
    net = net.float()

    # optimizer = torch.optim.Adam(net.parameters(), lr=0.001)
    # loss_func = torch.nn.MSELoss()

    loss_func = torch.nn.SmoothL1Loss()
    # Optimizers require the parameters to optimize and a learning rate
    optimizer = torch.optim.SGD(net.parameters(), lr=0.001)

    # start training
    for epoch in range(e):
        running_loss = 0
        for step, (batch_x, batch_y) in enumerate(loader):
            b_x = Variable(batch_x)
            b_y = Variable(batch_y)

            prediction = net(b_x.float())     # input x and predict based on x
            loss = loss_func(prediction, b_y.float())
            optimizer.zero_grad()   # clear gradients for next train
            loss.backward()         # backpropagation, compute gradients
            optimizer.step()        # apply gradients
            running_loss += loss.item()
        print(epoch, running_loss/len(loader))

    torch.save(net, 'models/' + str(e) + '.pt')
    return

    net = torch.load('models/1.pt')

    testingDates = [datetime.datetime(2019, 11, 19, 9, 30), datetime.datetime(2019, 10, 23, 9, 30), datetime.datetime(2019, 10, 4, 9, 30), datetime.datetime(2019, 9, 24, 9, 30), datetime.datetime(2019, 11, 15, 9, 30), datetime.datetime(2019, 11, 13, 9, 30), datetime.datetime(2019, 8, 1, 9, 30), datetime.datetime(2019, 7, 24, 9, 30), datetime.datetime(2019, 10, 8, 9, 30), datetime.datetime(2019, 10, 14, 9, 30), datetime.datetime(2019, 8, 27, 9, 30), datetime.datetime(2019, 10, 30, 9, 30), datetime.datetime(2019, 8, 7, 9, 30), datetime.datetime(2019, 8, 22, 9, 30), datetime.datetime(2019, 8, 2, 9, 30), datetime.datetime(2019, 10, 9, 9, 30), datetime.datetime(2019, 10, 16, 9, 30), datetime.datetime(2019, 9, 23, 9, 30)]
    features2 = {}
    stocks = getTopStocks(100)
    for stock in stocks:
        features2[stock] = {}
        for date in testingDates:
            features2[stock][date] = {}
            for feature in features[stock][date]:
                mean = result[stock][feature]["mean"]
                stdev = result[stock][feature]["stdev"]
                if (feature in featureList):
                    features2[stock][date][feature] = (features[stock][date][feature] - mean) / stdev

    testingData = []
    for stock in stocks:
        for date in testingDates:
            temp = openClose[stock][date]
            label = temp[2]
            testingData.append((np.asarray(list(features2[stock][date].values())), np.asarray(label)))

    testLoader = torch.utils.data.DataLoader(testingData, batch_size=1)
    result = {}
    for feature, labels in testLoader:
        prediction = net(feature.float())
        for stock in stocks:
            for date in testingDates:
                count = 0
                for f in features2[stock][date]:
                    if (f == 'UuserBullReturnUnique' or f == 'UstockBullReturnUnique'):
                        if (feature[0][0] == features2[stock][date][f] or feature[0][1] == features2[stock][date][f]):
                            count += 1
                if (count == 2):
                    # print(feature[0], features2[stock][date])
                    if (date not in result):
                        result[date] = {}
                    result[date][stock] = float(prediction)
                    # print(stock, date, float(prediction))

    writePickleObject("pickledObjects/results13.pkl", result)
    # print(result[datetime.datetime(2019, 11, 19, 9, 30)])
    return
