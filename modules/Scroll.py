import datetime
import time

from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from selenium import webdriver

from iexfinance.stocks import get_historical_intraday
from dateutil.parser import parse
from bs4 import BeautifulSoup

from .messageExtract import findDateTime



# ------------------------------------------------------------------------
# ----------------------------- Variables --------------------------------
# ------------------------------------------------------------------------



# SET NAME ATTRIBUTES
priceAttr = 'st_2BF7LWC'
messageStreamAttr = 'st_1m1w96g'
messagesCountAttr = 'st__tZJhLh'



# ------------------------------------------------------------------------
# ----------------------------- Functions --------------------------------
# ------------------------------------------------------------------------



# Scroll for # days
def scrollFor(name, days, driver):
	elem = driver.find_element_by_tag_name("body")

	dateTime = datetime.datetime.now() 
	delta = datetime.timedelta(days)
	oldTime = dateTime - delta
	oldTime = datetime.datetime(oldTime.year, oldTime.month, oldTime.day, 9, 30)

	SCROLL_PAUSE_TIME = 2
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
				time.sleep(0.1)

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

def helloWorld():
	print(math.pi)