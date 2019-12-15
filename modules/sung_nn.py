import torch
import os
import numpy as np
from .hyperparameters import constants
from .helpers import readPickleObject
from .stockAnalysis import getTopStocks
from torch import nn
import torch.nn.functional as F
from torchvision import datasets, transforms
import datetime
from .prediction import setupCloseOpen

def neuralnet():
    stocks = getTopStocks(91)
    print(stocks)
    # import os
    # os.chdir(os.path.dirname(__file__))
    features = readPickleObject("pickledObjects/features.pkl")

    basicStockInfo = constants['stocktweets_client'].get_database('stocks_data_db').training_stock_info_svm
    dates = [datetime.datetime(2019, 9, 11, 9, 30), datetime.datetime(2019, 11, 21, 9, 30), datetime.datetime(2019, 9, 9, 9, 30), datetime.datetime(2019, 8, 8, 9, 30), datetime.datetime(2019, 10, 25, 9, 30), datetime.datetime(2019, 7, 26, 9, 30), datetime.datetime(2019, 8, 29, 9, 30), datetime.datetime(2019, 8, 12, 9, 30), datetime.datetime(2019, 11, 18, 9, 30), datetime.datetime(2019, 7, 29, 9, 30), datetime.datetime(2019, 11, 22, 9, 30), datetime.datetime(2019, 8, 21, 9, 30), datetime.datetime(2019, 9, 26, 9, 30), datetime.datetime(2019, 10, 1, 9, 30), datetime.datetime(2019, 11, 27, 9, 30), datetime.datetime(2019, 8, 26, 9, 30), datetime.datetime(2019, 11, 11, 9, 30), datetime.datetime(2019, 8, 23, 9, 30), datetime.datetime(2019, 8, 16, 9, 30), datetime.datetime(2019, 9, 17, 9, 30), datetime.datetime(2019, 9, 5, 9, 30), datetime.datetime(2019, 11, 6, 9, 30), datetime.datetime(2019, 11, 26, 9, 30), datetime.datetime(2019, 11, 4, 9, 30), datetime.datetime(2019, 10, 17, 9, 30), datetime.datetime(2019, 10, 29, 9, 30), datetime.datetime(2019, 9, 20, 9, 30), datetime.datetime(2019, 10, 18, 9, 30), datetime.datetime(2019, 9, 18, 9, 30), datetime.datetime(2019, 8, 15, 9, 30), datetime.datetime(2019, 10, 15, 9, 30), datetime.datetime(2019, 9, 6, 9, 30), datetime.datetime(2019, 8, 14, 9, 30), datetime.datetime(2019, 9, 4, 9, 30), datetime.datetime(2019, 11, 5, 9, 30), datetime.datetime(2019, 8, 9, 9, 30), datetime.datetime(2019, 10, 21, 9, 30), datetime.datetime(2019, 9, 25, 9, 30), datetime.datetime(2019, 7, 31, 9, 30), datetime.datetime(2019, 11, 12, 9, 30), datetime.datetime(2019, 7, 30, 9, 30), datetime.datetime(2019, 8, 13, 9, 30), datetime.datetime(2019, 11, 8, 9, 30), datetime.datetime(2019, 10, 3, 9, 30), datetime.datetime(2019, 10, 28, 9, 30), datetime.datetime(2019, 10, 11, 9, 30), datetime.datetime(2019, 9, 30, 9, 30), datetime.datetime(2019, 10, 7, 9, 30), datetime.datetime(2019, 8, 20, 9, 30), datetime.datetime(2019, 11, 20, 9, 30), datetime.datetime(2019, 9, 13, 9, 30), datetime.datetime(2019, 9, 12, 9, 30), datetime.datetime(2019, 11, 7, 9, 30), datetime.datetime(2019, 8, 6, 9, 30), datetime.datetime(2019, 10, 31, 9, 30), datetime.datetime(2019, 9, 19, 9, 30), datetime.datetime(2019, 8, 5, 9, 30), datetime.datetime(2019, 11, 1, 9, 30), datetime.datetime(2019, 11, 14, 9, 30), datetime.datetime(2019, 10, 24, 9, 30), datetime.datetime(2019, 8, 28, 9, 30), datetime.datetime(2019, 9, 3, 9, 30), datetime.datetime(2019, 7, 25, 9, 30), datetime.datetime(2019, 10, 22, 9, 30), datetime.datetime(2019, 9, 16, 9, 30), datetime.datetime(2019, 7, 23, 9, 30), datetime.datetime(2019, 9, 27, 9, 30), datetime.datetime(2019, 11, 25, 9, 30), datetime.datetime(2019, 8, 30, 9, 30), datetime.datetime(2019, 10, 10, 9, 30), datetime.datetime(2019, 9, 10, 9, 30), datetime.datetime(2019, 10, 2, 9, 30), datetime.datetime(2019, 7, 22, 9, 30), datetime.datetime(2019, 8, 19, 9, 30)]
    result = {}
    for symbol in stocks:
        symbolInfo = basicStockInfo.find_one({'_id': symbol})
        result[symbol] = symbolInfo
    openClose = setupCloseOpen(dates,stocks)

    featureList = ["UuserBullReturnUnique", "UstockBullReturnUnique","userReturnRatio","stockReturnRatio","userReturnUniqueRatio",
    "stockReturnUniqueRatio","UuserReturnRatio","UstockReturnRatio","UstockReturnUniqueRatio","countRatio","UCountRatio"]
    for stock in stocks:
        for date in dates:
            # print(len(features[stock][date]))
            for feature in features[stock][date]:
                mean = result[stock][feature]["mean"]
                stdev = result[stock][feature]["stdev"]

                features[stock][date][feature] = (features[stock][date][feature] - mean)/stdev

    trainingData = []

    for stock in stocks:
        for date in dates:
            # print(stock)
            # print(openClose[stock])
            temp = openClose[stock][date]

            if temp[2] < 0:
                label = [0,1]
            else:
                label = [1,0]
            trainingData.append((np.asarray(list(features[stock][date].values())),np.asarray(label)))

    # print(features)
    # print(features)
    # print(features["ADXS"][datetime.datetime(2019, 9, 11, 9, 30)])

    # Define a transform to normalize the data
    transform = transforms.Compose([transforms.ToTensor(),
                                    transforms.Normalize((0.5,), (0.5,)),
                                  ])
    # Download and load the training data
    trainset = datasets.MNIST('~/.pytorch/MNIST_data/', download=True, train=True, transform=transform)
    # print(trainset)
    trainloader = torch.utils.data.DataLoader(trainingData, batch_size=1, shuffle=True)


    model = nn.Sequential(nn.Linear(33, 128),
                          nn.ReLU(),
                          nn.Linear(128, 64),
                          nn.ReLU(),
                          nn.Linear(64, 2),
                          nn.LogSoftmax(dim=1))
    # Define the loss
    criterion = nn.NLLLoss()
    # Optimizers require the parameters to optimize and a learning rate
    optimizer = torch.optim.SGD(model.parameters(), lr=0.003)
    epochs = 25
    for e in range(epochs):
        running_loss = 0
        # print(len(trainloader))
        for feature, labels in trainloader:
            # print(labels    )
            # print(feature.dim())
            # print(labels)
            # Flatten MNIST images into a 784 long vector
            # images = images.view(images.shape[0], -1)
            # print(images.dim())
            # print(images)
            # Training pass
            optimizer.zero_grad()

            output = model(feature.float())
            # if output.argmax() == labels.argmax():
                # print("fuck ya")
            # else:
                # print("FUCKFUCKFUCK")
            # print(output)
            loss = criterion(output, torch.max(labels, 1)[1])
            loss.backward()
            optimizer.step()
            running_loss += loss.item()
        else:
            print(f"Training loss at epoch %d: {running_loss/len(trainloader)}" %(e))

    testingDates = [datetime.datetime(2019, 11, 19, 9, 30), datetime.datetime(2019, 10, 23, 9, 30), datetime.datetime(2019, 10, 4, 9, 30), datetime.datetime(2019, 9, 24, 9, 30), datetime.datetime(2019, 11, 15, 9, 30), datetime.datetime(2019, 11, 13, 9, 30), datetime.datetime(2019, 8, 1, 9, 30), datetime.datetime(2019, 7, 24, 9, 30), datetime.datetime(2019, 10, 8, 9, 30), datetime.datetime(2019, 10, 14, 9, 30), datetime.datetime(2019, 8, 27, 9, 30), datetime.datetime(2019, 10, 30, 9, 30), datetime.datetime(2019, 8, 7, 9, 30), datetime.datetime(2019, 8, 22, 9, 30), datetime.datetime(2019, 8, 2, 9, 30), datetime.datetime(2019, 10, 9, 9, 30), datetime.datetime(2019, 10, 16, 9, 30), datetime.datetime(2019, 9, 23, 9, 30)]


    for stock in stocks:
        for date in testingDates:
            # print(len(features[stock][date]))
            # print(stock)
            for feature in features[stock][date]:
                mean = result[stock][feature]["mean"]
                stdev = result[stock][feature]["stdev"]

                features[stock][date][feature] = (features[stock][date][feature] - mean)/stdev

    testingData = []

    for stock in stocks:
        for date in testingDates:
            # print(stock)
            # print(openClose[stock])
            temp = openClose[stock][date]

            if temp[2] < 0:
                label = [0,1]
            else:
                label = [1,0]
            testingData.append((np.asarray(list(features[stock][date].values())),np.asarray(label)))

    testloader = torch.utils.data.DataLoader(testingData, batch_size=1, shuffle=True)

    correct = 0
    incorrect = 0
    for feature, labels in testloader:
        optimizer.zero_grad()
        output = model(feature.float())
        if (output.argmax() == labels.argmax()):
            correct += 1
        else:
            incorrect += 1
    print("correct is %d" % (correct))
    print("incorrect is %d" % (incorrect))
    print("correctness is %f" %((correct/(incorrect + correct))*100))
