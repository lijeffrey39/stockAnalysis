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
from modules.prediction import *
from modules.userAnalysis import *


chrome_options = webdriver.ChromeOptions()
prefs = {"profile.managed_default_content_settings.images": 2}
chrome_options.add_experimental_option("prefs", prefs)
chrome_options.add_argument("--headless")
chrome_options.add_argument('log-level=3')
cpuCount = multiprocessing.cpu_count()


chromedriverName = 'chromedriver' if (platform.system() == "Darwin") else 'chromedriver.exe'
PROJECT_ROOT = os.getcwd()
DRIVER_BIN = os.path.join(PROJECT_ROOT, chromedriverName)
DAYS_BACK = 75
CREATED_DICT_USERS = False
SAVE_USER_PAGE = False
SAVE_STOCK_PAGE = False
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
	foundEnough = scroll.scrollFor(symbol, days, driver)

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
	driver.close()

	if (error):
		print("ERROR BAD")
		return []

	savedSymbolHistorical = get_historical_intraday(symbol, date)

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

		foundAvg = priceAtTime(dateTime, savedSymbolHistorical) # fix this function to take dateTimeadjusted

		messageInfo = [user, isBull, dateTime, foundAvg]
		res.append(messageInfo)

	return res



# ------------------------------------------------------------------------
# ----------------------- Analyze Specific User --------------------------
# ------------------------------------------------------------------------


def analyzeUsers(users, days, path):
	for user in users:
		if (analyzedUserAlready(user)):
			continue

		print(user)
		driver = webdriver.Chrome(executable_path = DRIVER_BIN, chrome_options = chrome_options)
		soup = findPageUser(user, DAYS_BACK, driver, SAVE_USER_PAGE)

		driver.close()
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
	stocks.remove('ACB')

	actual = []
	for i in stocks:
		if (analyzedSymbolAlready(i, path)):
			continue
		else:
			actual.append(i)

	splitEqual = list(chunks(actual, processes))
	pool = Pool()

	# analyzeStocksToday(splitEqual[0], date, path, newUsersPath, folderPath)
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
			date = datetime.datetime(dateNow.year, 2, 5)
			dates = findTradingDays(date)
			computeStocksDay(date, 1)

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

		dateNow = datetime.datetime.now()
		date = datetime.datetime(dateNow.year, 1, 14)
		dates = findTradingDays(date)
		# dates = [datetime.datetime(dateNow.year, 2, 4)]
		totalReturn = 0

		money = 2000
		for date in dates:
			weights = [9, 0.48, 0.45, 0.64, 1.92]

			(res, hitPercent) = topStocks(date, money, weights)
			foundReturn = calcReturnBasedResults(date, res)
			# print(date.strftime("%m-%d-%y"), foundReturn)
			if (foundReturn > 0):
				print("%s %.2f +%.2f%%    Hit: %.2f%%" % (date.strftime("%m-%d-%y"), foundReturn, round((((money + foundReturn) / money) - 1) * 100, 2), hitPercent))
			else:
				print("%s %.2f %.2f%%    Hit: %.2f%%" % (date.strftime("%m-%d-%y"), foundReturn, round((((money + foundReturn) / money) - 1) * 100, 2), hitPercent))
			totalReturn += foundReturn
			money += foundReturn

		print("%d -> %d" % (2000, 2000 + totalReturn))
		print("+%.2f%%" % (round((((2000 + totalReturn) / 2000) - 1) * 100, 2)))



if __name__ == "__main__":
	main()