import os, sys, requests
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import crud
from database import SessionLocal

class MarzbanAPI:
    def __init__(self):
        self.servers_bearer_token = {}
        self.session = requests.Session()
        self.refresh_connection()

    def make_request(self, method, url, **kwargs):
        """Make an HTTP request and return JSON response."""
        response = self.session.request(method, url, **kwargs)
        response.raise_for_status()
        return response.json()

    def get_server_access_token(self, server):
        """Retrieve access token for a given server."""
        admin_token_url = 'api/admin/token'
        url = f"{server.server_protocol}{server.server_ip}:{server.server_port}/{admin_token_url}"
        data = {'username': server.server_username, 'password': server.server_password}
        return self.make_request('post', url=url, data=data)

    def refresh_connection(self):
        """Refresh access tokens for all servers."""
        with SessionLocal() as session:
            servers = crud.get_all_main_servers(session)
            for server in servers:
                response = self.get_server_access_token(server)
                self.servers_bearer_token[server.server_ip] = {
                    'access_token': response['access_token'],
                    'server_instant': server
                }

    @staticmethod
    def build_full_url(server, endpoint):
        """Construct full URL for a server and endpoint."""
        return f"{server.server_protocol}{server.server_ip}:{server.server_port}{endpoint}"

    def initialize_request(self, main_server_ip, endpoint):
        """Initialize the request by returning URL and headers."""
        access_token, server = self.servers_bearer_token[main_server_ip].values()
        headers = {'Authorization': f"Bearer {access_token}"}
        full_url = self.build_full_url(server, endpoint)
        return full_url, headers

    async def user_subscription_info(self, main_server_ip, token):
        """Retrieve user subscription info."""
        endpoint = f"/sub/{token}/info"
        url, headers = self.initialize_request(main_server_ip, endpoint)
        return self.make_request('get', url, headers=headers)

    async def get_system_stats(self, main_server_ip):
        """Retrieve system statistics."""
        endpoint = "/api/system"
        url, headers = self.initialize_request(main_server_ip, endpoint)
        return self.make_request('get', url, headers=headers)

    async def get_inbounds(self, main_server_ip):
        """Retrieve inbound statistics."""
        endpoint = "/api/inbounds"
        url, headers = self.initialize_request(main_server_ip, endpoint)
        return self.make_request('get', url, headers=headers)

    async def get_host(self, main_server_ip):
        """Retrieve host statistics."""
        endpoint = "/api/hosts"
        url, headers = self.initialize_request(main_server_ip, endpoint)
        return self.make_request('get', url, headers=headers)

    async def get_core_stats(self, main_server_ip):
        """Retrieve core statistics."""
        endpoint = "/api/core"
        url, headers = self.initialize_request(main_server_ip, endpoint)
        return self.make_request('get', url, headers=headers)


    async def restart_core(self, main_server_ip):
        """Restart core service."""
        endpoint = "/api/core/restart"
        url, headers = self.initialize_request(main_server_ip, endpoint)
        return self.make_request('post', url, headers=headers)

    async def add_user(self, main_server_ip, user_data):
        """Add a new user."""
        endpoint = "/api/user"
        url, headers = self.initialize_request(main_server_ip, endpoint)
        return self.make_request('post', url, headers=headers, json=user_data)

    async def get_user(self, main_server_ip, username):
        """Retrieve a user by username."""
        endpoint = f"/api/user/{username}"
        url, headers = self.initialize_request(main_server_ip, endpoint)
        return self.make_request('get', url, headers=headers)

    async def modify_user(self, main_server_ip, username, user_data):
        """Modify user details."""
        endpoint = f"/api/user/{username}"
        url, headers = self.initialize_request(main_server_ip, endpoint)
        return self.make_request('put', url, headers=headers, json=user_data)

    async def remove_user(self, main_server_ip, username):
        """Remove a user."""
        endpoint = f"/api/user/{username}"
        url, headers = self.initialize_request(main_server_ip, endpoint)
        return self.make_request('delete', url, headers=headers)

    async def delete_expired_users(self, main_server_ip):
        """Delete expired users."""
        endpoint = "/api/users/expired"
        url, headers = self.initialize_request(main_server_ip, endpoint)
        return self.make_request('delete', url, headers=headers)

    async def get_users(self, main_server_ip):
        """Retrieve all users."""
        endpoint = "/api/users"
        url, headers = self.initialize_request(main_server_ip, endpoint)
        return self.make_request('get', url, headers=headers)

    async def get_nodes(self, main_server_ip):
        """Retrieve node statistics."""
        endpoint = "/api/nodes"
        url, headers = self.initialize_request(main_server_ip, endpoint)
        return self.make_request('get', url, headers=headers)

    async def get_nodes_usage(self, main_server_ip):
        """Retrieve node usage statistics."""
        endpoint = "/api/nodes/usage"
        url, headers = self.initialize_request(main_server_ip, endpoint)
        return self.make_request('get', url, headers=headers)

    async def reset_user_data_usage(self, main_server_ip, username):
        """Retrieve node usage statistics."""
        endpoint = f"/api/user/{username}/reset"
        url, headers = self.initialize_request(main_server_ip, endpoint)
        return self.make_request('post', url, headers=headers)


marzban_api = MarzbanAPI()
