from bs4 import BeautifulSoup
import time
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
import os
import datetime
from iexfinance.stocks import get_historical_intraday
from dateutil.parser import parse

PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))
DRIVER_BIN = os.path.join(PROJECT_ROOT, "chromedriver")
driver = webdriver.Chrome(executable_path = DRIVER_BIN)


# SET NAME ATTRIBUTES
priceAttr = 'StockHeader__bid___2BF7L'
messageStreamAttr = 'MessageStreamView__message___2o0za'
timeAttr = 'MessageStreamView__created-at___HsSv2'
usernameAttr = 'MessageStreamView__username___x9n-9'
bullSentAttr = 'SentimentIndicator__SentimentIndicator-bullish___1WHAM SentimentIndicator__SentimentIndicator___3bEpt'
bearSentAttr = 'SentimentIndicator__SentimentIndicator-bearish___2KbIj SentimentIndicator__SentimentIndicator___3bEpt'
userPageAttr = 'UserHeader__username___33aun'


# Sroll down until length
def scroll(length):
	elem = driver.find_element_by_tag_name("body")

	for i in range(length):
		elem.send_keys(Keys.PAGE_DOWN)
		time.sleep(0.1)
	time.sleep(1)


def findDateTime(message):
	t = message.find('a', attrs={'class': timeAttr})

	if (t == None):
		return None
	else:
		dateTime = parse(t.text)
		return dateTime


def findUser(message):
	u = message.find('a', attrs={'class': usernameAttr})

	if (u == None):
		return None
	else:
		user = u['href'][1:]
		return user


def findHistoricalData(dateTime, symbol, datesSeen):
	dateTimeStr = dateTime.strftime("%Y-%m-%d")
	day = dateTime.strftime("%w")
	outOfRange = False
	historical = []
	delta = None

	# if it is a saturday or sunday, find friday's time
	if (day == '6'):
		delta = datetime.timedelta(1)
	if (day == '0'):
		delta = datetime.timedelta(2)

	if (delta != None):
		dateTime = dateTime - delta
		outOfRange = True

	if (dateTimeStr not in datesSeen):
		historical = get_historical_intraday(symbol, dateTime)
		datesSeen[dateTimeStr] = historical 
	else:
		historical = datesSeen[dateTimeStr]

	return (historical, outOfRange)


def priceAtTime(dateTime, historical, outOfRange):
	foundAvg = ""
	found = False
	for ts in historical:
		if (ts.get("minute") == dateTime.strftime("%X")[:5]):
			found = True
			foundAvg = ts.get('marketAverage')

	if (found == False or outOfRange == True):
		last = historical[len(historical) - 1]
		foundAvg = last.get('marketAverage')

	return foundAvg


def getBearBull(symbol):
	url = "https://stocktwits.com/symbol/" + symbol
	driver.get(url)
	time.sleep(1)

	scroll(10)

	html = driver.page_source
	soup = BeautifulSoup(html, 'html.parser')
	currentPrice = soup.find('span', attrs={'class': priceAttr}).text
	print("Current Price of %s: %s" % (symbol, currentPrice))

	bulls = []
	bears = []
	datesSeen = {} # make array for that date so don't have to keep calling api

	messages = soup.find_all('div', attrs={'class': messageStreamAttr})

	for m in messages:
		dateTime = findDateTime(m)
		user = findUser(m)

		if (dateTime == None or user == None):
			continue

		(historical, outOfRange) = findHistoricalData(dateTime, symbol, datesSeen)
		foundAvg = priceAtTime(dateTime, historical, outOfRange)

		res = [foundAvg, user]

		bull = m.find('span', attrs={'class': bullSentAttr})
		bear = m.find('span', attrs={'class': bearSentAttr})

		if (bull):
			bulls.append(res)
		if (bear):
			bears.append(res)

	print(len(bears))
	print(len(bulls))
	return {"bear": bears, "bull": bulls}




# def analyzeUser(username):
# 	url = "https://stocktwits.com/" + username
# 	driver.get(url)
# 	time.sleep(1)

# 	scroll(20)

# 	messages = soup.find_all('div', attrs={'class': messageStreamAttr})

# 	for m in messages:



def main():
	resTVIX = getBearBull("TVIX")
	print(resTVIX)
	# testUser = resTVIX['bear'][0][1]
	driver.close()
	#userAnalyze = analyzeUser(testUser)

main()