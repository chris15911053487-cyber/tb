import responses
import pytest
from auth import TeambitionAuth
from api_client import APIClient, APIError


@pytest.fixture
def auth():
    a = TeambitionAuth(app_id="x", app_secret="y", org_id="z")
    a._token = "test-token"  # 跳过真实 token 请求
    a._expires_at = float("inf")
    return a


@pytest.fixture
def client(auth):
    return APIClient(auth)


@responses.activate
def test_get_request_sends_auth_headers(client):
    responses.add(
        responses.GET,
        "https://open.teambition.com/api/v3/test",
        json={"result": "ok"},
        status=200,
    )
    data = client.get("/v3/test")
    assert data == {"result": "ok"}
    req_headers = responses.calls[0].request.headers
    assert req_headers["Authorization"] == "Bearer test-token"
    assert req_headers["X-Tenant-Id"] == "z"


@responses.activate
def test_get_raises_api_error_on_failure(client):
    responses.add(
        responses.GET,
        "https://open.teambition.com/api/v3/fail",
        json={"error": "not_found"},
        status=404,
    )
    with pytest.raises(APIError, match="404"):
        client.get("/v3/fail")


@responses.activate
def test_paginate_single_page(client):
    responses.add(
        responses.GET,
        "https://open.teambition.com/api/v3/items",
        json={"result": [{"id": 1}, {"id": 2}], "nextPageToken": ""},
        status=200,
    )
    items = list(client.paginate("/v3/items"))
    assert len(items) == 2
    assert items[0]["id"] == 1
    assert items[1]["id"] == 2


@responses.activate
def test_paginate_multiple_pages(client):
    responses.add(
        responses.GET,
        "https://open.teambition.com/api/v3/items",
        json={"result": [{"id": 1}, {"id": 2}], "nextPageToken": "tok-page2"},
        status=200,
        match=[responses.matchers.query_param_matcher({"pageSize": "50"})],
    )
    responses.add(
        responses.GET,
        "https://open.teambition.com/api/v3/items",
        json={"result": [{"id": 3}], "nextPageToken": ""},
        status=200,
        match=[responses.matchers.query_param_matcher({"pageSize": "50", "pageToken": "tok-page2"})],
    )
    items = list(client.paginate("/v3/items"))
    assert len(items) == 3
    ids = [item["id"] for item in items]
    assert ids == [1, 2, 3]


@responses.activate
def test_paginate_respects_custom_page_size(client):
    responses.add(
        responses.GET,
        "https://open.teambition.com/api/v3/items",
        json={"result": [], "nextPageToken": ""},
        status=200,
        match=[responses.matchers.query_param_matcher({"pageSize": "20"})],
    )
    list(client.paginate("/v3/items", page_size=20))
    assert len(responses.calls) == 1


@responses.activate
def test_paginate_merges_extra_params(client):
    responses.add(
        responses.GET,
        "https://open.teambition.com/api/v3/items",
        json={"result": [], "nextPageToken": ""},
        status=200,
        match=[
            responses.matchers.query_param_matcher(
                {"pageSize": "50", "orderBy": "created"}
            )
        ],
    )
    list(client.paginate("/v3/items", params={"orderBy": "created"}))
    assert len(responses.calls) == 1


@responses.activate
def test_post_request(client):
    responses.add(
        responses.POST,
        "https://open.teambition.com/api/v3/search",
        json={"result": [{"id": 9}]},
        status=200,
    )
    data = client.post("/v3/search", json={"query": "test"})
    assert data == {"result": [{"id": 9}]}
