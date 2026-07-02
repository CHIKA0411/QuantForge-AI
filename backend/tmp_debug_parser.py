import sys, datetime
from typing import Any, List
sys.path.append('backend')
from app.nse_client import nse_client

raw_json = nse_client.fetch_live_data('NIFTY')
print('raw_json keys', raw_json.keys())
wrapper_records = raw_json.get('records') if isinstance(raw_json, dict) else None
records = wrapper_records if isinstance(wrapper_records, dict) else raw_json
print('records type', type(records), 'keys', list(records.keys()))

def _normalize_expiry_dates(expiry_dates: Any) -> List[str]:
    if isinstance(expiry_dates, str):
        return [expiry_dates]
    if isinstance(expiry_dates, list):
        return [item for item in expiry_dates if isinstance(item, str)]
    return []

filtered_payload = raw_json.get('filtered') if isinstance(raw_json, dict) else None
if not isinstance(filtered_payload, dict) and isinstance(records, dict):
    filtered_payload = records.get('filtered')
filtered_data = filtered_payload.get('data') if isinstance(filtered_payload, dict) else None
print('filtered_payload type', type(filtered_payload), 'filtered_data type', type(filtered_data), 'filtered_len', len(filtered_data) if isinstance(filtered_data, list) else None)

data = records.get('data', [])
print('data len', len(data))
expiry_dates = _normalize_expiry_dates(records.get('expiryDates', []))
print('expiry_dates', expiry_dates[:5], 'len', len(expiry_dates))
target_expiry_str = expiry_dates[0]
print('target', target_expiry_str)
option_chain_list = []
for item in data:
    expiry_str = item.get('expiryDates') or item.get('expiryDate')
    if expiry_str != target_expiry_str:
        continue
    for opt_type in ['CE','PE']:
        opt_data = item.get(opt_type, {})
        if not opt_data:
            continue
        strike = float(opt_data.get('strikePrice', item.get('strikePrice', 0.0)) or 0.0)
        option_chain_list.append((strike, opt_type))
print('option_chain_list len', len(option_chain_list))
print(option_chain_list[:5])
