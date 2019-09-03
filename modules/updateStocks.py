from hyperparameters import constants
import requests
import datetime 
import hashlib
import pymongo
import time
import argparse
import pytz


def updateStock(ticker, hours_back, interval=5, insert=False):
    api_call = 'https://www.alphavantage.co/query?function=TIME_SERIES_INTRADAY&symbol=%s&interval=%dmin&outputsize=full&apikey=%s' % (ticker, interval, constants['alpha_vantage_api_key'])
    response = requests.get(url=api_call)
    price_data = None
    if insert:
        price_data_list = []
    try:
        price_data = response.json()['Time Series (%dmin)' % (interval)]
    except KeyError:
        time.sleep(60)
        response = requests.get(url=api_call)
        try:
            price_data = response.json()['Time Series (%dmin)' % (interval)]
        except:
            print(response.json())
            return
    price_data_list = []
    stock_data_collection = constants['db_client'].get_database('stocks_data_db').stock_data
    for timestamp_s in price_data:
        price_data_dict = {}
        etz = pytz.timezone('US/Eastern')
        timestamp = etz.localize(datetime.datetime.strptime(timestamp_s, '%Y-%m-%d %H:%M:%S'))
        now = datetime.datetime.now(etz)
        datetime_elapsed = now - timestamp
        hours_elapsed = 24 * datetime_elapsed.days + int(datetime_elapsed.seconds/3600)
        if hours_elapsed > hours_back:
            continue
        else:
            id = ticker+timestamp_s
            if insert:
                price_data_dict['_id'] = id
            """
            price_data_dict['ticker'] = ticker
            price_data_dict['timestamp'] = timestamp_s
            """
            price_data_dict['date'] = timestamp_s[:10]
            price_data_dict['price'] = 0.5 * round((float(price_data[timestamp_s]['2. high'])+float(price_data[timestamp_s]['3. low'])), 2)
            if insert:
                price_data_list.append(price_data_dict)
            else:
                stock_data_collection.update({'_id':id}, {'$set': price_data_dict}, upsert=True)
    if insert:
        stock_data_collection.insert_many(price_data_list)


def insertStock(ticker, hours_back, interval=5):
    stock_db = constants['db_client'].get_database('stocktwits_db').all_stocks
    try:
        updateStock(ticker, hours_back, interval, True) 
    except KeyError:
        return -1
    except pymongo.errors.BulkWriteError:
        print('Stock data already exists. Try updateStock instead')
    stock_db.insert({'_id':ticker})
    return 1

    
def updateAllStocks(hours_back=24*8, interval=5):
    all_tickers = constants['db_client'].get_database('stocktwits_db').all_stocks.find({}, no_cursor_timeout=True)
    for t in all_tickers:
        print('Updating stock data for ticker %s' % (t['_id']))
        try:
            updateStock(t['_id'], hours_back, interval)
        except KeyError:
            print('Ticker %s does not exist' % (interval))
    all_tickers.close()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-u', action='store_true', dest='update', default=False)
    results = parser.parse_args()
    if results.update:
        updateAllStocks()
    

if __name__ == '__main__':
    main()
