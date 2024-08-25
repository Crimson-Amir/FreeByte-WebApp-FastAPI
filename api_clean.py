import requests, crud, json
from private import auth, telegram_bot_token, ADMIN_CHAT_IDs

telegram_bot_url = f"https://api.telegram.org/bot{telegram_bot_token}/"

class XuiApiClean:
    server_details = {}

    def __init__(self, database):
        super().__init__('v2ray')
        self.connect = requests.Session()
        self.refresh_connecion()
        self.db = database

    def refresh_connecion(self):
        make_db = self.db()
        get_domains = crud.get_all_server(make_db)

        for server in get_domains:
            login = self.connect.post(f'{server.protocol}{server.server_address}:{server.server_port}/login', data=auth)

            self.server_details[server.server_address] = {
                'cookie': login.cookies,
                'protocol': server.protocol,
                'server_port': server.server_port,
            }

            if login.status_code != 200:
                print(f'Connection Problem. {login.status_code}')

    @staticmethod
    def send_telegram_message(message):
        requests.post(f'{telegram_bot_url}/sendMessage', data={'chat_id': ADMIN_CHAT_IDs[0], "text": message})

    def make_request(self, method, url, domain, json_data=None):
        try:
            cookie = self.server_details.get(domain, {}).get('cookie', {})

            with self.connect.request(method, url, json=json_data, cookies=cookie, timeout=5) as response:
                response.raise_for_status()
                connection_response = response.json()

                if not connection_response.get('success', False):

                    text = (f'🔴 Xui Api Response Success Is False [WEB APP]\n'
                            f'connection_response: {connection_response}\n'
                            f'url: {response.url}')

                    self.send_telegram_message(text)
                    raise ConnectionError(text)

                return connection_response

        except Exception as e:
            text = f'🔴 Connection problem in Xui Api [WEB APP]\ncode: {response.status_code}\nurl: {response.url}'
            self.send_telegram_message(text)
            raise e

    def get_all_inbounds(self):
        make_db = self.db()
        get_domains = crud.get_all_server(make_db)
        all_inbound = [
            self.make_request(
                'get', f'{server.protocol}{server.server_address}:{server.server_port}/panel/api/inbounds/list',
                domain=server.server_address
            ) for server in get_domains
        ]
        return all_inbound

    def get_server_url(self, domain, endpoint):
        server_detail = self.server_details[domain]
        protocol = server_detail['protocol']
        port = server_detail['server_port']
        return f"{protocol}{domain}:{port}/panel/api/{endpoint}"

    def get_country_inbounds(self, domain):
        url = self.get_server_url(domain, 'inbounds/list')
        return self.make_request('get', url, domain)

    def get_inbound(self, inbound_id, domain):
        url = self.get_server_url(domain, f'inbounds/get/{inbound_id}')
        return self.make_request('get', url, domain)

    def get_client(self, client_email, domain):
        url = self.get_server_url(domain, f'inbounds/getClientTraffics/{client_email}')
        return self.make_request('get', url, domain)

    def add_inbound(self, data, domain):
        url = self.get_server_url(domain, 'inbounds/add')
        return self.make_request('post', url, domain, data)

    def add_client(self, data, domain):
        url = self.get_server_url(domain, 'inbounds/addClient')
        return self.make_request('post', url, domain, data)

    def update_inbound(self, inbound_id, data, domain):
        url = self.get_server_url(domain, f'inbounds/update/{inbound_id}')
        return self.make_request('post', url, domain, data)

    def reset_client_traffic(self, inbound_id, email, domain):
        url = self.get_server_url(domain, f'inbounds/{inbound_id}/resetClientTraffic/{email}')
        return self.make_request('post', url, domain)

    def update_client(self, uuid, data, domain):
        url = self.get_server_url(domain, f'inbounds/updateClient/{uuid}')
        return self.make_request('post', url, domain, data)

    def del_inbound(self, inbound_id, domain):
        url = self.get_server_url(domain, f'inbounds/del/{inbound_id}')
        return self.make_request('post', url, domain)

    def del_client(self, inboundid, uuid, domain):
        url = self.get_server_url(domain, f'inbounds/{inboundid}/delClient/{uuid}')
        return self.make_request('post', url, domain)

    def del_depleted_clients(self, domain, inbound_id):
        url = self.get_server_url(domain, f'inbounds/delDepletedClients/{inbound_id}')
        return self.make_request('post', url, domain)

    def get_client_url(
            self, client_email, inbound_id, domain=None, header_type="http",
            host="ponisha.ir", default_config_schematic=None, server_domain=None
    ):
        if default_config_schematic is None:
            default_config_schematic = "vless://{}@{}:{}?security=none&host={}&headerType={}&type={}#{} {}"

        inbound_data = self.get_inbound(inbound_id, server_domain)
        if not inbound_data['success']:
            return False

        domain = domain or 'human.ggkala.shop'
        port = inbound_data['obj']['port']
        remark = inbound_data['obj']['remark']
        clients = json.loads(inbound_data['obj']['settings'])['clients']
        network = json.loads(inbound_data['obj']['streamSettings'])['network']

        for client in clients:
            if client['email'] == client_email:
                return default_config_schematic.format(
                    client['id'], domain, port, host, header_type,
                    network, remark, client['email']
                )

        return False

    def get_ips(self, email, domain):
        url = self.get_server_url(domain, f'inbounds/clientIps/{email}')
        return self.make_request('post', url, domain)

    def delete_depleted_clients(self, inbound_id, domain):
        url = self.get_server_url(domain, f'inbounds/delDepletedClients/{inbound_id}')
        return self.make_request('post', url, domain)

    def get_onlines(self, domain):
        url = self.get_server_url(domain, f'inbounds/onlines')
        return self.make_request('post', url, domain)

    def restart_xray(self, domain):
        server_detail = self.server_details[domain]
        protocol = server_detail['protocol']
        port = server_detail['server_port']

        inb = self.make_request('post', f'{protocol}{domain}:{port}/server/restartXrayService', domain=domain)
        return inb


# test = XuiApiClean()
# a = test.get_client(1012)
# print(a)