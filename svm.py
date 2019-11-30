import numpy as np
import torch
import datetime

from modules.helpers import findTradingDays
from modules.stockAnalysis import getTopStocks
from modules.hyperparameters import constants
from modules.stockPriceAPI import getUpdatedCloseOpen
from modules.userAnalysis import getAllUserInfo


clientStockTweets = constants['stocktweets_client']
clientUser = constants['db_user_client']


def usefulFunctions():
    # Get top 30 tweeted stocks
    stocks = getTopStocks(30)
    print(stocks)

    # Find all trading dates for historical days
    dateStart = datetime.datetime(2019, 8, 1, 9, 30)
    dateEnd = datetime.datetime(2019, 11, 27, 16, 0)
    dates = findTradingDays(dateStart, dateEnd)
    print(dates)

    # DB for all user accuracies
    analyzedUsersDB = clientUser.get_database('user_data_db')
    userAccuracy = analyzedUsersDB.new_user_accuracy

    # Query to find all users that have historical data on TSLA
    stockName = 'TSLA'
    query = {'perStock.' + stockName: {'$exists': True}}
    allAccs = userAccuracy.find(query)
    mappedTweets = list(map(lambda doc: [doc['_id'], doc['perStock'][stockName]['bullReturnUnique'], 
                        doc['perStock'][stockName]['bearReturnUnique']], allAccs))
    mappedTweets.sort(key=lambda x: x[1] + x[2], reverse=True)
    # Prints top 5 users with their returns
    print(mappedTweets[:5])

    # Query for all tweets with TSLA in it
    allTweets = clientStockTweets.get_database('tweets_db').tweets
    query = {'symbol': stockName}
    tweets = allTweets.find(query)
    print(stockName, tweets.count())

    # Query for all tweets on this given date between 9:30 am and 4:00 pm and they have a bull or bear
    dateStart = datetime.datetime(2019, 10, 15, 9, 30)
    dateEnd = datetime.datetime(2019, 10, 15, 16, 0)
    query = {"$and": [{'symbol': stockName},
                      {"$or": [
                                {'isBull': True},
                                {'isBull': False}
                              ]},
                      {'time': {'$gte': dateStart,
                                '$lt': dateEnd}}]}
    tweets = allTweets.find(query)
    print(stockName, tweets.count())

    # Print first 10 tweets
    for tweet in tweets[:10]:
        print(tweet['user'], tweet['time'])

    # Example from one tweet
    tweets = allTweets.find(query)
    firstTweet = tweets[0]
    print(firstTweet)
    user = firstTweet['user']

    # Get info about that user
    allUserInfo = getAllUserInfo(user)

    # Find users returns on TSLA 
    print(allUserInfo['perStock']['TSLA'])
    # Find users total tweets
    print(allUserInfo['totalTweets'])

    # Get close open prices for that given date and symbol
    closeOpen = getUpdatedCloseOpen(stockName, dateStart)
    print(closeOpen)