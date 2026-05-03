"""Teambition API 鉴权与 Token 管理."""
import time
import requests

BASE_URL = "https://open.teambition.com/api"


class AuthError(Exception):
    """Token 获取失败。"""


class TeambitionAuth:
    def __init__(self, app_id, app_secret, org_id, base_url=BASE_URL):
        self.app_id = app_id
        self.app_secret = app_secret
        self.org_id = org_id
        self.base_url = base_url
        self._token = None
        self._expires_at = 0.0
        self._operator_id = None

    def get_token(self):
        now = time.time()
        if self._token and now < self._expires_at - 60:
            return self._token

        resp = requests.post(
            f"{self.base_url}/appToken",
            json={"appId": self.app_id, "appSecret": self.app_secret},
            timeout=30,
        )
        if not resp.ok:
            raise AuthError(
                f"Token request failed: {resp.status_code} {resp.text}"
            )

        data = resp.json()
        self._token = data["appToken"]
        self._expires_at = now + data.get("expire", 1800)
        return self._token

    def get_operator_id(self):
        """获取企业拥有者的 userId，用作 X-Operator-Id。"""
        if self._operator_id:
            return self._operator_id
        resp = requests.get(
            f"{self.base_url}/org/owners",
            headers=self.headers,
            timeout=30,
        )
        if resp.ok:
            data = resp.json()
            owners = data.get("result", [])
            if owners:
                self._operator_id = owners[0].get("userId", "")
        if not self._operator_id:
            raise AuthError("无法获取企业拥有者信息作为 Operator ID")
        return self._operator_id

    @property
    def headers(self):
        return {
            "Authorization": f"Bearer {self.get_token()}",
            "X-Tenant-Id": self.org_id,
            "X-Tenant-Type": "organization",
        }

    @property
    def operator_headers(self):
        """带 X-Operator-Id 的请求头，用于需要用户上下文的接口。"""
        h = dict(self.headers)
        h["X-Operator-Id"] = self.get_operator_id()
        return h
