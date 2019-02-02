import multiprocessing
import platform
import datetime
import math
import json
import time
import sys
import os

from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from selenium import webdriver
from multiprocessing import Process, Pool, current_process
from iexfinance.stocks import get_historical_intraday
from dateutil.parser import parse
from bs4 import BeautifulSoup
from functools import reduce

from modules.scroll import *
from modules.messageExtract import *
from modules.fileIO import *
from modules.stockPriceAPI import *
from modules.helpers import *


chrome_options = webdriver.ChromeOptions()
prefs = {"profile.managed_default_content_settings.images": 2}
chrome_options.add_experimental_option("prefs", prefs)
# chrome_options.add_argument("--headless")
# chrome_options.add_argument('log-level=3')
cpuCount = multiprocessing.cpu_count()


chromedriverName = 'chromedriver' if (platform.system() == "Darwin") else 'chromedriver.exe'
PROJECT_ROOT = os.getcwd()
DRIVER_BIN = os.path.join(PROJECT_ROOT, chromedriverName)
DAYS_BACK = 75
SAVE_USER_PAGE = False
SAVE_STOCK_PAGE = False
CREATED_DICT_USERS = False
dictAccuracy = {}
dictPredictions = {}


# SET NAME ATTRIBUTES
messageStreamAttr = 'st_1m1w96g'
timeAttr = 'st_HsSv26f'
messageTextAttr = 'st_2giLhWN'


# Make cache for that symbol and date so don't have to keep calling api
# Formatted like {"TVIX": {"2018-12-24": [historical_data], "2018-12-23": [more_data]}
datesSeenGlobal = {} 
useDatesSeen = False



# ------------------------------------------------------------------------
# ----------------------- Analyze Specific Stock -------------------------
# ------------------------------------------------------------------------


# Return soup object page of that stock 
def findPageStock(symbol, days, driver):
	# if html is stored
	path = 'stocksPages/' + symbol + '.html'
	if (os.path.isfile(path)):
		print("File Exists")
		# html = open(path, "r")
		soup = BeautifulSoup(open(path), 'html.parser')
		print("Finished Reading in")
		return (soup, False)

	url = "https://stocktwits.com/symbol/" + symbol
	driver.get(url)
	foundEnough = scrollFor(symbol, days, driver)

	if (foundEnough == False):
		return (None, True)

	html = driver.page_source
	soup = BeautifulSoup(html, 'html.parser')

	if (SAVE_STOCK_PAGE):
		with open(path, "w") as file:
		    file.write(str(soup))

	return (soup, False)



def getBearBull(symbol, date, driver):
	# For caching
	processName = current_process().name
	datesSeenGlobal[processName] = {}

	dateNow = datetime.datetime.now()
	days = (dateNow - date).days

	(soup, error) = findPageStock(symbol, days, driver)

	if (error):
		print("ERROR BAD")
		return []

	messages = soup.find_all('div', attrs={'class': messageStreamAttr})
	res = []

	for m in messages:
		t = m.find('a', {'class': timeAttr})
		if (t == None):
			continue
		textM = m.find('div', attrs={'class': messageTextAttr})
		dateTime = findDateTime(t.text)
		user = findUser(m)
		isBull = isBullMessage(m)

		if (isValidMessage(dateTime, date, isBull, user, symbol, 0) == False):
			continue

		(historical, dateTimeAdjusted1) = findHistoricalData(dateTime, symbol, False)
		foundAvg = priceAtTime(dateTime, historical) # fix this function to take dateTimeadjusted

		messageInfo = [user, isBull, dateTimeAdjusted1, foundAvg]
		res.append(messageInfo)

	return res



# ------------------------------------------------------------------------
# ----------------------- Analyze Specific User --------------------------
# ------------------------------------------------------------------------



# Return soup object page of that user 
def findPageUser(username, days, driver):
	# if html is stored
	path = 'usersPages/' + username + '.html'
	if (os.path.isfile(path)):
		print("File Exists")
		# html = open(path, "r")
		soup = BeautifulSoup(open(path), 'html.parser')
		return soup

	url = "https://stocktwits.com/" + username
	driver.get(url)
	foundEnough = scrollFor(username, days, driver)

	if (foundEnough == False):
		return None

	html = driver.page_source
	soup = BeautifulSoup(html, 'html.parser')

	if (SAVE_USER_PAGE):
		with open(path, "w") as file:
		    file.write(str(soup))

	return soup


def analyzeUser(username, soup, daysInFuture):
	messages = soup.find_all('div', attrs={'class': messageStreamAttr})
	dateNow = datetime.datetime.now()
	res = []

	for m in messages:
		t = m.find('a', attrs={'class': timeAttr})
		dateTime = findDateTime(t.text)
		user = findUser(m)
		isBull = isBullMessage(m)
		symbol = findSymbol(m)
		likeCnt = likeCount(m)
		commentCnt = commentCount(m)

		if (isValidMessage(dateTime, dateNow, isBull, user, symbol, daysInFuture) == False):
			continue

		(historical, dateTimeAdjusted) = findHistoricalData(dateTime, symbol, False)
		priceAtPost = priceAtTime(dateTime, historical) # Price at the time of posting
		# Price at 3:59 PM
		prices = priceAtTime(datetime.datetime(dateTime.year, dateTime.month, dateTime.day, 15, 59), historical)


		# Find price after # days
		delta = datetime.timedelta(daysInFuture)
		newTime = dateTime + delta
		newTime = datetime.datetime(newTime.year, newTime.month, newTime.day, 9, 30)

		(historical, dateTimeAdjusted) = findHistoricalData(newTime, symbol, True)
		newPrices = priceAtTime(newTime, historical) # Find price at 9:30 AM
		# Find price at 10:00 AM
		price10 = priceAtTime(datetime.datetime(newTime.year, newTime.month, newTime.day, 10, 0), historical)
		# Find price at 10:30 AM
		price1030 = priceAtTime(datetime.datetime(newTime.year, newTime.month, newTime.day, 10, 30), historical)

		correct = 0
		change = round(newPrices - prices, 4)
		percent = 0
		try:
			percent = round((change * 100.0 / prices), 5)
		except:
			pass

		if ((change > 0 and isBull == True) or (change <= 0 and isBull == False)):
			correct = 1

		# If result of any price is a 0
		if (prices == 0 or priceAtPost == 0 or newPrices == 0 or price10 == 0 or price1030 == 0 or newPrices == -1):
			continue

		res.append([symbol, dateTime.strftime("%Y-%m-%d %H:%M:%S"), prices, 
			newPrices, isBull, correct, change, percent, likeCnt, commentCnt, priceAtPost, price10, price1030])

	return res



def analyzeUsers(users, days, path):
	for user in users:
		if (analyzedUserAlready(user)):
			continue

		print(user)
		driver = webdriver.Chrome(executable_path = DRIVER_BIN, chrome_options = chrome_options)
		soup = findPageUser(user, DAYS_BACK, driver)
		path = "userinfo/" + user + ".csv"

		# If the page doesn't have enought bull/bear indicators
		if (soup == None):
			writeSingleList(path, [])
			continue

		result = analyzeUser(user, soup, days)
		stocks = []

		for r in result:
			stocks.append(r[0])

		# stocks = list(set(stocks))
		# addToNewList(stocks, 'stockList.csv')
		writeSingleList(path, result)
		driver.close()

# ------------------------------------------------------------------------
# ----------------------------- Analysis ---------------------------------
# ------------------------------------------------------------------------


def saveStockInfo(result, path):
	currList = []
	with open(path) as f:
		file = f.readlines()
		for i in file:
			x = i.split(',')
			if (x[0] == "\n"):
				continue
			x[3] = float(x[3])
			currList.append(x)

	currList.append(result)
	currList = sorted(currList, key=lambda x: x[3], reverse = True)
	writeSingleList(path, currList)
	return


def analyzeStocksToday(listStocks, date, path, usersPath, folderPath):
	for symbol in listStocks:
		if (analyzedSymbolAlready(symbol, path)):
			continue

		print(symbol)

		users = []
		driver = webdriver.Chrome(executable_path = DRIVER_BIN, chrome_options = chrome_options)
		result = getBearBull(symbol, date, driver)

		bulls = 0
		bears = 0

		for d in result:
			user = d[0]
			bull = d[1]
			users.append(user)
			if (bull):
				bulls += 1
			else:
				bears += 1
		
		bullBearRatio = bulls
		try:
			bullBearRatio = round(bulls / bears, 2)
		except:
			pass

		users = list(set(users))
		addToNewList(users, usersPath)

		tempPath = folderPath + symbol + ".csv"
		writeSingleList(tempPath, result)

		saveStockInfo([symbol, bulls, bears, bullBearRatio], path)
		print("%s: (%d/%d %0.2f)" % (symbol, bulls, bears, bullBearRatio))

		driver.close()

	return


# ------------------------------------------------------------------------
# --------------------------- Main Function ------------------------------
# ------------------------------------------------------------------------


def computeStocksDay(date, processes):
	path = date.strftime("stocksResults/%m-%d-%y.csv")
	folderPath = date.strftime("stocksResults/%m-%d-%y/")
	newUsersPath = date.strftime("newUsers/newUsersList-%m-%d-%y.csv")

	global useDatesSeen
	useDatesSeen = True

	# create empty folder
	if not os.path.exists(folderPath):
	    os.makedirs(folderPath)

	# create empty file
	if (os.path.isfile(path) == False):
		with open(path, "w") as my_empty_csv:
			pass

	if (os.path.isfile(newUsersPath) == False):
		with open(newUsersPath, "w") as my_empty_csv:
			pass

	stocks = readSingleList('stocksActual.csv')
	stocks.sort()

	actual = []
	for i in stocks:
		if (analyzedSymbolAlready(i, path)):
			continue
		else:
			actual.append(i)

	splitEqual = list(chunks(actual, processes))
	pool = Pool()

	for i in range(processes):
		arguments = [splitEqual[i], date, path, newUsersPath, folderPath]
		pool.apply_async(analyzeStocksToday, arguments)

	pool.close()
	pool.join()

	# Extend allNewUsers list
	newUsers = readSingleList('allNewUsers.csv')
	newUsersList = readSingleList(newUsersPath)
	newUsers.extend(newUsersList)
	newUsers = list(map(lambda x: [x], sorted(list(set(newUsers)))))
	writeSingleList('allNewUsers.csv', newUsers)
		


def computeUsersDay(outputPath, inputPath, days, processes):
	users = readSingleList('allNewUsers.csv')
	users.sort()

	actual = []
	for user in users:
		if (analyzedUserAlready(user)):
			continue
		else:
			actual.append(user)

	print('USERS: ', len(actual))

	actual.remove('AngryPanda')

	splitEqual = list(chunks(actual, processes))
	pool = Pool()

	for i in range(processes):
		arguments = [splitEqual[i], days, outputPath]
		pool.apply_async(analyzeUsers, arguments)

	pool.close()
	pool.join()

	createUsersCSV()


def createUsersCSV():
	users = allUsers()
	result = []
	resPath = 'userInfo.csv'

	for user in users:
		path = 'userCalculated/' + user + '_info.csv'
		if (os.path.isfile(path) == False):
			continue

		res = readMultiList(path)
		if (len(res) == 0):
			continue

		res.sort(key = lambda x: x[4], reverse = True)
		res = list(map(lambda x: [x[0], float(x[1]), float(x[2]), float(x[3]), float(x[4])], res))

		total = round(reduce(lambda a, b: a + b, list(map(lambda x: x[4], res))), 4)
		correct = round(reduce(lambda a, b: a + b, list(map(lambda x: x[2], res))), 4)
		incorrect = round(reduce(lambda a, b: a + b, list(map(lambda x: x[3], res))), 4)

		result.append([user, correct, incorrect, total])

	result.sort(key = lambda x: x[3], reverse = True)
	writeSingleList(resPath, result)



# Creates userxxx_info.csv for each user
def statsUsers():
	users = allUsers()

	for user in users:
		path = "userinfo/" + user + ".csv"
		if (os.path.isfile(path) == False):
			continue

		res = []
		read = readMultiList(path)
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


def topUsersStock(stock, num):
	users = allUsers()
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

	(historical, dateTimeAdjusted) = findHistoricalData(date, stock, False)
	priceAtPost = priceAtTime(date, historical) # Price at the time of posting

	stockList.append([dateStock, priceAtPost])
	stockList.sort(key = lambda x: x[0])
	writeSingleList(path, stockList)

	return priceAtPost


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
		#print([symbol, priceAtPost, ratios[i], numStocks])
		
	return stocksNum


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


# Ideal when enough user information collected
def topStocks(date, money, weights):
	numStocks = weights[0]
	uAccW = weights[1]
	uStockAccW = weights[2]
	uPredW = weights[3]
	uStockPredW = weights[4]

	path = date.strftime("stocksResults/%m-%d-%y.csv")
	pathWeighted = date.strftime("stocksResults/%m-%d-%y_weighted.csv")
	folderPath = date.strftime("stocksResults/%m-%d-%y/")

	# if not created yet
	if ((not os.path.exists(folderPath)) or os.path.isfile(path) == False):
	    return

	users = readMultiList('userInfo.csv')
	stocks = readMultiList(path)
	users = list(filter(lambda x: len(x) >= 4, users))
	mappedUsers = set(list(map(lambda x: x[0], users)))
	result = []

	global CREATED_DICT_USERS
	if (CREATED_DICT_USERS == False):
		createDictUsers()
		CREATED_DICT_USERS = True


	# Find weight for each stock
	for s in stocks:
		symbol = s[0]
		resPath = folderPath + symbol + ".csv"
		resSymbol = readMultiList(resPath)
		total = 0

		# scale based on how accurate that user is
		topUsersForStock = readMultiList('templists/' + symbol + '.csv')

		# safety check cuz len(topUsersForStock) must be  > 1
		if (len(topUsersForStock) < 2):
			continue

		try:
			maxPercent = math.log(float(topUsersForStock[0][1]))
		except:
			maxPercent = 0.0
		minPercent = -1 * math.log(abs(float(topUsersForStock[len(topUsersForStock) - 1][1])))

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
			isBull = bool(r[1])

			# Only based no user info's that's been collected
			if (user in mappedUsers):
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

		if (symbol == 'AMD' or symbol == 'TSLA' or symbol == "AMZN"):
			continue
		result.append([symbol, total])

	result.sort(key = lambda x: x[1], reverse = True)
	res = recommendStocks(result, date, money, numStocks)
	writeSingleList(pathWeighted, result)
	
	return res


def writeTempListStocks():
	stocks1 = readSingleList('stocksActual.csv')
	stocks1.sort()
	for s in stocks1:
		res = topUsersStock(s, 0)
		print(s)
		writeSingleList('templists/' + s + '.csv', res)
 


def calcReturnBasedResults(date, result):
	totalsReturns = []
	afterDate = datetime.datetime(date.year, date.month, date.day, 9, 30)
	afterDate += datetime.timedelta(1)
	while (isTradingDay(afterDate) == False):
		afterDate += datetime.timedelta(1)

	for i in range(5):
		if (i % 5 == 0):
			totalReturn = 0
			for x in result:
				symbol = x[0]
				priceBefore = x[1]
				shares = x[3]
				totalBefore = priceBefore * shares
				diff = 0
				priceAfter = savedPricesStocks(afterDate, symbol)

				totalAfter = priceAfter * shares
				diff = totalAfter - totalBefore

				# print(symbol, diff, priceBefore, priceAfter)
				totalReturn += diff

			totalReturn = round(totalReturn, 2)
			totalsReturns.append([totalReturn, afterDate])
			# print(afterDate, totalReturn)
			return totalReturn

		afterDate = afterDate + datetime.timedelta(minutes = 1)


def checkInvalid():
	users = allUsers()
	count = 0

	for name in users:
		l = readMultiList('userInfo/' + name + '.csv')
		res = []

		for r in l:
			four = r[2]
			nine = r[3]
			priceAtPost = r[10]
			ten = r[11]
			ten30 = r[12]
			if (four != '-1' and nine != '-1' and ten != '-1' and ten30 != '-1' and priceAtPost != '-1'):
				continue

			count += 1
	print(count4)




# Find the change in the number of new users each day
def findNewUserChange():
	path = "newUsers/"
	files = [f for f in os.listdir(path) if os.path.isfile(os.path.join(path, f))] 
	files = sorted(list(filter(lambda x: x != '.DS_Store', files)))

	users = []
	prevLen = 0
	for file in files:
		print(file)
		res = readSingleList(path + file)
		res = list(filter(lambda x: len(x) > 0, res))

		users.extend(res)
		users = list(set(users))

		print(len(users) - prevLen)
		prevLen = len(users)


def isTradingDay(date):
	historical = get_historical_intraday('TVIX', date)
	return len(historical) > 0


# Return list of valid trading days from date on
def findTradingDays(date):
	currDate = datetime.datetime.now()
	delta = datetime.timedelta(1)
	dates = []

	while (date < currDate - delta):
		# See if it's a valid trading day
		if (isTradingDay(date)):
			dates.append(date)

		date += delta

	return dates



# TODO
# 1. SHOULD IGNORE DIFF if it is 0? count as correct
# 2. Remove outliers that are obviously not true prices
# 3. Some stocks barely get any users so ignore them and look at others (#1 priority)
# 4. Weight likes/comments into the accuracy of user
# 5. Weight predictions by these and find the argmax
# 	 - the times that it was sold at (9:30, 9:35...)
#	 - how accurate the user is in general, past history of the stock
#	 - number of stocks to pick from (currently 10)
#    - number of total predictions made
#	 - how much the user predicts for that stock
# 6. Figure out why some invalid symbols are not actually invalid
# 7. View which stocks should be removed based on # users
# 8. Implement better caching
# 9. View graph of number of new users added each day to see when feasible to also find user info when predictings
# 10. Find faster way to update templists folder
# 11. Look at past prediction weights and see if there is a huge jump
# 12. Start looking at users throughout day for stocks so bulk of work is done before 4pm
# 13. For dictPredictions, find the middle number of users for prediction rate

def main():
	args = sys.argv
	if (len(args) > 1):
		dayUser = args[1]
		if (dayUser == "day"):
			dateNow = datetime.datetime.now()
			date = datetime.datetime(dateNow.year, 2, 1)
			dates = findTradingDays(date)
			computeStocksDay(date, 3)

			# weights = [9, 0.48, 0.45, 0.64, 1.92]
			
			# res = topStocks(date, 2000, weights)
			# RUN everytime
			# statsUsers()
			# writeTempListStocks()

			# count = 0
			# result = []

			# for i in range(8, 9):
			# 	numStocks = i 
			# 	for j in range(3, 8):
			# 		w1 = j * 0.1
			# 		for k in range(1, 7):
			# 			w2 = k * 0.1
			# 			for l in range(2, 5):
			# 				w3 = l * 0.3
			# 				for m in range(5, 11):
			# 					w4 = m * 0.3

			# 					count += 1
			# 					weights = [numStocks, w1, w2, w3, w4]
			# 					# res = topStocks(date, 2000, weights)
			# 					# foundReturn = calcReturnBasedResults(date, res)
			# 					totalReturn = 0

			# 					for date in dates:
			# 						res = topStocks(date, 2000, weights)
			# 						foundReturn = calcReturnBasedResults(date, res)
			# 						totalReturn += foundReturn

			# 					print(count, totalReturn, weights)
			# 					result.append([count, totalReturn, weights])
			# 					writeSingleList('argMax.csv', result)

			print("hi")
		else:
			computeUsersDay('userInfo.csv', 'allNewUsers.csv', 1, 1)
	else:
		print("rip")

		# findNewUserChange()
		# res = topUsersStock('BIOC', 0)

		helper()


		# dateNow = datetime.datetime.now()
		# date = datetime.datetime(dateNow.year, 1, 14)
		# dates = findTradingDays(date)
		# # dates = [datetime.datetime(dateNow.year, 1, 31)]
		# totalReturn = 0

		# money = 2000
		# for date in dates:
		# 	weights = [9, 0.48, 0.45, 0.64, 1.92]

		# 	res = topStocks(date, money, weights)
		# 	foundReturn = calcReturnBasedResults(date, res)
		# 	print(date, foundReturn)
		# 	totalReturn += foundReturn
		# 	money += foundReturn

		# print(totalReturn)


		# res = readMultiList('argMax.csv')
		# res.sort(key = lambda x: float(x[1]), reverse = True)
		
		# result = []

		# for i in range(20):
		# 	temp = res[i]
		# 	numStocks = int(temp[2][2])
		# 	w1 = round(float(temp[3]), 2)
		# 	w2 = round(float(temp[4]), 2)
		# 	w3 = round(float(temp[5]), 2)
		# 	w4 = round(float(temp[6][:4]), 2)
		# 	temp = [round(float(temp[1]), 2), numStocks, w1, w2, w3, w4]
		# 	print(temp)
		# 	result.append(temp)

		# for i in range(2, 6):
		# 	w1Total = list(map(lambda x: x[i],result))
		# 	avg = sum(w1Total) / len(w1Total)
		# 	print(avg)


if __name__ == "__main__":
	main()