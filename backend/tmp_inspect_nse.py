import requests, json, os
from pprint import pprint

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept-Encoding': 'gzip, deflate, br',
    'Referer': 'https://www.nseindia.com/option-chain',
    'Connection': 'keep-alive',
    'sec-ch-ua': '"Not;A=Brand";v="99", "Chromium";v="124"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Windows"',
}

s = requests.Session()
for url in ['https://www.nseindia.com/option-chain', 'https://www.nseindia.com/api/equity-stockIndices?index=NIFTY%2050']:
    r = s.get(url, headers=headers, timeout=20)
    print('URL', url, 'STATUS', r.status_code)
    print('content-type', r.headers.get('content-type'))
    print('cookies', dict(r.cookies))
    print(r.text[:500])
    print('---')

r = s.get('https://www.nseindia.com/api/option-chain-indices?symbol=NIFTY', headers=headers, timeout=20)
print('CHAIN STATUS', r.status_code)
print(r.text[:1500])
