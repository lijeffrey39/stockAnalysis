import numpy as np
from sklearn.decomposition import PCA
from sklearn.tree import DecisionTreeClassifier
from sklearn.svm import SVC

import matplotlib.pyplot as plt
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
from .prediction import setupCloseOpen

from .helpers import findTradingDays
from .stockAnalysis import getTopStocks
from .hyperparameters import constants
from .stockPriceAPI import getUpdatedCloseOpen
from .userAnalysis import getAllUserInfo







def svmtesting():
	path = "pickledObjects/features.pkl"
	features = readPickleObject(path)
	stocks = getTopStocks(91)
	# print(features.keys(),len(features.keys()))
	# return

	basicStockInfo = constants['stocktweets_client'].get_database('stocks_data_db').training_stock_info_svm
	result = {}
	for symbol in stocks:
		symbolInfo = basicStockInfo.find_one({'_id': symbol})
		result[symbol] = symbolInfo


	train = []
	labels = []
	traindates = [datetime.datetime(2019, 9, 11, 9, 30), datetime.datetime(2019, 11, 21, 9, 30), datetime.datetime(2019, 9, 9, 9, 30), datetime.datetime(2019, 8, 8, 9, 30), datetime.datetime(2019, 10, 25, 9, 30), datetime.datetime(2019, 7, 26, 9, 30), datetime.datetime(2019, 8, 29, 9, 30), datetime.datetime(2019, 8, 12, 9, 30), datetime.datetime(2019, 11, 18, 9, 30), datetime.datetime(2019, 7, 29, 9, 30), datetime.datetime(2019, 11, 22, 9, 30), datetime.datetime(2019, 8, 21, 9, 30), datetime.datetime(2019, 9, 26, 9, 30), datetime.datetime(2019, 10, 1, 9, 30), datetime.datetime(2019, 11, 27, 9, 30), datetime.datetime(2019, 8, 26, 9, 30), datetime.datetime(2019, 11, 11, 9, 30), datetime.datetime(2019, 8, 23, 9, 30), datetime.datetime(2019, 8, 16, 9, 30), datetime.datetime(2019, 9, 17, 9, 30), datetime.datetime(2019, 9, 5, 9, 30), datetime.datetime(2019, 11, 6, 9, 30), datetime.datetime(2019, 11, 26, 9, 30), datetime.datetime(2019, 11, 4, 9, 30), datetime.datetime(2019, 10, 17, 9, 30), datetime.datetime(2019, 10, 29, 9, 30), datetime.datetime(2019, 9, 20, 9, 30), datetime.datetime(2019, 10, 18, 9, 30), datetime.datetime(2019, 9, 18, 9, 30), datetime.datetime(2019, 8, 15, 9, 30), datetime.datetime(2019, 10, 15, 9, 30), datetime.datetime(2019, 9, 6, 9, 30), datetime.datetime(2019, 8, 14, 9, 30), datetime.datetime(2019, 9, 4, 9, 30), datetime.datetime(2019, 11, 5, 9, 30), datetime.datetime(2019, 8, 9, 9, 30), datetime.datetime(2019, 10, 21, 9, 30), datetime.datetime(2019, 9, 25, 9, 30), datetime.datetime(2019, 7, 31, 9, 30), datetime.datetime(2019, 11, 12, 9, 30), datetime.datetime(2019, 7, 30, 9, 30), datetime.datetime(2019, 8, 13, 9, 30), datetime.datetime(2019, 11, 8, 9, 30), datetime.datetime(2019, 10, 3, 9, 30), datetime.datetime(2019, 10, 28, 9, 30), datetime.datetime(2019, 10, 11, 9, 30), datetime.datetime(2019, 9, 30, 9, 30), datetime.datetime(2019, 10, 7, 9, 30), datetime.datetime(2019, 8, 20, 9, 30), datetime.datetime(2019, 11, 20, 9, 30), datetime.datetime(2019, 9, 13, 9, 30), datetime.datetime(2019, 9, 12, 9, 30), datetime.datetime(2019, 11, 7, 9, 30), datetime.datetime(2019, 8, 6, 9, 30), datetime.datetime(2019, 10, 31, 9, 30), datetime.datetime(2019, 9, 19, 9, 30), datetime.datetime(2019, 8, 5, 9, 30), datetime.datetime(2019, 11, 1, 9, 30), datetime.datetime(2019, 11, 14, 9, 30), datetime.datetime(2019, 10, 24, 9, 30), datetime.datetime(2019, 8, 28, 9, 30), datetime.datetime(2019, 9, 3, 9, 30), datetime.datetime(2019, 7, 25, 9, 30), datetime.datetime(2019, 10, 22, 9, 30), datetime.datetime(2019, 9, 16, 9, 30), datetime.datetime(2019, 7, 23, 9, 30), datetime.datetime(2019, 9, 27, 9, 30), datetime.datetime(2019, 11, 25, 9, 30), datetime.datetime(2019, 8, 30, 9, 30), datetime.datetime(2019, 10, 10, 9, 30), datetime.datetime(2019, 9, 10, 9, 30), datetime.datetime(2019, 10, 2, 9, 30), datetime.datetime(2019, 7, 22, 9, 30), datetime.datetime(2019, 8, 19, 9, 30)]
	for stock in stocks:
		# print(stock)
		x = setupCloseOpen(traindates,stock)

		# dates = x[stock].keys()
		# print(features[stock].keys())
		# print(features[stock][datetime.datetime(2019, 10, 2, 9, 30)])
		for date in traindates:
			# print(date)
			try:
				feature = features[stock][date]
				temp1 = []
				for f in feature:
					mean = result[stock][f]["mean"]
					stdev = result[stock][f]["stdev"]
					temp1.append((feature[f]-mean)/stdev)
				

				(_,_, change) = (x[stock][date])
				if change <= 0:
					labels.append(0)
				else:
					labels.append(1)

				train.append(temp1)


			except:
				print("yolo",stock,date)


	print(len(train), len(labels))
	train = np.asarray(train)
	labels = np.asarray(labels)
	#print(train, len(train))

	classifier = SVC()


	classifier.fit(train, labels)


	testdates = [datetime.datetime(2019, 11, 19, 9, 30), datetime.datetime(2019, 10, 23, 9, 30), datetime.datetime(2019, 10, 4, 9, 30), datetime.datetime(2019, 9, 24, 9, 30), datetime.datetime(2019, 11, 15, 9, 30), datetime.datetime(2019, 11, 13, 9, 30), datetime.datetime(2019, 8, 1, 9, 30), datetime.datetime(2019, 7, 24, 9, 30), datetime.datetime(2019, 10, 8, 9, 30), datetime.datetime(2019, 10, 14, 9, 30), datetime.datetime(2019, 8, 27, 9, 30), datetime.datetime(2019, 10, 30, 9, 30), datetime.datetime(2019, 8, 7, 9, 30), datetime.datetime(2019, 8, 22, 9, 30), datetime.datetime(2019, 8, 2, 9, 30), datetime.datetime(2019, 10, 9, 9, 30), datetime.datetime(2019, 10, 16, 9, 30), datetime.datetime(2019, 9, 23, 9, 30)]


	finalstart = []
	finalend = []
	testlabels = []
	test = []
	for stock in stocks:
		# print(stock)
		x = setupCloseOpen(testdates,stock)
		# dates = x[stock].keys()
		# print(features[stock].keys())
		# print(features[stock][datetime.datetime(2019, 10, 2, 9, 30)])
		for date in testdates:
			# print(date)
			try:
				feature = features[stock][date]
				temp1 = []
				for f in feature:
					mean = result[stock][f]["mean"]
					stdev = result[stock][f]["stdev"]
					temp1.append((feature[f]-mean)/stdev)
				
				(start,end, change) = (x[stock][date])
				if change <= 0:
					testlabels.append(0)
				else:
					testlabels.append(1)

				finalstart.append(start)
				finalend.append(end)

				test.append(temp1)


			except:
				print("yolo",stock,date)


	print(len(test), len(testlabels))
	test = np.asarray(test)
	testlabels = np.asarray(testlabels)


	# # predict labels using the trained classifier

	pred_labels = classifier.predict(test)


	print(pred_labels)

	count = 0

	before = 0
	after = 0
	for i in range(len(pred_labels)):
		if testlabels[i] == pred_labels[i]:
			count += 1;


		if pred_labels[i] == 1:
			before += finalstart[i]
			after += finalend[i]

	print("percent",(after-before)/after*100)

	print(count/len(testlabels))


	return(count/len(testlabels))




