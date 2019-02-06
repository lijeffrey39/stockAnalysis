import datetime
import sys
sys.path.append("..")

from iexfinance.stocks import get_historical_intraday
from stockAnalysis import stocktwits 
from multiprocessing import current_process
# import stocktwits
from .fileIO import *


# ------------------------------------------------------------------------
# ----------------------------- Variables --------------------------------
# ------------------------------------------------------------------------


# Invalid symbols so they aren't check again
invalidSymbols = []
currHistorical = []
currSymbol = ""


# ------------------------------------------------------------------------
# ----------------------------- Functions --------------------------------
# ------------------------------------------------------------------------


def historicalFromDict(symbol, dateTime):
	global invalidSymbols
	global currSymbol
	global currHistorical
	historial = []
	dateTimeStr = dateTime.strftime("%Y-%m-%d")

	if (symbol != currSymbol):
		currSymbol = symbol
		currHistorical = get_historical_intraday(symbol, dateTime)
		return currHistorical
	else:
		return currHistorical

	# if (useDatesSeen == False):	
	# 	if (symbol in invalidSymbols):
	# 		return []
	# 	try:
	# 		historical = get_historical_intraday(symbol, dateTime)
	# 		return historical
	# 	except:
	# 		print(symbol)
	# 		invalidSymbols.append(symbol)
	# 		invalidSymbols.sort()

	# 		tempList = []
	# 		for s in invalidSymbols:
	# 			tempList.append([s])

	# 		writeSingleList('invalidSymbols.csv', tempList)

	# 		print("Invalid ticker2")
	# 		return []



	# Find what process is using it
	# currentP = current_process().name
	# datesSeen = datesSeenGlobal[currentP]

	# if (symbol not in datesSeen):
	# 	try:
	# 		historical = get_historical_intraday(symbol, dateTime)
	# 		newSymbolTime = {}
	# 		newSymbolTime[dateTimeStr] = historical
	# 		datesSeen[symbol] = newSymbolTime
	# 	except:
	# 		pass
	# 		print("Invalid ticker1")
	# 		return []
	# else:
	# 	datesForSymbol = datesSeen[symbol]
	# 	if (dateTimeStr not in datesForSymbol):
	# 		try:
	# 			historical = get_historical_intraday(symbol, dateTime)
	# 			datesSeen[symbol][dateTimeStr] = historical
	# 		except:
	# 			pass
	# 			print("Invalid ticker")
	# 	else:
	# 		print("hi")
	# 		historical = datesSeen[symbol][dateTimeStr]

	# datesSeenGlobal[currentP] = datesSeen
	# return historical



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
            foundAvg2 = ts.get('marketHigh')
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

	# Go from end to front
    if (found == False):
    	lastPos = len(historical) - 1
    	foundAvg = -1
    	while (foundAvg == -1 and lastPos > 0):	
    		last = historical[lastPos]
    		foundAvg = last.get('average')
    		foundAvg1 = last.get('marketAverage')
    		if (foundAvg1 != -1):
    			foundAvg = foundAvg1
    			break
    		lastPos = lastPos - 1

    return foundAvg
