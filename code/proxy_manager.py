import os
from g2a_config import PROXY_FILE

PROXY_ROTATION_COUNT = 15
class ProxyManager:
    def __init__(self):
        self.proxies = []
        self.current_index = 0
        self.request_count = 0
        self.load_proxies()

    def load_proxies(self):
        if not os.path.exists(PROXY_FILE):
            print("proxy.txt not found, working without proxies")
            return

        with open(PROXY_FILE, 'r') as f:
            for line in f:
                line = line.strip()
                if line and ':' in line:
                    parts = line.split('@')
                    if len(parts) == 2:
                        auth, address = parts
                        login, password = auth.split(':')
                        ip, port = address.split(':')

                        proxy_url = f"http://{login}:{password}@{ip}:{port}"
                        self.proxies.append(proxy_url)
                    else:
                        proxy_url = f"http://{line}"
                        self.proxies.append(proxy_url)


    def get_current_proxy(self):
        if not self.proxies:
            return None
        return self.proxies[self.current_index]

    def should_rotate(self, status_code=None):
        if status_code == 429:
            return True

        self.request_count += 1
        if self.request_count >= PROXY_ROTATION_COUNT:
            return True

        return False

    def rotate_proxy(self):
        if not self.proxies:
            return

        self.current_index = (self.current_index + 1) % len(self.proxies)
        self.request_count = 0

    def has_proxies(self):
        return len(self.proxies) > 0