import responses
import time
import pytest
from auth import TeambitionAuth, AuthError


@responses.activate
def test_get_token_makes_correct_request():
    """首次调用 get_token 应向正确 URL 发送 POST 请求并返回 token。"""
    responses.add(
        responses.POST,
        "https://open.teambition.com/api/appToken",
        json={"appToken": "tok-abc123", "expire": 7200},
        status=200,
    )
    auth = TeambitionAuth(app_id="my-app", app_secret="my-secret", org_id="org-1")
    token = auth.get_token()
    assert token == "tok-abc123"
    assert len(responses.calls) == 1
    body = responses.calls[0].request.body
    assert b"my-app" in body
    assert b"my-secret" in body


@responses.activate
def test_get_token_caches_within_expiry():
    """有效期内重复调用 get_token 不发起新请求，使用缓存。"""
    responses.add(
        responses.POST,
        "https://open.teambition.com/api/appToken",
        json={"appToken": "tok-first", "expire": 7200},
        status=200,
    )
    auth = TeambitionAuth(app_id="a", app_secret="s", org_id="o")
    t1 = auth.get_token()
    t2 = auth.get_token()
    assert t1 == "tok-first"
    assert t2 == "tok-first"
    assert len(responses.calls) == 1  # 只调用了一次 API


@responses.activate
def test_get_token_refreshes_after_expiry():
    """Token 过期后重新请求新 token。"""
    responses.add(
        responses.POST,
        "https://open.teambition.com/api/appToken",
        json={"appToken": "tok-new", "expire": 0},  # 立即过期
        status=200,
    )
    auth = TeambitionAuth(app_id="a", app_secret="s", org_id="o")
    auth.get_token()
    # 第二次调用时 token 已过期，应重新请求
    responses.add(
        responses.POST,
        "https://open.teambition.com/api/appToken",
        json={"appToken": "tok-newer", "expire": 7200},
        status=200,
    )
    t = auth.get_token()
    assert t == "tok-newer"
    assert len(responses.calls) == 2


@responses.activate
def test_get_token_raises_on_http_error():
    """API 返回非 2xx 时抛出 AuthError。"""
    responses.add(
        responses.POST,
        "https://open.teambition.com/api/appToken",
        json={"error": "invalid_client"},
        status=401,
    )
    auth = TeambitionAuth(app_id="bad", app_secret="bad", org_id="o")
    with pytest.raises(AuthError):
        auth.get_token()


@responses.activate
def test_headers_property_includes_token_and_org():
    """headers 属性返回正确的鉴权头。"""
    responses.add(
        responses.POST,
        "https://open.teambition.com/api/appToken",
        json={"appToken": "tok-hdr", "expire": 7200},
        status=200,
    )
    auth = TeambitionAuth(app_id="a", app_secret="s", org_id="org-xyz")
    h = auth.headers
    assert h["Authorization"] == "Bearer tok-hdr"
    assert h["X-Tenant-Id"] == "org-xyz"
    assert h["X-Tenant-Type"] == "organization"
