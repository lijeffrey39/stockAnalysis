import os
import math
import datetime
from . import helpers
from . import stockPriceAPI
from .fileIO import *


# ------------------------------------------------------------------------
# ----------------------------- Variables --------------------------------
# ------------------------------------------------------------------------


CREATED_DICT_USERS = False
dictPredictions = {}
dictAccuracy = {}
symbolsIgnored = ["PTX", "RGSE", "AMD", "TSLA", "AMZN", "MNGA", "NBEV", "CRMD"]


# ------------------------------------------------------------------------
# ----------------------------- Functions --------------------------------
# ------------------------------------------------------------------------



# Creates top users for each stock (Run each time there are new users)
def writeTempListStocks():
	stocks1 = readSingleList('stockList.csv')
	stocks1.sort()
	for s in stocks1:
		res = topUsersStock(s, 0)
		writeSingleList('templists/' + s + '.csv', res)
 


# Returns the top users for that stock
def topUsersStock(stock, num):
	users = helpers.allUsers()
	result = []

	for user in users:
		path = 'userCalculated/' + user + '_info.csv'
		read = readMultiList(path)
		filtered = list(filter(lambda x: x[0] == stock, read))
		if (len(filtered) == 0):
			continue
		else:
			percent = float(filtered[0][4])	
			result.append([user, percent, float(filtered[0][1]), float(filtered[0][2]), float(filtered[0][3])])

	result.sort(key = lambda x: x[1], reverse = True)
	
	if (num == 0):
		return result
	else:
		return result[:num]



# Creates userxxx_info.csv for each user
def statsUsers():
	users = helpers.allUsers()

	for user in users:
		path = "userinfo/" + user + ".csv"
		if (os.path.isfile(path) == False):
			continue

		res = []
		read = readMultiList(path)

		# Temp filter by ones that have a bull/bear sentiment
		read = list(filter(lambda x: x[5] != '-1', read))

		symbols = list(set(map(lambda x: x[0], read)))
		total = float(len(read))

		for s in symbols:
			filterSymbol = list(filter(lambda x: x[0] == s, read))
			totalCorrect = list(map(lambda x: abs(float(x[7])), list(filter(lambda x: x[5] == '1', filterSymbol))))
			totalIncorrect = list(map(lambda x: abs(float(x[7])), list(filter(lambda x: x[5] == '0', filterSymbol))))
			summedCorrect = reduce(lambda a, b: a + b, totalCorrect) if len(totalCorrect) > 0 else 0
			summedIncorrect = reduce(lambda a, b: a + b, totalIncorrect) if len(totalIncorrect) > 0 else 0

			res.append([s, round(100 * len(filterSymbol) / total, 2), len(totalCorrect), 
				len(totalIncorrect), round(summedCorrect - summedIncorrect, 2)])

		res.sort(key = lambda x: x[4], reverse = True)
		#total = round(reduce(lambda a, b: a + b, list(map(lambda x: x[4], res))), 4)

		writeSingleList('userCalculated/' + user + '_info.csv', res)



# Find how much stock to buy based on money/ratios
def recommendStocks(result, date, money, numStocks):
	picked = result[:numStocks]
	totalWeight = reduce(lambda a, b: a + b, list(map(lambda x: x[1], picked)))
	ratios = list(map(lambda x: x[1] * money / totalWeight, picked))
	stocksNum = []

	date = datetime.datetime(date.year, date.month, date.day, 15, 59)

	for i in range(len(picked)):
		symbol = picked[i][0]
		priceAtPost = savedPricesStocks(date, symbol)
		numStocks = int(ratios[i] / priceAtPost)

		stocksNum.append([symbol, priceAtPost, ratios[i], numStocks])
		# print([symbol, priceAtPost, ratios[i], numStocks])
		
	return stocksNum



# Returns the price of a stock based on whether it was saved from a previous prediction
# need to save all prices for all stocks

def savedPricesStocks(date, stock):
	path = date.strftime("stocksResults/%m-%d-%y-%I_savedStocks.csv")
	dateStock = date.strftime("%m-%d-%y-%I:%M_") + stock

	# create empty file
	if (os.path.isfile(path) == False):
		with open(path, "w") as my_empty_csv:
			pass

	stockList = readMultiList(path)
	foundStock = list(filter(lambda x: x[0] == dateStock, stockList))

	# If stock price exists
	if (len(foundStock) == 1):
		return float(foundStock[0][1])

	(historical, dateTimeAdjusted) = stockPriceAPI.findHistoricalData(date, stock, False)
	priceAtPost = stockPriceAPI.priceAtTime(date, historical) # Price at the time of posting

	stockList.append([dateStock, priceAtPost])
	stockList.sort(key = lambda x: x[0])
	writeSingleList(path, stockList)

	return priceAtPost



# Finds the returns based on predictions made from topStocks
def calcReturnBasedResults(date, result):
	totalsReturns = []
	afterDate = datetime.datetime(date.year, date.month, date.day, 9, 30)
	afterDate += datetime.timedelta(1)
	while (helpers.isTradingDay(afterDate) == False):
		afterDate += datetime.timedelta(1)

	for i in range(5):
		if (i % 5 == 0):
			totalReturn = 0
			pos = 0
			neg = 0
			res = []

			for x in result:
				symbol = x[0]
				priceBefore = x[1]
				shares = x[3]
				totalBefore = priceBefore * shares
				diff = 0
				priceAfter = savedPricesStocks(afterDate, symbol)

				totalAfter = priceAfter * shares
				diff = totalAfter - totalBefore
				if (diff >= 0):
					pos += 1
				else:
					neg += 1

				# print(symbol, diff, priceBefore, priceAfter)
				totalReturn += diff
				res.append([symbol, diff])

			totalReturn = round(totalReturn, 2)
			totalsReturns.append([totalReturn, afterDate])
			return (totalReturn, pos, neg, res)

		afterDate = afterDate + datetime.timedelta(minutes = 1)



# Want to scale between the top cutoff with > 0 return and bottom cutoff with < 0 return
def createDictUsers():
	global dictAccuracy
	global dictPredictions

	users = readMultiList('userInfo.csv')
	users = list(filter(lambda x: len(x) >= 4, users))

	cutoff = 0.98
	topPercent = list(filter(lambda x: float(x[3]) > 0, users))
	topPercentIndex = int(len(topPercent) * (cutoff))
	maxPercent = float(topPercent[len(topPercent) - topPercentIndex][3])

	bottomPercent = list(filter(lambda x: float(x[3]) < 0, users))
	bottomPercentIndex = int(len(bottomPercent) * (cutoff))
	minPercent = float(bottomPercent[bottomPercentIndex][3])

	totalPredictionsList = list(map(lambda x: int(float(x[1]) + float(x[2])), users))
	maxNumPredictionsLog = math.log(max(totalPredictionsList))

	# Find user's accuracy scaled by max and min percent as well as number of prediction
	for user in users:
		username = user[0]
		percent = float(user[3])
		numPredictions = int(float(user[1]) + float(user[2]))
		dictPredictions[username] = (math.log(numPredictions) / maxNumPredictionsLog) - 0.5
		if (percent > 0):
			percent = maxPercent if (percent >= maxPercent) else percent
			dictAccuracy[username] = percent / maxPercent
		else:
			percent = minPercent if (percent <= minPercent) else percent
			dictAccuracy[username] = percent / minPercent
	return


# Save the current day's stock price at 4pm and next day's prices at 9 am for all stocks
def saveStockPricesDay(date, stocks, afterDate):
	# Time at 4pm for current date
	path = date.strftime("stocksResults/%m-%d-%y-%I_savedStocks.csv")
	if (os.path.isfile(path) == False): 	# create empty file
		with open(path, "w") as my_empty_csv:
			pass
	else:
		return

	stockList = []
	for s in stocks:
		print(s)
		(historical, dateTimeAdjusted) = stockPriceAPI.findHistoricalData(date, s, False)

		for i in range(6):
			date = datetime.datetime(date.year, date.month, date.day, 9, i * 5)
			dateString = date.strftime("%m-%d-%y-%I:%M_") + s
			priceAtPost = stockPriceAPI.priceAtTime(date, historical) # Price at the time of posting
			stockList.append([dateString, priceAtPost])

	stockList.sort(key = lambda x: x[0])
	writeSingleList(path, stockList)

	return


# Ideal when enough user information collected

# Current weightings for predictions 
# 1. Number of stocks to pick from (higher means lower risk)
# 2. Accuracy for that user overall 
# 3. Accuracy for that user for that specific stock
# 4. How many predictions this user has made relative to everyone else
# 5. How many predictions this user has made relative to people predicting this stock

# Other weights to add
# 6. Number of likes/comments for a prediction
# 7. Number of followers (If in thousands, remove k and multiply by 1,000)
# 8. How old of a member he/she is

# TODO
# 8. Find weight of a particular sector/industry


def topStocks(date, money, weights):

	# path = date.strftime("stocksResults/%m-%d-%y/")
	pathWeighted = date.strftime("stocksResults/%m-%d-%y_weighted.csv")
	folderPath = date.strftime("stocksResults/%m-%d-%y/")

	# if not created yet
	if ((not os.path.exists(folderPath))):
		return

	stocks = [f for f in os.listdir(folderPath) if os.path.isfile(os.path.join(folderPath, f))] 
	stocks = list(map(lambda x: x[:len(x) - 4], stocks))
	stocks = list(filter(lambda x: '.DS_S' not in x, stocks))


	# Save all the stock prices at 4 pm and 9 am the next day
	# Time at 4pm for current date
	beforeDate = datetime.datetime(date.year, date.month, date.day, 15, 59)
	saveStockPricesDay(beforeDate, stocks, False)

	# Time at 9:30 for next day
	afterDate = datetime.datetime(date.year, date.month, date.day, 9, 30)
	afterDate += datetime.timedelta(1)
	while (helpers.isTradingDay(afterDate) == False):
		afterDate += datetime.timedelta(1)

	saveStockPricesDay(afterDate, stocks, True)





	users = readMultiList('userInfo.csv')
	users = list(filter(lambda x: len(x) >= 4, users))
	mappedUsers = set(list(map(lambda x: x[0], users)))
	result = []


	numStocks = weights[0] 
	uAccW = weights[1]
	uStockAccW = weights[2]
	uPredW = weights[3]
	uStockPredW = weights[4]

	global CREATED_DICT_USERS
	if (CREATED_DICT_USERS == False):
		createDictUsers()
		CREATED_DICT_USERS = True

	totalUsers = 0
	totalHits = 0

	# Find weight for each stock
	for symbol in stocks:
		resPath = folderPath + symbol + ".csv"
		resSymbol = readMultiList(resPath)
		total = 0

		# scale based on how accurate that user is
		topUsersForStock = readMultiList('templists/' + symbol + '.csv')

		# safety check cuz len(topUsersForStock) must be  > 1
		if (len(topUsersForStock) < 2):
			continue

		try:
			maxPercent = math.log(abs(float(topUsersForStock[0][1])))
		except:
			maxPercent = 0.1

		try:
			minPercent = -1 * math.log(abs(float(topUsersForStock[len(topUsersForStock) - 1][1])))
		except:
			minPercent = -0.1

		if (maxPercent == 0.0):
			maxPercent = 0.1
		if (minPercent == 0.0):
			minPercent = 0.1


		dictUserStockAccuracy = {}
		dictUserStockPredictions = {}
		for u in topUsersForStock:
			user = u[0]
			percent = float(u[1])
			dictUserStockPredictions[user] = (float(u[2]) / 100.0) - 0.5
			if (percent == 0.0):
				dictUserStockAccuracy[user] = 0
				continue

			percentLog = math.log(abs(percent))
			if (percent > 0):
				dictUserStockAccuracy[user] = percentLog / maxPercent
			else:
				dictUserStockAccuracy[user] = -1 * percentLog / minPercent

		for r in resSymbol:
			user = r[0]
			if (r[1] == ''):
				continue
			isBull = bool(r[1])

			totalUsers += 1
			# Only based no user info's that's been collected
			if (user in mappedUsers):
				totalHits += 1
				userAccuracy = dictAccuracy[user] # How much return the user had overall
				userPredictions = dictPredictions[user] # Number of predictions user made overall

				totalWeight = 0
				if (user in dictUserStockAccuracy):
					userStockAccuracy = dictUserStockAccuracy[user]
					userStockPredictions = dictUserStockPredictions[user]
					totalWeight = (uAccW * userAccuracy) + (uStockAccW * userStockAccuracy) + (uPredW * userPredictions) + (uStockPredW * userStockPredictions)
				else:
					totalWeight = (uAccW * userAccuracy) + (uPredW * userPredictions)

				if (isBull):
					total += totalWeight
				else:
					total -= totalWeight

		if (symbol in symbolsIgnored):
			continue
		result.append([symbol, total])

	result.sort(key = lambda x: x[1], reverse = True)
	res = recommendStocks(result, date, money, numStocks)
	writeSingleList(pathWeighted, result)
	hitPrecent = totalHits * 100.0 / totalUsers
	
	return (res, round(hitPrecent, 2))
