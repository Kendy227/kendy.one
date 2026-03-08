import hashlib
import time
import requests

class SmileOneAPI:
    BASE_URLS = {
        'default': 'https://www.smile.one',
        'br': 'https://www.smile.one/br',
        'ru': 'https://www.smile.one/ru',
        'ph': 'https://www.smile.one/ph'
    }

    def __init__(self, email, uid, key, region='default'):
        self.email = email
        self.uid = uid
        self.key = key
        self.region = region.lower()
        self.base_url = self.BASE_URLS.get(self.region, self.BASE_URLS['default'])
    
    def generate_sign(self, params: dict) -> str:
        """
        Generate Smile.one API sign parameter.
        All params are sorted by key, concatenated as key1=value1&key2=value2&...&key,
        then double MD5 hashed.
        """
        # Sort parameters by key
        sorted_items = sorted(params.items())
        # Build the string with no separator between key-value pairs
        sign_str = ''.join(f"{k}={v}&" for k, v in sorted_items)
        sign_str += self.key
        # Double MD5 hash
        first_md5 = hashlib.md5(sign_str.encode('utf-8')).hexdigest()
        final_md5 = hashlib.md5(first_md5.encode('utf-8')).hexdigest()
        return final_md5

    def create_order(self, userid, zoneid, product, productid):
        """
        Create a new order using Smile.one regional API
        """
        endpoint = f"{self.base_url}/smilecoin/api/createorder"
        
        # Prepare parameters
        params = {
            'email': self.email,
            'uid': self.uid,
            'userid': userid,
            'zoneid': zoneid,
            'product': product,
            'productid': productid,
            'time': int(time.time())
        }
        
        # Generate signature
        params['sign'] = self.generate_sign(params)
        
        try:
            response = requests.post(endpoint, data=params, timeout=15)
            response_data = response.json()
            if response_data.get('status') != 200:
                return {"status": "error", "message": response_data.get('message', 'Order creation failed')}
            return response_data
        except requests.RequestException as e:
            return {"status": "error", "message": str(e)}
        except Exception as e:
            return {'status': 500, 'message': f'API Error: {str(e)}'}
            
    def check_order_status(self, order_id):
        """
        Check order status using Smile.one API
        """
        endpoint = f"{self.base_url}/api/status"
        
        params = {
            'email': self.email,
            'uid': self.uid,
            'order_id': order_id,
            'time': int(time.time())
        }
        
        params['sign'] = self.generate_sign(params)
        
        try:
            response = requests.post(endpoint, data=params)
            return response.json()
        except Exception as e:
            return {'status': 500, 'message': f'API Error: {str(e)}'}