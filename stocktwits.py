from bs4 import BeautifulSoup
import time
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
import os
from datetime import datetime
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

def scroll(length):
	elem = driver.find_element_by_tag_name("body")

	# Sroll down until length
	for i in range(length):
		elem.send_keys(Keys.PAGE_DOWN)
		time.sleep(0.1)
	time.sleep(1)


def getBearBull(symbol):
	url = "https://stocktwits.com/symbol/" + symbol
	driver.get(url)
	time.sleep(1)

	scroll(10)

	html = driver.page_source
	soup = BeautifulSoup(html, 'html.parser')
	currentPrice = soup.find('span', attrs={'class': priceAttr}).text
	print("Current Price of %s: %s" % (symbol, currentPrice))

	messages = soup.find_all('div', attrs={'class': messageStreamAttr})
	bulls = []
	bears = []

	for m in messages:
		t = m.find('a', attrs={'class': timeAttr})
		u = m.find('a', attrs={'class': usernameAttr})

		if (t == None or u == None):
			continue

		user = u['href'][1:]
		dateTime = parse(t.text)
		found = False
		historical = get_historical_intraday(symbol, dateTime)
		foundAvg = ""

		for ts in historical:
			if (ts.get("minute") == dateTime.strftime("%X")[:5]):
				found = True
				foundAvg = ts.get('marketAverage')

		if (found == False):
			last = historical[len(historical) - 1]
			foundAvg = last.get('marketAverage')

		res = [foundAvg, user]

		bull = m.find('span', attrs={'class': bullSentAttr})
		bear = m.find('span', attrs={'class': bearSentAttr})

		if (bull):
			bulls.append(res)
		if (bear):
			bears.append(res)

	return {"bear": bears, "bull": bulls}


def analyzeUser(username):
	url = "https://stocktwits.com/" + username
	driver.get(url)
	time.sleep(1)

	scroll(20)


def main():
	resTVIX = getBearBull("TVIX")
	print(resTVIX)
	testUser = resTVIX['bear'][0][1]
	#userAnalyze = analyzeUser(testUser)

main()