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
from multiprocessing import Process

chrome_options = webdriver.ChromeOptions()
prefs = {"profile.managed_default_content_settings.images": 2}
chrome_options.add_experimental_option("prefs", prefs)

PROJECT_ROOT = os.getcwd()
DRIVER_BIN = os.path.join(PROJECT_ROOT, "chromedriver.exe")


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
datesSeen = {} 
useDatesSeen = False

# Invalid symbols so they aren't check again
invalidSymbols = []


# ------------------------------------------------------------------------
# ----------------------- Useful helper functions ------------------------
# ------------------------------------------------------------------------


# Read a single item CSV
def readSingleList(path):
	l = []
	with open(path) as f:
		file = f.readlines()
		for i in file:
			l.append(''.join(e for e in i if e.isalnum()))
	return l


# Write 1d array of items to CSV 
def writeSingleList(path, items):
	with open(path, "w+") as my_csv:
	    csvWriter = csv.writer(my_csv, delimiter=',')
	    csvWriter.writerows(items)


# Find time of a message
# TODO : add error checking to this (ValueError: day is out of range for month) for parse()
def findDateTime(message):
	if (message == None):
		return None
	else:
		try:
			dateTime = parse(message)
		except:
			return None
		test = datetime.datetime(2019, 1, 15)
		if (dateTime > test):
			return datetime.datetime(2018, dateTime.month, dateTime.day, dateTime.hour, dateTime.minute)
		return dateTime


# Sroll for # days
def scrollFor(days, minBullBear, driver):
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

	while (oldTime < dateTime):

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

			print(dateTime)
			time.sleep(SCROLL_PAUSE_TIME)
			if (analyzingStock == False and new_height == last_height):
			    break

		last_height = new_height
		driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")

		count += 1

	print("Finished Reading")
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
def findPageStock(symbol, daysInFuture, driver):

	# if html is stored
	path = 'stocks/' + symbol + '.html'
	if (os.path.isfile(path)):
		print("File Exists")
		# html = open(path, "r")
		soup = BeautifulSoup(open(path), 'html.parser')
		print("Finished Reading in")
		return (soup, False)

	url = "https://stocktwits.com/symbol/" + symbol
	driver.get(url)
	foundEnough = scrollFor(daysInFuture, 5, driver)

	if (foundEnough == False):
		return (None, True)

	html = driver.page_source
	soup = BeautifulSoup(html, 'html.parser')

	# with open(path, "w") as file:
	#     file.write(str(soup))

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
	dateNowCheck = datetime.datetime(dateNow.year, dateNow.month, dateNow.day, 23, 59)

	delta = datetime.timedelta(daysInFuture)
	newTime = dateTime + delta
	# If the next day at 9:30 am is < than the current time, then there is a stock price
	newTime = datetime.datetime(newTime.year, newTime.month, newTime.day, 9, 30)
	newTimeDay = newTime.weekday()

	if (user and isBull and symbol and inTradingHours(dateTime, symbol)):
		print(user, isBull, symbol, dateTime)

	if (user == None or 
		isBull == None or 
		symbol == None or
		inTradingHours(dateTime, symbol) == False or
		(daysInFuture == 0 and dateCheck != dateNow) or
		(daysInFuture > 0 and newTime > dateNow) or
		(dateCheck > dateNow)): 
		return False
	return True


def getBearBull(symbol, daysInFuture, driver):
	(soup, error) = findPageStock(symbol, daysInFuture, driver)

	if (error):
		return []

	dateNow = datetime.datetime.now()
	messages = soup.find_all('div', attrs={'class': messageStreamAttr})
	res = []
	
	for m in messages:
		t = m.find('a', attrs={'class': timeAttr})
		dateTime = findDateTime(t.text)
		user = findUser(m)
		isBull = isBullMessage(m)

		if (isValidMessage(dateTime, dateNow, isBull, user, symbol, 0) == False):
			continue

		(historical, dateTimeAdjusted1) = findHistoricalData(dateTime, symbol, False)
		foundAvg = priceAtTime(dateTime, historical) # fix this function to take dateTimeadjusted

		messageInfo = [user, isBull, dateTimeAdjusted1, foundAvg]
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
def findPageUser(username, driver):

	# if html is stored
	path = 'usersPages/' + username + '.html'
	if (os.path.isfile(path)):
		print("File Exists")
		# html = open(path, "r")
		soup = BeautifulSoup(open(path), 'html.parser')
		return soup

	url = "https://stocktwits.com/" + username
	driver.get(url)
	foundEnough = scrollFor(36, 5, driver)

	if (foundEnough == False):
		return None

	html = driver.page_source
	soup = BeautifulSoup(html, 'html.parser')

	# with open(path, "w") as file:
	#     file.write(str(soup))

	return soup



def analyzeUser(username, soup, days, beginningOfDay):
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

		if (isValidMessage(dateTime, dateNow, isBull, user, symbol, days) == False):
			continue

		(prices, noDataTicker) = findPricesTickers(symbol, dateTime, False)

		# Find price after # days
		delta = datetime.timedelta(days)
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
	path2 = "users.csv"

	with open(path1, "w") as my_csv:
	    csvWriter = csv.writer(my_csv, delimiter=',')
	    csvWriter.writerows(result)

	# Check to see if username already exists
	l = []
	newResult = []
	with open(path2) as f:
		file = f.readlines()
		for i in file:
			x = i.split(',')
			if (x[0] == "\n"):
				continue
			l.append(x[0])
			newResult.append(x)

	if (username not in l):
		newResult.append(otherInfo)
	else:
		for i in range(len(newResult)):
			if (newResult[i][0] == username):
				newResult[i] = otherInfo
				break

	for i in range(len(newResult)):
			newResult[i][3] = float(newResult[i][3])
	sortedResult = sorted(newResult, key=lambda x: x[3], reverse = True)
	writeSingleList(path2, sortedResult)


def analyzedAlready(username, path):
	# Check to see if username already exists
	l = []
	with open(path) as f:
		file = f.readlines()
		for i in file:
			x = i.split(',')
			l.append(x[0])

	return (username in l)


def analyzeResultsUser(username, days, driver):
	print(username)
	soup = findPageUser(username, driver)

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
			x = ''.join(e for e in i if e.isalnum())
			l.append(x)
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
	# Add error checking for x[3] (empty lines at end)
	currList = []
	with open(path) as f:
		file = f.readlines()
		for i in file:
			x = i.split(',')
			x[3] = float(x[3])
			currList.append(x)

	currList.append(result)
	currList = sorted(currList, key=lambda x: x[3], reverse = True)
	writeSingleList(path, currList)
	return


def analyzeStocksToday(listStocks, path, usersPath, driver):
	result = []

	for symbol in listStocks:
		if (analyzedAlready(symbol, path)):
			continue

		print(symbol)

		users = []
		res = getBearBull(symbol, 0, driver)

		bulls = 0
		bears = 0

		for d in res:
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
		addToNewList(users, usersPath)
		saveStockInfo([symbol, bulls, bears, bullBearRatio], path)
		print("%s: (%d/%d %0.2f)" % (symbol, bulls, bears, bullBearRatio))

		driver.close()
		driver = webdriver.Chrome(executable_path = DRIVER_BIN, chrome_options = chrome_options)

	driver.close()
	return result


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

		global datesSeen
		datesSeen = {}

	driver.close()

	return result 



# ------------------------------------------------------------------------
# --------------------------- Main Function ------------------------------
# ------------------------------------------------------------------------


def chunks(seq, size):
    return (seq[i::size] for i in range(size))


def computeStocksDay(path, processes):
	newUsersPath = "newUsers/newUsersList-1-10-2019.csv"

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
	allProcesses = []

	for i in range(processes):
		driver = webdriver.Chrome(executable_path = DRIVER_BIN, chrome_options = chrome_options)
		arguments = [splitEqual[i], path, newUsersPath, driver]
		allProcesses.append(Process(target = analyzeStocksToday, args = arguments))

	for p in allProcesses:
		p.start()

	for p in allProcesses:
		p.join()


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



# TODO
# - Store information for each day for each stock
# - Use list of users to find new stocks 
# - Find jumps in stocks of > 10% for the next day and see which users were the best at predicting these jumps
# - Add caching


def main():

	global invalidSymbols
	invalidSymbols = readSingleList('invalidSymbols.csv')

	# computeStocksDay('stocksResults/1-10-2019.csv', 2)
	computeUsersDay('users.csv', 'allNewUsers.csv', 1, 2)

	# driver = webdriver.Chrome(executable_path = DRIVER_BIN, chrome_options = chrome_options)
	# analyzeResultsUser('NineFingerMike', 1, driver)

	# analyzeStocksHistory(l, 3, newUsersPath, driver)

	# driver.close()

if __name__ == "__main__":
	main()