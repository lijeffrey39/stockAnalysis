from bs4 import BeautifulSoup
import time
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
import os
import datetime
from iexfinance.stocks import get_historical_intraday
from dateutil.parser import parse
import json
import csv
import multiprocessing
from multiprocessing import Process, Pool, current_process
import threading
import platform
import sys
from functools import reduce

chrome_options = webdriver.ChromeOptions()
prefs = {"profile.managed_default_content_settings.images": 2}
chrome_options.add_experimental_option("prefs", prefs)
chrome_options.add_argument("--headless")
chrome_options.add_argument('log-level=3')
global_lock = threading.Lock()
cpuCount = multiprocessing.cpu_count()

chromedriverName = 'chromedriver' if (platform.system() == "Darwin") else 'chromedriver.exe'
PROJECT_ROOT = os.getcwd()
DRIVER_BIN = os.path.join(PROJECT_ROOT, chromedriverName)


# SET NAME ATTRIBUTES
priceAttr = 'StockHeader__bid___2BF7L'
messageStreamAttr = 'MessageStreamView__message___2o0za'
timeAttr = 'MessageStreamView__created-at___HsSv2'
usernameAttr = 'MessageStreamView__username___x9n-9'
bullSentAttr = 'SentimentIndicator__SentimentIndicator-bullish___1WHAM SentimentIndicator__SentimentIndicator___3bEpt'
bearSentAttr = 'SentimentIndicator__SentimentIndicator-bearish___2KbIj SentimentIndicator__SentimentIndicator___3bEpt'
userPageAttr = 'UserHeader__username___33aun'
messageTextAttr = 'MessageStreamView__body___2giLh'
likeCountAttr = 'LikeButton__count___1tZ74'
commmentCountAttr = 'StreamItemFooter__count___1YAqr'
messagesCountAttr = 'UserPage__heading____tZJh'


# Make cache for that symbol and date so don't have to keep calling api
# Formatted like {"TVIX": {"2018-12-24": [historical_data], "2018-12-23": [more_data]}
datesSeenGlobal = {} 
useDatesSeen = False

# Invalid symbols so they aren't check again
invalidSymbols = []


# ------------------------------------------------------------------------
# ----------------------- Useful helper functions ------------------------
# ------------------------------------------------------------------------


def removeSpecialCharacters(string):
	return ''.join(e for e in string if e.isalnum())



# Read a single item CSV
def readSingleList(path):
	l = []

	if not os.path.exists(path):
		return l

	with open(path) as f:
		file = f.readlines()
		for i in file:
			l.append(removeSpecialCharacters(i))
	return l


# Read a multi item CSV
def readMultiList(path):
	l = []

	if not os.path.exists(path):
		return l

	with open(path) as f:
		file = f.readlines()
		for i in file:
			x = i.split(',')
			if (x[0] == '\n' or len(x) == 1):
				continue
			for j in range(len(x)):
				# remove new line
				if ('\n' in x[j]):
					x[j] = x[j][:len(x[j]) - 1]
			l.append(x)
	return l


# Write 1d array of items to CSV 
def writeSingleList(path, items):

	while global_lock.locked():
		continue

	global_lock.acquire()

	with open(path, "w+") as my_csv:
	    csvWriter = csv.writer(my_csv, delimiter=',')
	    csvWriter.writerows(items)

	global_lock.release()


# Find time of a message
def findDateTime(message):
	if (message == None):
		return None
	else:
		try:
			dateTime = parse(message)
		except:
			return None
		test = datetime.datetime(2019, 1, 20)
		if (dateTime > test):
			return datetime.datetime(2018, dateTime.month, dateTime.day, dateTime.hour, dateTime.minute)
		return dateTime


# Sroll for # days
def scrollFor(name, days, driver):
	elem = driver.find_element_by_tag_name("body")

	dateTime = datetime.datetime.now() 
	delta = datetime.timedelta(days)
	oldTime = dateTime - delta
	oldTime = datetime.datetime(oldTime.year, oldTime.month, oldTime.day, 9, 30)

	SCROLL_PAUSE_TIME = 1
	time.sleep(SCROLL_PAUSE_TIME)

	last_height = driver.execute_script("return document.body.scrollHeight")
	driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")

	html = driver.page_source
	soup = BeautifulSoup(html, 'html.parser')
	messages = soup.find_all('div', attrs={'class': messageStreamAttr})
	currentCount = len(messages)

	# page doesnt exist
	if (currentCount == 0):
		print("Doesn't Exist")
		return False

	# check every 10 page downs
	count = 1
	modCheck = 1
	analyzingStock = False
	messageCount = driver.find_elements_by_class_name(messagesCountAttr)
	if (len(messageCount) == 0):
		analyzingStock = True
		price = driver.find_elements_by_class_name(priceAttr)
		ActionChains(driver).move_to_element(price[0]).perform()  
	else:	
		ActionChains(driver).move_to_element(messageCount[0]).perform()  

	while(True):
		new_height = driver.execute_script("return document.body.scrollHeight")
		time.sleep(SCROLL_PAUSE_TIME)

		if (count % modCheck == 0):
			for i in range(10):
				driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
				new_height = driver.execute_script("return document.body.scrollHeight")

			messages = driver.find_elements_by_class_name(messageStreamAttr)
			
			if (len(messages) == 0):
				print("Strange Error")
				return False

			modCheck += 1
			lastMessage = messages[len(messages) - 1].text
			t = lastMessage.split('\n')
			if (t[0] == "Bearish" or t[0] == "Bullish"):
				dateTime = findDateTime(t[2])
			else:
				dateTime = findDateTime(t[1])

			print(name, dateTime)
			time.sleep(SCROLL_PAUSE_TIME)
			if (analyzingStock == False and new_height == last_height):
				break

		last_height = new_height
		driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
		count += 1

		if (dateTime < oldTime):
			break


	print("Finished Reading", name)
	return True


# Find username of a message
def findUser(message):
	u = message.find('a', attrs={'class': usernameAttr})

	if (u == None):
		return None
	else:
		user = u['href'][1:]
		return user


def historicalFromDict(symbol, dateTime):
	global invalidSymbols
	historial = []
	dateTimeStr = dateTime.strftime("%Y-%m-%d")

	if (useDatesSeen == False):	
		if (symbol in invalidSymbols):
			return []

		try:
			historical = get_historical_intraday(symbol, dateTime)
			return historical
		except:
			print(symbol)
			invalidSymbols.append(symbol)
			invalidSymbols.sort()

			tempList = []
			for s in invalidSymbols:
				tempList.append([s])

			writeSingleList('invalidSymbols.csv', tempList)

			print("Invalid ticker2")
			return []

	# Find what process is using it
	currentP = current_process().name
	datesSeen = datesSeenGlobal[currentP]

	if (symbol not in datesSeen):
		try:
			historical = get_historical_intraday(symbol, dateTime)
			newSymbolTime = {}
			newSymbolTime[dateTimeStr] = historical
			datesSeen[symbol] = newSymbolTime
		except:
			pass
			print("Invalid ticker1")
			return []
	else:
		datesForSymbol = datesSeen[symbol]
		if (dateTimeStr not in datesForSymbol):
			try:
				historical = get_historical_intraday(symbol, dateTime)
				datesSeen[symbol][dateTimeStr] = historical
			except:
				pass
				print("Invalid ticker")
		else:
			historical = datesSeen[symbol][dateTimeStr]

	datesSeenGlobal[currentP] = datesSeen
	return historical


# Find historical stock data given date and ticker
def findHistoricalData(dateTime, symbol, futurePrice):
	historical = []
	originalDateTime = dateTime

	# if it is a saturday or sunday, find friday's time if futurePrice == False
	# Else find monday's time if it's futurePrice
	if (futurePrice):
		historical = historicalFromDict(symbol, dateTime)
		delta = datetime.timedelta(1)
		# keep going until a day is found
		count = 0
		while (len(historical) == 0):
			dateTime = dateTime + delta
			historical = historicalFromDict(symbol, dateTime)
			count += 1
			if (count == 10):
				historical = []
				dateTime = originalDateTime
				break
	else:
		historical = historicalFromDict(symbol, dateTime)

	return (historical, dateTime)


# Price of a stock at a certain time given historical data
def priceAtTime(dateTime, historical):
    foundAvg = ""
    found = False
    for ts in historical:
        if (int(ts.get("minute").replace(":","")) >= int((dateTime.strftime("%X")[:5]).replace(":",""))):
            foundAvg = ts.get('average')
            foundAvg1 = ts.get('marketAverage')
            if (foundAvg != -1):
            	found = True
            	break
            else:
            	if (foundAvg1 != -1):
            		found = True
            		foundAvg = foundAvg1
            		break
            	else:
                	continue

    if (found == False):
        last = historical[len(historical) - 1]
        foundAvg = last.get('average')

    return foundAvg


def likeCount(message):
	count = message.find('span', attrs={'class': likeCountAttr})
	if (count == None):
		return 0
	else:
		return int(count.text)


def commentCount(message):
	count = message.find('span', attrs={'class': commmentCountAttr})
	if (count == None):
		return 0
	else:
		return int(count.text)

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

	with open(path, "w") as file:
	    file.write(str(soup))

	return (soup, False)


def inTradingHours(dateTime, symbol):
	day = dateTime.weekday()
	nineAM = datetime.datetime(dateTime.year, dateTime.month, dateTime.day, 9, 30)
	fourPM = datetime.datetime(dateTime.year, dateTime.month, dateTime.day, 16, 0)

	if (dateTime < nineAM or dateTime >= fourPM or day == "0" or day == "6"):
		return False

	historical = historicalFromDict(symbol, dateTime)
	strDate = dateTime.strftime("%X")[:5]
	found = False

	for ts in historical:
		if (ts.get('minute') == strDate):
			found = True

	return found


# True if bull
def isBullMessage(message):
	bull = message.find('span', attrs={'class': bullSentAttr})
	bear = message.find('span', attrs={'class': bearSentAttr})

	if (bull == None and bear == None):
		return None

	if (bull):
		return True 
	else: 
		return False


def isValidMessage(dateTime, dateNow, isBull, user, symbol, daysInFuture):
	if (dateTime == None):
		return False

	dateCheck = datetime.datetime(dateTime.year, dateTime.month, dateTime.day)
	dateNow = datetime.datetime(dateNow.year, dateNow.month, dateNow.day)

	delta = datetime.timedelta(daysInFuture)
	newTime = dateTime + delta
	# If the next day at 9:30 am is < than the current time, then there is a stock price
	newTime = datetime.datetime(newTime.year, newTime.month, newTime.day, 9, 30)
	newTimeDay = newTime.weekday()

	if (user == None or 
		isBull == None or 
		symbol == None or
		inTradingHours(dateTime, symbol) == False or
		(daysInFuture == 0 and dateCheck != dateNow) or
		(daysInFuture > 0 and newTime > dateNow) or
		(dateCheck > dateNow)): 
		return False
	return True


def getBearBull(symbol, date, driver):
	# For caching
	processName = current_process().name
	datesSeenGlobal[processName] = {}

	dateNow = datetime.datetime.now()
	days = (dateNow - date).days

	(soup, error) = findPageStock(symbol, days, driver)

	if (error):
		return []

	messages = soup.find_all('div', attrs={'class': messageStreamAttr})
	res = []

	for m in messages:
		t = m.find('a', attrs={'class': timeAttr})
		textM = m.find('div', attrs={'class': messageTextAttr})
		dateTime = findDateTime(t.text)
		user = findUser(m)
		isBull = isBullMessage(m)

		if (isValidMessage(dateTime, date, isBull, user, symbol, 0) == False):
			continue

		(historical, dateTimeAdjusted1) = findHistoricalData(dateTime, symbol, False)
		foundAvg = priceAtTime(dateTime, historical) # fix this function to take dateTimeadjusted

		messageInfo = [user, isBull, dateTimeAdjusted1, foundAvg, textM]
		res.append(messageInfo)

	return res



# ------------------------------------------------------------------------
# ----------------------- Analyze Specific User --------------------------
# ------------------------------------------------------------------------



def addNewStocks(stocks):
	currList = readSingleList('stockList.csv')
	currList.extend(stocks)
	currList = list(set(currList))
	currList.sort()

	for i in range(len(currList)):
		currList[i] = [currList[i]]

	writeSingleList("stockList.csv", currList)


def findSymbol(message):
	textM = message.find('div', attrs={'class': messageTextAttr})
	spans = textM.find_all('span')

	tickers = []
	foundTicker = False
	for s in spans:
		foundA = s.find('a')
		ticker = foundA.text

		if ('@' in ticker or '#' in ticker or '.X' in ticker):
			continue

		tickers.append(ticker[1:])

		if ("$" in ticker):
			foundTicker = True

	# Never found a ticker or more than 1 ticker
	if (foundTicker == False or len(tickers) > 1):
		return None
	else:
		return tickers[0]


def findPricesTickers(symbol, dateTime, futurePrice):

	(historical, dateTimeAdjusted) = findHistoricalData(dateTime, symbol, futurePrice)
	if (len(historical) == 0):
		return (0, True)

	foundAvg = priceAtTime(dateTime, historical)
	return (foundAvg, False)


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

	# with open(path, "w") as file:
	#     file.write(str(soup))

	return soup



def analyzeUser(username, soup, daysInFuture, beginningOfDay):
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

		(prices, noDataTicker) = findPricesTickers(symbol, dateTime, False)

		# Find price after # days
		delta = datetime.timedelta(daysInFuture)
		newTime = dateTime + delta

		# Find time at 9:30 am
		if (beginningOfDay):
			newTime = datetime.datetime(newTime.year, newTime.month, newTime.day, 9, 30)

		(newPrices, noDataTicker) = findPricesTickers(symbol, newTime, True)

		correct = 0
		change = round(newPrices - prices, 4)
		percent = 0
		try:
			percent = round((change * 100.0 / prices), 5)
		except:
			pass

		if ((change > 0 and isBull == True ) or (change <= 0 and isBull == False)):
			correct = 1

		res.append([symbol, dateTime.strftime("%Y-%m-%d %H:%M:%S"), prices, 
			newPrices, isBull, correct, change, percent, likeCnt, commentCnt])

	return res



def saveUserInfo(username, result, otherInfo):

	path1 = "userinfo/" + username + ".csv"
	writeSingleList(path1, result)

	createUsersCSV()

	# path2 = "users.csv"
	# # Check to see if username already exists
	# l = []
	# newResult = []
	# with open(path2) as f:
	# 	file = f.readlines()
	# 	for i in file:
	# 		x = i.split(',')
	# 		if (x[0] == "\n"):
	# 			continue
	# 		l.append(x[0])
	# 		newResult.append(x)

	# if (username not in l):
	# 	newResult.append(otherInfo)
	# else:
	# 	for i in range(len(newResult)):
	# 		if (newResult[i][0] == username):
	# 			newResult[i] = otherInfo
	# 			break

	# for i in range(len(newResult)):
	# 		newResult[i][3] = float(newResult[i][3])
	# sortedResult = sorted(newResult, key=lambda x: x[3], reverse = True)
	# writeSingleList(path2, sortedResult)


def analyzedAlready(name, path):
	# Check to see if username already exists
	users = readMultiList(path)
	filtered = filter(lambda x: len(x) >= 2, users)
	mappedUsers = map(lambda x: x[0], filtered)

	return (name in mappedUsers)


def analyzeResultsUser(username, days, driver):
	print(username)
	soup = findPageUser(username, 36, driver)

	# If the page doesn't have enought bull/bear indicators
	if (soup == None):
		saveUserInfo(username, [], [username, 0, 0, 0])
		return False

	result = analyzeUser(username, soup, days, True)

	ratio = 0
	totalGood = 0
	totalBad = 0
	stocks = []

	for r in result:
		print(r)
		percent = abs(r[7])
		stocks.append(r[0])
		if (r[5] == True):
			totalGood += 1
			ratio += percent
		else:
			totalBad += 1
			ratio -= percent	

	stocks = list(set(stocks))
	otherInfo = [username, totalGood, totalBad, round(ratio, 4)]

	addNewStocks(stocks)
	saveUserInfo(username, result, otherInfo)

	return True


def analyzeUsers(users, days, path):

	for user in users:
		if (analyzedAlready(user, path)):
			continue
		driver = webdriver.Chrome(executable_path = DRIVER_BIN, chrome_options = chrome_options)
		analyzeResultsUser(user, days, driver)
		driver.close()

# ------------------------------------------------------------------------
# ----------------------------- Analysis ---------------------------------
# ------------------------------------------------------------------------


def readUsers(path):
	l = []
	with open(path) as f:
		file = f.readlines()
		for i in file:
			# x = i.split(',')
			# for j in range(len(x)):
			# 	x[j] = ''.join(e for e in x[j] if e.isalnum())
			# l.append(x[0])
			l.append(removeSpecialCharacters(i))
	return l


def addToNewList(users, path):
	currList = readUsers(path)
	currList.extend(users)
	currList = list(set(currList))
	currList.sort()

	for i in range(len(currList)):
		currList[i] = [currList[i]]

	writeSingleList(path, currList)


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
		if (analyzedAlready(symbol, path)):
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


def analyzeStocksHistory(listStocks, daysBack, usersPath, driver):
	result = []

	for symbol in listStocks:
		res = getBearBull(symbol, daysBack, driver)

		bulls = 0
		bears = 0
		users = []

		for d in res:
			print(d)
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

		result.append([symbol, bulls, bears, bullBearRatio])
		users = list(set(users))
		print(users)
		addToNewList(users, usersPath)

	driver.close()

	return result 



# ------------------------------------------------------------------------
# --------------------------- Main Function ------------------------------
# ------------------------------------------------------------------------


def chunks(seq, size):
    return (seq[i::size] for i in range(size))


def computeStocksDay(date, processes):

	path = date.strftime("stocksResults/%m-%d-%y.csv")
	folderPath = date.strftime("stocksResults/%m-%d-%y/")
	newUsersPath = date.strftime("newUsers/newUsersList-%m-%d-%y.csv")

	# analyzeStocksToday(['AAPL'], date, path, newUsersPath, folderPath)

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

	global useDatesSeen
	useDatesSeen = True

	stocks = readSingleList('stocksActual.csv')
	stocks.sort()
	splitEqual = list(chunks(stocks, processes))

	pool = Pool()

	for i in range(processes):
		arguments = [splitEqual[i], date, path, newUsersPath, folderPath]
		pool.apply_async(analyzeStocksToday, arguments)

	pool.close()
	pool.join()


def computeUsersDay(outputPath, inputPath, days, processes):

	users = readSingleList('allNewUsers.csv')
	users = list(set(users))
	users.sort()
	print(len(users))

	splitEqual = list(chunks(users, processes))
	allProcesses = []

	for i in range(processes):
		arguments = [splitEqual[i], days, outputPath]
		allProcesses.append(Process(target = analyzeUsers, args = arguments))

	for p in allProcesses:
		p.start()

	for p in allProcesses:
		p.join()


def createUsersCSV():
	path = "userinfo/"
	resPath = "userInfo.csv"
	files = [f for f in os.listdir(path) if os.path.isfile(os.path.join(path, f))] 
	names = list(map(lambda x: x[:len(x) - 4], files))
	result = []

	for user in names:
		# if (user != "Rocketman810"):
		# 	continue
		path = "userinfo/" + user + ".csv"
		res = []

		read = readMultiList(path)

		if (len(read) == 0):
			continue

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
		total = round(reduce(lambda a, b: a + b, list(map(lambda x: x[4], res))), 4)
		correct = round(reduce(lambda a, b: a + b, list(map(lambda x: x[2], res))), 4)
		incorrect = round(reduce(lambda a, b: a + b, list(map(lambda x: x[3], res))), 4)

		result.append([user, correct, incorrect, total])

	result.sort(key = lambda x: x[3], reverse = True)
	writeSingleList(resPath, result)


def statsUsers():
	users = readMultiList('users.csv')
	filtered = filter(lambda x: len(x) >= 4, users)
	mappedUsers = map(lambda x: x[0], filtered)

	for user in mappedUsers:
		path = "userinfo/" + user + ".csv"
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
		total = round(reduce(lambda a, b: a + b, list(map(lambda x: x[4], res))), 4)

		writeSingleList('userinfo/' + user + '_info.csv', res)


def topUsersStock(stock, num):
	users = readMultiList('users.csv')
	filtered = list(filter(lambda x: len(x) >= 4, users))
	mappedUsers = list(map(lambda x: x[0], filtered))
	result = []

	for user in mappedUsers:
		path = 'userinfo/' + user + '_info.csv'
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


# Ideal when enough user information collected
def topStocks(date):
	path = date.strftime("stocksResults/%m-%d-%y.csv")
	pathWeighted = date.strftime("stocksResults/%m-%d-%y_weighted.csv")
	folderPath = date.strftime("stocksResults/%m-%d-%y/")

	# if not created yet
	if ((not os.path.exists(folderPath)) or os.path.isfile(path) == False):
	    return

	users = readMultiList('usersinfo.csv')
	filtered = list(filter(lambda x: len(x) >= 4, users))

	maxPercent = float(filtered[0][3])
	minPercent = float(filtered[len(filtered) - 1][3])

	dict = {}
	for l in filtered:
		percent = float(l[3])
		if (percent > 0):
			dict[l[0]] = (maxPercent - percent) / maxPercent
		else:
			dict[l[0]] = -1 * (minPercent - percent) / minPercent

	mappedUsers = set(list(map(lambda x: x[0], filtered)))
	stocks = readMultiList(path)
	result = []

	for s in stocks:
		symbol = s[0]
		resPath = folderPath + symbol + ".csv"
		resSymbol = readMultiList(resPath)
		total = 0

		# scale based on how accurate that user is
		topUsersForStock = topUsersStock(symbol, 0)

		# safety check cuz len(topUsersForStock) must be  > 1
		maxPercent = float(topUsersForStock[0][11])
		minPercent = float(topUsersForStock[len(topUsersForStock) - 1][1])

		topUserDict = {}
		for u in topUsersForStock:
			user = u[0]
			percent = u[1]
			if (percent > 0):
				topUserDict[user] = (maxPercent - percent) / maxPercent
			else:
				topUserDict[user] = -1 * (minPercent - percent) / minPercent

		for r in resSymbol:
			user = r[0]
			isBull = bool(r[1])

			# Only based no user info's that's been collected
			if (user in mappedUsers):
				if (isBull):
					total += dict[user]
				else:
					total -= dict[user]

			# Secondary weighting based on how accurate that user is for specific stocks
			if (user in topUserDict):
				if (isBull):
					total += topUserDict[user]
				else:
					total -= topUserDict[user]

		result.append([symbol, total])

	result.sort(key = lambda x: x[1], reverse = True)
	writeSingleList(pathWeighted, result)
	
	return

# TODO
# - Use list of users to find new stocks 
# - Find jumps in stocks of > 10% for the next day and see which users were the best at predicting these jumps
# - Add caching


def main():
	args = sys.argv
	if (len(args) > 1):
		dayUser = args[1]
		if (dayUser == "day"):
			dateNow = datetime.datetime.now()
			date = datetime.datetime(dateNow.year, dateNow.month, dateNow.day)
			date = datetime.datetime(2019, 1, 14)
			computeStocksDay(date, cpuCount - 1)
			# topStocks(date)
			print("hi")
		else:
			computeUsersDay('usersinfo.csv', 'allNewUsers.csv', 1, 2)
	else:
		print("rip")
		# date = datetime.datetime(2019, 1, 11)
		# computeStocksDay(date, cpuCount - 1)

		# res = topUsersStock('APHA', 0)
		# print(res)
		# for r in res:
		# 	print(r)
		createUsersCSV()







if __name__ == "__main__":
	main()