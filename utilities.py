import logging
from . import panel_api
from .database import SessionLocal
import jwt, aiohttp, pytz, random, string, requests
from datetime import datetime, timedelta
from.auth import SECRET_KEY
from .private import ADMIN_CHAT_IDs, telegram_bot_token, telegram_thread_id

def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()


class SendRequest:
    @staticmethod
    async def send_request(method, url, params=None, json_data=None, data=None, header=None, session_header=None):
        async with aiohttp.ClientSession(headers=session_header) as session:
            async with session.request(method, url, params=params, json=json_data, data=data, headers=header) as response:
                return await response.json()

async def decode_access_token(request, all_=False):
    if not request.state.user:
        return

    decode_data = jwt.decode(request.state.user, SECRET_KEY, algorithms=["HS256"])
    if not all_: return decode_data.get('user_id')
    return decode_data

class ConnectToServer:
    api_operation = panel_api.marzban_api
    last_update = None

    def refresh_token(self):
        now = datetime.now()
        if self.last_update:
            if (self.last_update + timedelta(minutes=5)) < now:
                self.api_operation.refresh_connection()
                self.last_update = now
        else:
            self.api_operation.refresh_connection()
            self.last_update = now

class TokenBlackList:
    def __init__(self): self.black_list = set()
    def add(self, token): self.black_list.add(token)
    def is_blacklisted(self, token): return token in self.black_list

async def calculate_total_price(purchase_associations):
    try:
        return sum([purchase.purchase.price * purchase.count for purchase in purchase_associations])
    except Exception as e:
        logging.error(f'Error occurred in calculate_total_price:\n{e}')

def second_to_ms(date, time_to_ms: bool = True):
    if time_to_ms:
        return int(date.timestamp() * 1000)
    else:
        return datetime.fromtimestamp(date)

def traffic_to_gb(traffic, byte_to_gb:bool = True):
    if byte_to_gb:
        return traffic / (1024 ** 3)
    else:
        return int(traffic * (1024 ** 3))



def generate_random_string(length=5):
    characters = string.ascii_letters + string.digits
    random_string = ''.join(random.choice(characters) for _ in range(length))
    return random_string

async def report_status_to_admin(text, status='success', owner=None):
    try:
        status_emoji = {
            'success': '🟢',
            'error': '🔴'
        }

        text = (f'{status_emoji.get(status)} Web app {status} report'
                f'\n\n{text}')

        if owner:
            text += ('\n\n👤 User Info:'
                     f'\nUser ID: {owner.user_id}'
                     f'\nEmail: {owner.email}'
                     f'\nName: {owner.name}')

        telegram_bot_url = f"https://api.telegram.org/bot{telegram_bot_token}/sendMessage"
        requests.post(telegram_bot_url, data={'chat_id': ADMIN_CHAT_IDs[0], 'text': text, 'message_thread_id': telegram_thread_id})
    except Exception as e:
        print(f'Failed to send message to ADMIN {e}')

async def remove_service_from_server(purchase):
    connect_to_server_instance.refresh_token()
    await connect_to_server_instance.api_operation.remove_user(purchase.product.main_server.server_ip,purchase.username)



token_black_list = TokenBlackList()
connect_to_server_instance = ConnectToServer()