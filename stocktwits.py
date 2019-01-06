from bs4 import BeautifulSoup
import time
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
import os
import datetime
from iexfinance.stocks import get_historical_intraday
from dateutil.parser import parse
import json
import csv

chrome_options = webdriver.ChromeOptions()
prefs = {"profile.managed_default_content_settings.images": 2}
chrome_options.add_experimental_option("prefs", prefs)

PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))
DRIVER_BIN = os.path.join(PROJECT_ROOT, "chromedriver")
driver = webdriver.Chrome(executable_path = DRIVER_BIN, chrome_options=chrome_options)


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


# Make cache for that symbol and date so don't have to keep calling api
# Formatted like {"TVIX": {"2018-12-24": [historical_data], "2018-12-23": [more_data]}
datesSeen = {} 
useDatesSeen = False


# ------------------------------------------------------------------------
# ----------------------- Useful helper functions ------------------------
# ------------------------------------------------------------------------


# Sroll down until length
def scroll(length):
	elem = driver.find_element_by_tag_name("body")

	for i in range(length):
		elem.send_keys(Keys.PAGE_DOWN)
		time.sleep(0.2)


# Find time of a message
def findDateTime(message):
	t = message.find('a', attrs={'class': timeAttr})

	if (t == None):
		return None
	else:
		dateTime = parse(t.text)
		test = datetime.datetime(2019, 2, 1)
		if (dateTime > test):
			return datetime.datetime(2018, dateTime.month, dateTime.day, dateTime.hour, dateTime.minute)
		return dateTime


# Sroll for # days
def scrollFor(days, minBullBear):
	elem = driver.find_element_by_tag_name("body")

	dateTime = datetime.datetime.now() 
	delta = datetime.timedelta(days)
	oldTime = dateTime - delta
	oldTime = datetime.datetime(oldTime.year, oldTime.month, oldTime.day, 9, 30)

	soup = None
	prevSoup = None # Used to see if it ever scrolls to end of page

	# check every 10 page downs
	count = 0

	while (oldTime < dateTime):
		count += 1
		elem.send_keys(Keys.PAGE_DOWN)

		if (count == 50):
			html = driver.page_source
			soup = BeautifulSoup(html, 'html.parser')
			messages = soup.find_all('div', attrs={'class': messageStreamAttr})

			# page doesnt exist
			if (len(messages) == 0):
				return False

			lastMessage = messages[len(messages) - 1]
			dateTime = findDateTime(lastMessage)
			count = 0

			# If reached bottom of the page, the prev page should look the same
			if (prevSoup == soup):
				return True

			prevSoup = soup

	# Make sure count of bull/bear tags are over certain number
	messages = soup.find_all('div', attrs={'class': messageStreamAttr})
	countBullBear = 0

	for m in messages:
		bull = m.find('span', attrs={'class': bullSentAttr})
		bear = m.find('span', attrs={'class': bearSentAttr})
		
		if (bull or bear):
			countBullBear += 1

	# If less than number of min, keep scrolling, else leave loop
	while (countBullBear < minBullBear):
		count += 1
		elem.send_keys(Keys.PAGE_DOWN)

		if (count == 50):
			count = 0
			countBullBear = 0
			html = driver.page_source
			soup = BeautifulSoup(html, 'html.parser')

			# If reached bottom of the page, the prev page should look the same
			if (prevSoup == soup):
				return False

			messages = soup.find_all('div', attrs={'class': messageStreamAttr})
			for m in messages:
				bull = m.find('span', attrs={'class': bullSentAttr})
				bear = m.find('span', attrs={'class': bearSentAttr})

				if (bull or bear):
					countBullBear += 1

			prevSoup = soup

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
	historial = []
	dateTimeStr = dateTime.strftime("%Y-%m-%d")

	if (useDatesSeen == False):
		try:
			historical = get_historical_intraday(symbol, dateTime)
			return historical
		except:
			pass
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

	# if it is a saturday or sunday, find friday's time if futurePrice == False
	# Else find monday's time if it's futurePrice
	if (futurePrice):
		historical = historicalFromDict(symbol, dateTime)
		delta = datetime.timedelta(1)
		# keep going until a day is found
		while (len(historical) == 0):
			dateTime = dateTime + delta
			historical = historicalFromDict(symbol, dateTime)
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
def findPageStock(symbol, daysInFuture):

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
	foundEnough = scrollFor(daysInFuture, 5)

	if (foundEnough == False):
		return (None, True)

	html = driver.page_source
	soup = BeautifulSoup(html, 'html.parser')

	with open(path, "w") as file:
	    file.write(str(soup))

	return (soup, False)


def inTradingHours(dateTime, symbol):
	day = dateTime.strftime("%w")
	historical = historicalFromDict(symbol, dateTime)
	strDate = dateTime.strftime("%X")[:5]
	found = False

	for ts in historical:
		if (ts.get('minute') == strDate):
			found = True

	# if it's a weekend, ignore
	if (day == "6" or day == "0" or found == False):
		return False

	return True 


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
	dateCheck = datetime.datetime(dateTime.year, dateTime.month, dateTime.day)
	dateNow = datetime.datetime(dateNow.year, dateNow.month, dateNow.day)

	delta = datetime.timedelta(daysInFuture)
	newTime = dateTime + delta
	# If the next day at 9:30 am is < than the current time, then there is a stock price
	newTime = datetime.datetime(newTime.year, newTime.month, newTime.day, 9, 30)

	if (dateTime == None or 
		user == None or 
		isBull == None or 
		symbol == None or
		inTradingHours(dateTime, symbol) == False or
		# (daysInFuture == 0 and dateCheck != dateNow) or
		(daysInFuture > 0 and newTime > dateNow) or
		(dateCheck > dateNow)): 
		return False
	return True


def getBearBull(symbol, daysInFuture):
	(soup, error) = findPageStock(symbol, daysInFuture)

	if (error):
		return []

	dateNow = datetime.datetime.now()
	messages = soup.find_all('div', attrs={'class': messageStreamAttr})
	res = []
	
	for m in messages:
		dateTime = findDateTime(m)
		user = findUser(m)
		isBull = isBullMessage(m)

		if (isValidMessage(dateTime, dateNow, isBull, user, symbol, daysInFuture) == False):
			continue


		(historical, dateTimeAdjusted1) = findHistoricalData(dateTime, symbol, False)
		foundAvg = priceAtTime(dateTime, historical) # fix this function to take dateTimeadjusted

		# If only looking for current day's prices
		if (daysInFuture == 0):
			messageInfo = [user, isBull, dateTimeAdjusted1, foundAvg]
			res.append(messageInfo)
			continue

		# Find price after # days
		delta = datetime.timedelta(daysInFuture)
		newTime = dateTime + delta
		newTime = datetime.datetime(newTime.year, newTime.month, newTime.day, 9, 30)

		(historical, dateTimeAdjusted2) = findHistoricalData(newTime, symbol, True)
		newFoundAvg = priceAtTime(newTime, historical)

		change = abs(newFoundAvg - foundAvg)
		correct = False

		if ((change > 0 and bull) or (change <= 0 and bull == False)):
			correct = True

		messageInfo = [user, isBull, dateTimeAdjusted1, foundAvg, dateTimeAdjusted2, correct, change]
		res.append(messageInfo)

	return res



# ------------------------------------------------------------------------
# ----------------------- Analyze Specific User --------------------------
# ------------------------------------------------------------------------




def readStocks():
	l = []
	with open('stockList.csv') as f:
		file = f.readlines()
		for i in file:
			x = ''.join(e for e in i if e.isalnum())
			l.append(x)

	return l


def writeStocks(stocks):
	with open("stockList.csv","w+") as my_csv:
	    csvWriter = csv.writer(my_csv, delimiter=',')
	    csvWriter.writerows(stocks)


def addNewStocks(stocks):
	currList = readStocks()
	currList.extend(stocks)
	currList = list(set(currList))
	currList.sort()

	for i in range(len(currList)):
		currList[i] = [currList[i]]

	writeStocks(currList)


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
def findPageUser(username):

	# if html is stored
	path = 'usersPages/' + username + '.html'
	if (os.path.isfile(path)):
		print("File Exists")
		# html = open(path, "r")
		soup = BeautifulSoup(open(path), 'html.parser')
		return soup

	url = "https://stocktwits.com/" + username
	driver.get(url)
	foundEnough = scrollFor(30, 5)

	if (foundEnough == False):
		return None

	html = driver.page_source
	soup = BeautifulSoup(html, 'html.parser')

	with open(path, "w") as file:
	    file.write(str(soup))

	return soup



def analyzeUser(username, soup, days, beginningOfDay):
	messages = soup.find_all('div', attrs={'class': messageStreamAttr})
	dateNow = datetime.datetime.now()
	res = []

	for m in messages:
		dateTime = findDateTime(m)
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
		percent = round(change / prices, 4)

		if((change > 0 and isBull == True ) or (change <= 0 and isBull == False)):
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
			l.append(x[0])
			newResult.append(x)

	if (username not in l):
		newResult.append(otherInfo)
		sortedResult = sorted(result, key=lambda x: x[3], reverse = True)

		with open(path2, 'a') as f1:
		    writer = csv.writer(f1)
		    writer.writerows(sortedResult)


def analyzeResultsUser(username, days):
	soup = findPageUser(username)

	# If the page doesn't have enought bull/bear indicators
	if (soup == None):
		return False

	result = analyzeUser(username, soup, days, True)

	ratio = 0
	totalGood = 0
	totalBad = 0

	print(username)
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



# ------------------------------------------------------------------------
# ----------------------------- Analysis ---------------------------------
# ------------------------------------------------------------------------


def readUsers():
	l = []
	with open('newUsersList.csv') as f:
		file = f.readlines()
		for i in file:
			# x = i.split(',')
			# for j in range(len(x)):
			# 	x[j] = ''.join(e for e in x[j] if e.isalnum())
			# l.append(x[0])

			x = ''.join(e for e in i if e.isalnum())
			l.append(x)

	return l


def writeUsers(users):
	with open("newUsersList.csv","w+") as my_csv:
	    csvWriter = csv.writer(my_csv, delimiter=',')
	    csvWriter.writerows(users)


def addToNewList(users):
	currList = readUsers()
	currList.extend(users)
	currList = list(set(currList))
	currList.sort()

	for i in range(len(currList)):
		currList[i] = [currList[i]]

	writeUsers(currList) 


def analyzeStocksToday(listStocks):
	result = []

	for symbol in listStocks:
		res = []
		users = []
		print(symbol)
		res = getBearBull(symbol, 0)
		# try:
		# 	res = getBearBull(symbol, 0)
		# except:
		# 	print("ERROR")
		# 	continue

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
		addToNewList(users)

	return result


def pickStocks(result, cutOff):
	sort = sorted(result, key=lambda x: x[3], reverse = True)
	filtered = filter(lambda x: x[3] > cutOff,sort)

	for res in filtered:
		symbol = res[0]
		bulls = res[1]
		bears = res[2]
		bullBearRatio = res[3]
		print("%s: (%d/%d %0.2f)" % (symbol, bulls, bears, bullBearRatio))



def analyzeStocksHistory(listStocks, daysBack):
	result = []

	for i in l:
		res = []
		try:
			res = getBearBull(i, daysBack)
			if (len(res) == 0):
				print("error occured")
				continue
		except:
			continue

		correctCount = 0
		for d in res:
			c = d[1]
			w = d[2]
			bull = d[3]
			bear = d[4]

			correctRatio = 0
			bullBearRatio = 0
			try:
				# correctRatio = round(c / w, 2)
				bullBearRatio = round(bull / bear, 2)
			except:
				bullBearRatio = bull
				pass

			if (correctRatio > 1 or (c > 0 and w == 0)):
				correctCount += 1

			# print("%s: (%d/%d %0.2f), (%d/%d %0.2f)" % (d[0], c, w, correctRatio, bull, bear, bullBearRatio))

			print("")
			print(i, bull, bear, bullBearRatio)
			result.append([i, bull, bear, bullBearRatio])

	return result 




# ------------------------------------------------------------------------
# --------------------------- Main Function ------------------------------
# ------------------------------------------------------------------------



def parseSingleList(path):
	l = []
	with open(path) as f:
		file = f.readlines()
		for i in file:
			l.append(''.join(e for e in i if e.isalnum()))
	return l


# def loadJson():
# 	with open('datesSeen.json') as file:
# 		datesSeen = json.load(file)

# def saveJson():
# 	with open('datesSeen.json', 'w') as file:
# 		json.dump(datesSeen, file)



# TODO
# - When analyzing stocks, find new users and store list of users
# - Make document for all users that stores info about them (accuracy)
# - Store information for each day for each stock
# - Use list of users to find new stocks 
# - Find jumps in stocks of > 10% for the next day and see which users were the best at predicting these jumps



def main():
	users = parseSingleList('testList.csv')
	# users = users[2:3] 1Life

	# for user in users:
	# 	analyzeResultsUser(user, 1)

	#analyzeResultsUser("RudyPicks13", 1)
	analyzeResultsUser("RudyPicks13", 1)

	# l = parseSingleList('stockList.csv')

	# global useDatesSeen
	# useDatesSeen = True

	# res = analyzeStocksToday(list)
	# pickStocks(res, 0)


	#analyzeStocksHistory(l, 9)

	driver.close()


main()