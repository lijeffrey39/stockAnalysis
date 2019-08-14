# stockAnalysis
Analyzing stock performance using Stock Twits

## Running the program

1. Scrape data from a given day
--daysback: # days to scrape back from the current day
```
# scrape the current day's tweets for all stocks
python3 stocktwits.py -stocks --daysback 0 
```

2. Scrape data from users
--daysback: # days to scrape back from the current day
```
# scrape tweets from all users 
python3 stocktwits.py -users --daysback 75 
```


3. Calculate returns from past data
--daysback: # days to calculate returns back from
--numstocks: top n stocks to invest from (lower means more risk)
```
# calculate returns for each day back from current day
python3 stocktwits.py -returns --daysback 30 --numstocks 5 
```

4. Predict stocks
--numstocks: top n stocks to invest from (lower means more risk)
```
# predict which stocks to buy 
# run at end of the day
python3 stocktwits.py --numstocks 1
```
