import datetime 
import pytz
from modules.hyperparameters import constants
from pymongo.errors import BulkWriteError
import hashlib

def get_ticker(message):
    words = message.split() 
    tickers = []
    for w in words:
        if w[0] == '$' and w[1:].isupper():
            tickers.append(w[1:])
    if len(tickers) == 0:
        return None
    return ' '.join(tickers)

def transfer_and_delete(origin, destination, extract_ticker=False):
    batch = origin.find({}, no_cursor_timeout=True, limit=10000)
    count = 1
    while batch.count() > 0:
        to_write = []
        to_delete = []
        for tweet in batch:
            count += 1
            if count % 1000 == 0:
                print('Processed %d tweets' % count)
            to_delete.append(tweet['_id'])
            w = {}
            w['_id'] = hash(tweet['messageText']+tweet['time']+tweet['user'])
            if extract_ticker:
                w['symbol'] = get_ticker(tweet['messageText'])
            else:
                w['symbol'] = tweet['symbol']
            w['user'] = tweet['user']
            w['time'] = datetime.datetime.strptime(tweet['time'], '%Y-%m-%d %H:%M:%S')
            etz = pytz.timezone('US/Eastern')
            etz.localize(w['time'])
            w['time'] = tweet['time']
            w['isBull'] = tweet['isBull']
            w['likeCount'] = tweet['likeCount']
            w['commentCount'] = tweet['commentCount']
            w['messageText'] = tweet['messageText']
            to_write.append(w)
        try:
            destination.insert_many(to_write, ordered=False)
        except BulkWriteError as bwe:
            print(bwe.details)
        origin.delete_many({'_id': {'$in':to_delete}})
        batch = origin.find({}, no_cursor_timeout=True, limit=10000)

user_tweets_db = constants['db_user_client'].get_database('user_data_db').user_info
stock_tweets_db = constants['stocktweets_client'].get_database('stocks_data_db').stock_tweets
consolidated_tweets_db = constants['stocktweets_client'].get_database('tweets_db').tweets
transfer_and_delete(stock_tweets_db, consolidated_tweets_db) 
transfer_and_delete(user_tweets_db, consolidated_tweets_db, True)


