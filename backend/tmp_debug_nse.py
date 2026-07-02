import sys
sys.path.append('backend')
from app.nse_client import nse_client

raw = nse_client.fetch_live_data('NIFTY')
result = nse_client.parse_nse_json('NIFTY', raw)
print('options_len', len(result['options']))
print('options_sample', result['options'][:5])
