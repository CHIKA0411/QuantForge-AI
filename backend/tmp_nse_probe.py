import requests

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept-Encoding': 'gzip, deflate, br',
    'Referer': 'https://www.nseindia.com/option-chain',
    'Connection': 'keep-alive'
}

s = requests.Session()
print('=== page load ===')
try:
    r = s.get('https://www.nseindia.com/option-chain', headers=headers, timeout=20)
    print('PAGE', r.status_code, r.headers.get('content-type'))
    print('COOKIES', s.cookies.get_dict())
except Exception as e:
    print('PAGE ERROR', e)

print('=== contract info ===')
try:
    ci = s.get('https://www.nseindia.com/api/option-chain-contract-info?symbol=NIFTY', headers=headers, timeout=20)
    print('contract-info', ci.status_code, ci.headers.get('content-type'))
    print(ci.text[:1200])
    try:
        data = ci.json()
        expiry = data.get('records', {}).get('expiryDates', [None])[0] or data.get('expiry')
        print('expiry', expiry)
    except Exception as ex:
        print('PARSE CONTRACT INFO ERROR', ex)
        expiry = None
except Exception as e:
    print('CONTRACT INFO ERROR', e)
    expiry = None

if expiry:
    print('=== option-chain-v3 ===')
    try:
        url = f'https://www.nseindia.com/api/option-chain-v3?type=Indices&symbol=NIFTY&expiry={expiry}'
        chain = s.get(url, headers=headers, timeout=20)
        print('option-chain-v3', chain.status_code, chain.headers.get('content-type'))
        print(chain.text[:1200])
    except Exception as e:
        print('OPTION CHAIN V3 ERROR', e)
