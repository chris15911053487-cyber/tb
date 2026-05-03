"""HTTP 客户端：重试、超时、分页遍历."""
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class APIError(Exception):
    """API 调用失败（非 2xx 响应）。"""


class APIClient:
    def __init__(self, auth, max_retries=3, timeout=30):
        self.auth = auth
        self.timeout = timeout
        self.session = requests.Session()
        retry_strategy = Retry(
            total=max_retries,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST"],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("https://", adapter)

    def request(self, method, path, **kwargs):
        url = f"{self.auth.base_url}{path}"
        kwargs.setdefault("timeout", self.timeout)
        kwargs.setdefault("headers", self.auth.operator_headers)
        resp = self.session.request(method, url, **kwargs)
        data = resp.json()
        code = data.get("code", 0)
        if code not in (0, 200):
            raise APIError(
                f"{method} {path} failed: code={code} "
                f"{data.get('errorMessage', data.get('errorCode', ''))}"
            )
        return data

    def get(self, path, params=None):
        return self.request("GET", path, params=params)

    def post(self, path, json=None, params=None):
        return self.request("POST", path, json=json, params=params)

    def paginate(self, path, params=None, page_size=50):
        """遍历所有分页，逐条 yield 结果项。"""
        params = (params or {}).copy()
        params["pageSize"] = page_size
        while True:
            data = self.get(path, params)
            result = data.get("result")
            if result:
                yield from result
            next_token = data.get("nextPageToken")
            if not next_token:
                break
            params["pageToken"] = next_token
