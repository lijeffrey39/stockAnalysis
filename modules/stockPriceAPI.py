import datetime
from iexfinance.stocks import get_historical_intraday
from multiprocessing import current_process
from .fileIO import *


# ------------------------------------------------------------------------
# ----------------------------- Variables --------------------------------
# ------------------------------------------------------------------------


# Invalid symbols so they aren't check again
invalidSymbols = []
currHistorical = []
currSymbol = ""
currDateTimeStr = ""


# ------------------------------------------------------------------------
# ----------------------------- Functions --------------------------------
# ------------------------------------------------------------------------


def historicalFromDict(symbol, dateTime):
	global invalidSymbols
	global currSymbol
	global currHistorical
	global currDateTimeStr
	historial = []
	dateTimeStr = dateTime.strftime("%Y-%m-%d")

	if (symbol == None):
		return []

	if (symbol != currSymbol or dateTimeStr != currDateTimeStr):
		currSymbol = symbol
		currDateTimeStr = dateTimeStr
		try:
			currHistorical = get_historical_intraday(symbol, dateTime, token = "pk_d6528871eca4497282a367b88d51f813")
			return currHistorical
		except:
			print("Invalid ticker")
			currHistorical = []
			return currHistorical
	else:
		return currHistorical


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
            if (foundAvg != None):
            	found = True
            	break
            else:
            	if (foundAvg1 != None):
            		found = True
            		foundAvg = foundAvg1
            		break
            	else:
                	continue

	# Go from end to front
    if (found == False):
    	lastPos = len(historical) - 1
    	foundAvg = None
    	while (foundAvg == None and lastPos > 0):
    		last = historical[lastPos]
    		foundAvg = last.get('average')
    		foundAvg1 = last.get('marketAverage')
    		if (foundAvg1 != None):
    			foundAvg = foundAvg1
    			break
    		lastPos = lastPos - 1

    return foundAvg
