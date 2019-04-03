import os
import sys
import math
import json
import time
import platform
import datetime
import operator
import multiprocessing

from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains

from bs4 import BeautifulSoup
from dateutil.parser import parse
from multiprocessing import Process, Pool

from modules.scroll import *
from modules.fileIO import *
from modules.helpers import *
from modules.analytics import *
from modules.prediction import *
from modules.userAnalysis import *
from modules.stockAnalysis import *
from modules.stockPriceAPI import *
from modules.messageExtract import *


# ------------------------------------------------------------------------
# -------------------------- Global Variables ----------------------------
# ------------------------------------------------------------------------


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
SAVE_USER_PAGE = False
SAVE_STOCK_PAGE = False
DEBUG = True
PROGRESSIVE = False


# ------------------------------------------------------------------------
# ----------------------- Analyze Specific Stock -------------------------
# ------------------------------------------------------------------------


def computeStocksDay(date, processes):
	path = date.strftime("stocksResults/%m-%d-%y.csv")
	folderPath = date.strftime("stocksResults/%m-%d-%y/")
	newUsersPath = date.strftime("newUsers/newUsersList-%m-%d-%y.csv")

	# create empty folder
	if not os.path.exists(folderPath):
	    os.makedirs(folderPath)
	    print("HERE")

	# create empty file
	if (os.path.isfile(path) == False):
		with open(path, "w") as my_empty_csv:
			pass

	if (os.path.isfile(newUsersPath) == False):
		with open(newUsersPath, "w") as my_empty_csv:
			pass

	stocks = readSingleList('newStockList.csv')
	stocks.sort()

	actual = []
	dateCompare = datetime.datetime(date.year, date.month, date.day, 16)
	for stock in stocks:
		path = folderPath + stock + ".csv"
		if (os.path.exists(path)):
			t = os.path.getmtime(path)
			t = datetime.datetime.fromtimestamp(t)
			if (t > dateCompare):
				continue
		if (analyzedSymbolAlready(stock, folderPath) and PROGRESSIVE == False):
			continue
		else:
			actual.append(stock)

	print(len(actual))

	if (DEBUG):
		analyzeStocksToday(actual, date, path, newUsersPath, folderPath)
		return

	pool = Pool()
	stocks = readMultiList('stockFrequency.csv')
	splitEqual = allocateStocks(2, stocks, actual)

	for i in range(processes):
		arguments = [splitEqual[i], date, path, newUsersPath, folderPath]
		pool.apply_async(analyzeStocksToday, arguments)

	pool.close()
	pool.join()
		
	findNewUserChange()


def analyzeStocksToday(listStocks, date, path, usersPath, folderPath):
	for symbol in listStocks:
		print(symbol)

		users = []
		driver = webdriver.Chrome(executable_path = DRIVER_BIN, chrome_options = chrome_options)
		dateNow = datetime.datetime.now()
		days = (dateNow - date).days

		(soup, error) = findPageStock(symbol, days, driver, SAVE_STOCK_PAGE)
		analyzed = analyzedSymbolAlready(symbol, folderPath)
		driver.quit()

		if (error):
			print("ERROR BAD")
			continue

		result = getBearBull(symbol, date, soup)

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

		if (analyzed and PROGRESSIVE):
			filePath = folderPath + symbol + '.csv'
			stockRead = readMultiList(filePath)
			mappedRead = set(list(map(lambda x: ''.join([str(x[0]), str(x[2]), str(x[3])]), stockRead)))
			realRes = []

			for s in result:
				sString = ''.join([str(s[0]), str(s[2]), str(s[3])])
				if (sString not in mappedRead):
					realRes.append(s)

			print(len(realRes))
			stockRead.extend(realRes)
			stockRead = list(filter(lambda x: len(x) > 2, stockRead))
			stockRead = list(map(lambda x: [x[0], x[1], str(x[2]), x[3], x[4]], stockRead))
			stockRead.sort(key = lambda x: parse(x[2]), reverse = True)
			writeSingleList(filePath, stockRead)
			continue

		tempPath = folderPath + symbol + ".csv"
		writeSingleList(tempPath, result)
		print("%s: (%d/%d %0.2f)" % (symbol, bulls, bears, bullBearRatio))



# ------------------------------------------------------------------------
# ----------------------- Analyze Specific User --------------------------
# ------------------------------------------------------------------------



def computeUsersDay(outputPath, inputPath, days, processes):
	users = readSingleList('allNewUsers.csv')

	actual = []
	for user in users:
		if (analyzedUserAlready(user)):
			continue
		else:
			actual.append(user)

	print('USERS: ', len(actual))
	actual.remove('AnalystRatingsNetwork')
	actual.remove('ChartMill')

	if (DEBUG):
		analyzeUsers(actual, days, outputPath)
		return

	splitEqual = list(chunks(actual, processes))
	pool = Pool()

	for i in range(processes):
		arguments = [splitEqual[i], days, outputPath]
		pool.apply_async(analyzeUsers, arguments)

	pool.close()
	pool.join()



def analyzeUsers(users, days, path):
	for user in users:
		if (analyzedUserAlready(user)):
			continue

		print(user)
		driver = webdriver.Chrome(executable_path = DRIVER_BIN, chrome_options = chrome_options)
		soup = findPageUser(user, DAYS_BACK, driver, SAVE_USER_PAGE)

		driver.quit()
		path = "newUserInfo/" + user + ".csv"

		# If the page doesn't have enought bull/bear indicators
		if (soup == None):
			writeSingleList(path, [])
			continue

		result = analyzeUser(user, soup, days)
		writeSingleList(path, result)

		if (len(result) > 0):
			otherInfo = findUserInfo(user, soup)
			saveUserToCSV(user, result, otherInfo)
		continue

		stocks = []
		for r in result:
			stocks.append(r[0])

		writeSingleList(path, result)


# ------------------------------------------------------------------------
# --------------------------- Main Function ------------------------------
# ------------------------------------------------------------------------


# TODO
# 1. SHOULD IGNORE DIFF if it is 0? count as correct
# 2. Remove outliers that are obviously not true prices
# 4. Weight likes/comments into the accuracy of user
# 6. Figure out why some invalid symbols are not actually invalid
# 7. View which stocks should be removed based on # users
# 8. Implement better caching
# 10. Find faster way to update templists folder
# 13. For dictPredictions, find the middle number of users for prediction rate

# Find outliers in stocks 

def runInterval(date, endTime, sleepTime):
	prevHour = datetime.datetime.now()
	while (datetime.datetime.now() < endTime):
		# Compute stocks
		computeStocksDay(date, 7)

		# View how much time has passed
		newHour = datetime.datetime.now()
		secPassed = (newHour - prevHour).seconds

		if (secPassed > sleepTime):
			prevHour = newHour
		else:
			timeRest = sleepTime - secPassed
			time.sleep(timeRest)
	

def findOutliers(stockName, date):
	folder = "userinfo/"
	allU = allUsers()
	print(len(allU))
	found = 0
	count = 0

	for u in allU:
		l = readMultiList('userInfo/' + u + '.csv')
		
		for r in l:
			four = float(r[2])
			nine = float(r[3])
			foundDate = parse(r[1])

			if (r[0] == stockName 
				and foundDate.year == date.year 
				and foundDate.day == date.day 
				and foundDate.month == date.month):
				count += 2
				found += four
				found += nine

	print(found / count)



def savePrices():
	folder = "userinfo/"
	allU = allUsers()
	print(len(allU))
	stockNames = {}
	count = 0

	for u in allU:
		l = readMultiList('userInfo/' + u + '.csv')
		
		count += 1
		if (count % 100 == 0):
			print(count)

		for r in l:
			four = float(r[2])
			nine = float(r[3])
			foundDate = parse(r[1])
			dateA = foundDate.strftime("%m/%d/%y")
			stock = r[0]

			if (stock not in stockNames):
				stockNames[stock] = {}
				stockNames[stock][dateA] = [(four + nine) / 2]
			else:
				if (dateA not in stockNames[stock]):
					stockNames[stock][dateA] = [(four + nine) / 2]
				else:
					stockNames[stock][dateA].append((four + nine) / 2)

	print(stockNames["TVIX"])

def main():
	args = sys.argv
	dateNow = datetime.datetime.now()

	if (len(args) > 1):
		dayUser = args[1]
		if (dayUser == "day"):
			date = datetime.datetime(dateNow.year, 3, 29)
			computeStocksDay(date, 2)
			# DIDnt calc on 2/22
			# hour = 60 * 60
			# timeEnd = datetime.datetime(dateNow.year, dateNow.month, dateNow.day, 20)
			# runInterval(date, timeEnd, hour)

			# # weights = [9, 0.48, 0.45, 0.64, 1.92]
			# # res = topStocks(date, 2000, weights)
			# statsUsers()
			# writeTempListStocks()
		else:
			computeUsersDay('userInfo.csv', 'allNewUsers.csv', 1, 10)
	else:	

		savePrices()
		return

		date = datetime.datetime(dateNow.year, 1, 14)
		dates = findTradingDays(date)
		# dates = dates[0: len(dates) - 1]
		# print(dates)
		# dates = [datetime.datetime(dateNow.year, 2, 15)]

		money = 2000
		startMoney = 2000
		totalReturn = 0
		x = 0
		y = 0
		dictPrices = {}
		for date in dates:
			weights = [9, 0.48, 0.45, 0.64, 1.92]

			(res, hitPercent) = topStocks(date, money, weights)
			(foundReturn, pos, neg, newRes) = calcReturnBasedResults(date, res)

			for new in newRes:
				if (new[0] not in dictPrices):
					dictPrices[new[0]] = new[1]
				else:
					dictPrices[new[0]] += new[1]

			x += pos
			y += neg
			if (foundReturn > 0):
				print("%s $%.2f +%.2f%%    Hit: %.2f%%" % (date.strftime("%m-%d-%y"), foundReturn, 
					round((((money + foundReturn) / money) - 1) * 100, 2), hitPercent))
			else:
				print("%s $%.2f %.2f%%    Hit: %.2f%%" % (date.strftime("%m-%d-%y"), foundReturn, 
					round((((money + foundReturn) / money) - 1) * 100, 2), hitPercent))
			totalReturn += foundReturn
			money += foundReturn

		sorted_x = sorted(dictPrices.items(), key=operator.itemgetter(1))
		print(sorted_x)
		print("$%d -> $%d" % (startMoney, startMoney + totalReturn))
		print("+%.2f%%" % (round((((startMoney + totalReturn) / startMoney) - 1) * 100, 2)))
		print("+%d -%d" % (x, y))


if __name__ == "__main__":
	main()
