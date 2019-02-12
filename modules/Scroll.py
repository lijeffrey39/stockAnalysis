import time
import datetime

from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains

from bs4 import BeautifulSoup
from dateutil.parser import parse
from .messageExtract import findDateTime
from iexfinance.stocks import get_historical_intraday
from .helpers import analyzedSymbolAlready
from .fileIO import *


# ------------------------------------------------------------------------
# ----------------------------- Variables --------------------------------
# ------------------------------------------------------------------------


priceAttr = 'st_2BF7LWC'
messageStreamAttr = 'st_1m1w96g'
messagesCountAttr = 'st__tZJhLh'
SCROLL_PAUSE_TIME = 2


# ------------------------------------------------------------------------
# ----------------------------- Functions --------------------------------
# ------------------------------------------------------------------------


def findLastTime(messages):
	lastMessage = messages[len(messages) - 1].text
	t = lastMessage.split('\n')
	if (t[0] == "Bearish" or t[0] == "Bullish"):
		dateTime = findDateTime(t[2])
		return dateTime
	else:
		dateTime = findDateTime(t[1])
		return dateTime


def isStockPage(driver):
	messageCount = driver.find_elements_by_class_name(messagesCountAttr)
	analyzingStock = False
	if (len(messageCount) == 0):
		analyzingStock = True
		price = driver.find_elements_by_class_name(priceAttr)
		# ActionChains(driver).move_to_element(price[0]).perform()  
	else:	
		ActionChains(driver).move_to_element(messageCount[0]).perform()  

	return analyzingStock


def pageExists(driver):
	html = driver.page_source
	soup = BeautifulSoup(html, 'html.parser')
	messages = soup.find_all('div', attrs={'class': messageStreamAttr})

	# page doesnt exist
	currentCount = len(messages)
	if (currentCount == 0):
		return False

	return True


# Scroll for # days
def scrollFor(name, days, driver, progressive):
	dateTime = datetime.datetime.now() 
	folderPath = dateTime.strftime("stocksResults/%m-%d-%y/")
	oldTime = dateTime - datetime.timedelta(days)
	oldTime = datetime.datetime(oldTime.year, oldTime.month, oldTime.day, 9, 30)
	last_height = driver.execute_script("return document.body.scrollHeight")
	price = driver.find_elements_by_class_name(priceAttr)
	analyzingStock = isStockPage(driver)

	if (pageExists(driver) == findLastTime or (len(price) == 0 and analyzingStock)):
		print("Doesn't Exist")
		return False

	count = 1
	modCheck = 1
	analyzedAlready = analyzedSymbolAlready(name, folderPath)
	if (analyzedAlready and analyzingStock and progressive):
		filePath = folderPath + name + '.csv'
		stockRead = readMultiList(filePath)
		if (len(stockRead) == 0):
			pass
		else:
			oldTime = parse(stockRead[0][2])

	while(True):
		new_height = driver.execute_script("return document.body.scrollHeight")
		time.sleep(SCROLL_PAUSE_TIME)
		if (count % modCheck == 0):
			modCheck += 1
			time.sleep(SCROLL_PAUSE_TIME)
			driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
			new_height = driver.execute_script("return document.body.scrollHeight")
			messages = driver.find_elements_by_class_name(messageStreamAttr)
			
			if (len(messages) == 0):
				print("Strange Error")
				return False

			dateTime = findLastTime(messages)

			print(name, dateTime)
			if (analyzingStock == False and new_height == last_height):
				break

		last_height = new_height
		driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
		count += 1

		if (dateTime < oldTime):
			break

	print("Finished Reading", name)
	return True