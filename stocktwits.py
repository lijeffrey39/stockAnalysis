from bs4 import BeautifulSoup
import time
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
import os
import datetime
from iexfinance.stocks import get_historical_intraday
from dateutil.parser import parse

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


# Make cache for that symbol and date so don't have to keep calling api
# Formatted like {"TVIX": {"2018-12-24": [historical_data], "2018-12-23": [more_data]}
datesSeen = {} 


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
	# oldTime = dateTime - delta
	oldTime = datetime.datetime(dateTime.year, dateTime.month, dateTime.day, 9, 30)

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

	if (symbol not in datesSeen):
		try:
			historical = get_historical_intraday(symbol, dateTime)
			newSymbolTime = {}
			newSymbolTime[dateTimeStr] = historical
			datesSeen[symbol] = newSymbolTime
		except:
			pass
			print("Invalid ticker1")
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
	day = dateTime.strftime("%w")
	outOfRange = False
	delta = None
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
		if (day == '6'):
			delta = datetime.timedelta(1)
		if (day == '0'):
			delta = datetime.timedelta(2)

	if (delta != None):
		if (futurePrice == False):
			dateTime = dateTime - delta
		outOfRange = True

	historical = historicalFromDict(symbol, dateTime)

	return (historical, outOfRange, dateTime)


# Price of a stock at a certain time given historical data
def priceAtTime(dateTime, historical, outOfRange):
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

    if (found == False or outOfRange == True):
        last = historical[len(historical) - 1]
        foundAvg = last.get('average')

    return foundAvg


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
		inTradingHours(dateTime, symbol) == False or
		(daysInFuture == 0 and dateCheck != dateNow) or
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

		(historical, outOfRange, dateTimeAdjusted1) = findHistoricalData(dateTime, symbol, False)
		foundAvg = priceAtTime(dateTime, historical, outOfRange) # fix this function to take dateTimeadjusted

		# If only looking for current day's prices
		if (daysInFuture == 0):
			messageInfo = [user, isBull, dateTimeAdjusted1, foundAvg]
			res.append(messageInfo)
			continue

		# Find price after # days
		delta = datetime.timedelta(daysInFuture)
		newTime = dateTime + delta
		newTime = datetime.datetime(newTime.year, newTime.month, newTime.day, 9, 30)

		(historical, outOfRange, dateTimeAdjusted2) = findHistoricalData(newTime, symbol, True)
		newFoundAvg = priceAtTime(newTime, historical, False)

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



def findPricesTickers(spans, dateTime, futurePrice):
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
		return ([], True)

	prices = []
	noData = False

	# Should only have 1 ticker
	for ticker in tickers:
		(historical, outOfRange, dateTimeAdjusted) = findHistoricalData(dateTime, ticker, futurePrice)
		if (len(historical) == 0):
			noData = True
			break

		foundAvg = priceAtTime(dateTime, historical, outOfRange)
		prices.append([ticker, foundAvg])

	return (prices, noData)


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
	foundEnough = scrollFor(1, 5)

	if (foundEnough == False):
		return None

	html = driver.page_source
	soup = BeautifulSoup(html, 'html.parser')

	with open(path, "w") as file:
	    file.write(str(soup))

	return soup


def analyzeUser(username, soup, days, beginningOfDay):

	messages = soup.find_all('div', attrs={'class': messageStreamAttr})
	res = []

	for m in messages:
		bull = m.find('span', attrs={'class': bullSentAttr})
		bear = m.find('span', attrs={'class': bearSentAttr})
		dateTime = findDateTime(m)
		bullish = False

		if ((bull == None and bear == None) or dateTime == None):
			continue

		if (bear == None):
			bullish = True

		textM = m.find('div', attrs={'class': messageTextAttr})
		spans = textM.find_all('span')

		(prices, noDataTicker) = findPricesTickers(spans, dateTime, False)

		# Some stocks have no data?
		if (noDataTicker):
			continue

		# Find price after # days
		delta = datetime.timedelta(days)
		newTime = dateTime + delta

		# Find time at 9:30 am
		if (beginningOfDay):
			newTime = datetime.datetime(newTime.year, newTime.month, newTime.day, 9, 30)

		(newPrices, noDataTicker) = findPricesTickers(spans, newTime, True)

		# If time + delta is too far in the future
		if (noDataTicker):
			# print(dateTime.strftime("%Y-%m-%d"))
			# print("Too far in future/not a stock trading day (holiday)")
			continue

		print(prices + [dateTime.strftime("%m/%d %H:%M:%S")], newPrices + [newTime.strftime("%m/%d %H:%M:%S")])
		correct = False
		change = newPrices[0][1] - prices[0][1]
		totalChange = abs(change)

		if((change > 0 and bullish == True ) or (change <= 0 and bullish == False)):
			correct = True

		res.append([prices, newPrices, dateTime.strftime("%Y-%m-%d %H:%M:%S"), bullish, correct, totalChange])

	return res


def analyzeResultsUser(username, days):
	soup = findPageUser(username)
	results = []

	# If the page doesn't have enought bull/bear indicators
	if (soup == None):
		return False
	
	for i in range(1, days):
		print(i)
		dayLoop = analyzeUser(username, soup, i, True)
		goodcents = 0
		badcents = 0
		totalGood = 0
		totalBad = 0

		for dataLoop in dayLoop:
			if (dataLoop[4] == True):
				goodcents += dataLoop[5]
				totalGood += 1
			else:
				badcents += dataLoop[5]
				totalBad += 1

		ratio = goodcents / badcents
		results.append([totalGood, totalBad, round(ratio, 2)])
	
	print(results)

	return True



# ------------------------------------------------------------------------
# --------------------------- Main Function ------------------------------
# ------------------------------------------------------------------------



def parseUsers():
	with open('users.csv') as f:
		file = f.readlines()
		users = file[0].split(',')

	for i in range(len(users)):
		user = users[i]
		s = ''.join(e for e in user if e.isalnum())
		users[i] = s

	return users


def parseStocksList():
	l = []
	with open('stockList.csv') as f:
		file = f.readlines()
		for i in file:
			l.append(''.join(e for e in i if e.isalnum()))

	return l


def analyzeStocksToday(listStocks):

	result = []

	for symbol in listStocks:
		res = []
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
			bull = d[1]
			
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


def main():
	# users = parseUsers()
	# users = users[2:3]

	# for user in users:
	# 	analyzeResultsUser(user, 1)

	l = parseStocksList()

	res = analyzeStocksToday(l)
	pickStocks(res, 0)

	#analyzeStocksHistory(l, 9)

	driver.close()


main()