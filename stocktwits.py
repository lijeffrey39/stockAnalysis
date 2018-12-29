from bs4 import BeautifulSoup
import time
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
import os
from datetime import datetime
from iexfinance.stocks import get_historical_intraday

PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))
DRIVER_BIN = os.path.join(PROJECT_ROOT, "chromedriver")
driver = webdriver.Chrome(executable_path = DRIVER_BIN)

def scroll():
	elem = driver.find_element_by_tag_name("body")

	# Sroll down until x
	for i in range(10):
		elem.send_keys(Keys.PAGE_DOWN)
		time.sleep(0.1)

	print('done scrolling')
	time.sleep(1)
	

def getBearBull(symbol):

	url = "https://stocktwits.com/symbol/" + symbol
	driver.get(url)
	print('loaded')
	time.sleep(1)

	scroll()

	html = driver.page_source
	soup = BeautifulSoup(html, 'html.parser')
	currentPrice = soup.find('span', attrs={'class': 'StockHeader__bid___2BF7L'}).text
	print(currentPrice)

	messages = soup.find_all('div', attrs={'class': 'MessageStreamView__message___2o0za'})
	bulls = []
	bears = []

	for m in messages:
		t = m.find('a', attrs={'class': 'MessageStreamView__created-at___HsSv2'})

		if (t == None):
			continue

		t = t.text.encode("utf-8")

		bull = m.find('span', attrs={'class': 'SentimentIndicator__SentimentIndicator-bearish___2KbIj SentimentIndicator__SentimentIndicator___3bEpt'})
		bear = m.find('span', attrs={'class': 'SentimentIndicator__SentimentIndicator-bullish___1WHAM SentimentIndicator__SentimentIndicator___3bEpt'})

		if (bull):
			bulls.append(t)

		if (bear):
			bears.append(t)

	return {"bear": bears, "bull": bulls}

resTVIX = getBearBull("TVIX")
resSQQQ = getBearBull("SQQQ")

print(resTVIX)
print(resSQQQ)