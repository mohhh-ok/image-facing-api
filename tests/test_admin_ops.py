"""admin の運用エンドポイント検証: サンプル削除 / API キー回転。"""

from __future__ import annotations

import base64

from tests.conftest import create_project, image_bytes, make_image


def _b64(side: str) -> str:
    return base64.b64encode(image_bytes(make_image(side))).decode("ascii")


def _label(client, project, key, side, facing):
    return client.post(
        f"/v1/{project}/label",
        json={"image_base64": _b64(side), "facing": facing},
        headers={"X-API-Key": key},
    )


def _counts(client, admin_auth, project):
    for p in client.get("/v1/projects", auth=admin_auth).json():
        if p["project"] == project:
            return p["sample_count"], p["label_count"]
    return None


# --- サンプル削除 -------------------------------------------------------


def test_admin_delete_removes_original_and_flip(client, admin_auth):
    key = create_project(client, admin_auth)
    sid = _label(client, "proj", key, "left", "left").json()["sample_id"]
    assert _counts(client, admin_auth, "proj") == (2, 1)  # 原本 + flip

    resp = client.post(
        "/admin/delete", data={"project": "proj", "sample_id": str(sid)}, auth=admin_auth
    )
    assert resp.status_code == 200, resp.text  # 303 で /admin に追従
    assert _counts(client, admin_auth, "proj") == (0, 0)  # 原本+flip とも消えた


def test_admin_delete_requires_auth(client, admin_auth):
    key = create_project(client, admin_auth)
    sid = _label(client, "proj", key, "left", "left").json()["sample_id"]
    resp = client.post("/admin/delete", data={"project": "proj", "sample_id": str(sid)})
    assert resp.status_code == 401


def test_admin_delete_rejects_cross_origin(client, admin_auth):
    key = create_project(client, admin_auth)
    sid = _label(client, "proj", key, "left", "left").json()["sample_id"]
    resp = client.post(
        "/admin/delete",
        data={"project": "proj", "sample_id": str(sid)},
        auth=admin_auth,
        headers={"Origin": "http://evil.example"},
    )
    assert resp.status_code == 403


def test_admin_delete_rejects_flip_child(client, admin_auth):
    key = create_project(client, admin_auth)
    sid = _label(client, "proj", key, "left", "left").json()["sample_id"]
    child = client.get("/admin?project=proj&show_flip=true", auth=admin_auth)
    assert child.status_code == 200
    # flip 子（次の id）を狙っても原本以外は拒否される
    resp = client.post(
        "/admin/delete", data={"project": "proj", "sample_id": str(sid + 1)}, auth=admin_auth
    )
    assert resp.status_code == 400


def test_predict_misses_after_delete(client, admin_auth):
    """削除後はインメモリ index からも消え、近傍が無くなる。"""
    key = create_project(client, admin_auth)
    sid = _label(client, "proj", key, "left", "left").json()["sample_id"]
    before = client.post(
        "/v1/proj/predict", json={"image_base64": _b64("left")}, headers={"X-API-Key": key}
    ).json()
    assert before["neighbors"]  # 近傍あり

    client.post("/admin/delete", data={"project": "proj", "sample_id": str(sid)}, auth=admin_auth)

    after = client.post(
        "/v1/proj/predict", json={"image_base64": _b64("left")}, headers={"X-API-Key": key}
    ).json()
    assert not after["neighbors"]  # index から消えた


# --- API キー回転 -------------------------------------------------------


def test_rotate_key_invalidates_old(client, admin_auth):
    key = create_project(client, admin_auth)
    resp = client.post("/v1/projects/proj/rotate_key", auth=admin_auth)
    assert resp.status_code == 200, resp.text
    new_key = resp.json()["api_key"]
    assert new_key.startswith("fk_live_") and new_key != key

    img = {"image_base64": _b64("left")}
    assert client.post("/v1/proj/predict", json=img, headers={"X-API-Key": key}).status_code == 403
    assert (
        client.post("/v1/proj/predict", json=img, headers={"X-API-Key": new_key}).status_code == 200
    )


def test_rotate_key_requires_admin(client, admin_auth):
    create_project(client, admin_auth)
    assert client.post("/v1/projects/proj/rotate_key").status_code == 401


def test_rotate_key_rejects_cross_origin(client, admin_auth):
    create_project(client, admin_auth)
    resp = client.post(
        "/v1/projects/proj/rotate_key",
        auth=admin_auth,
        headers={"Origin": "http://evil.example"},
    )
    assert resp.status_code == 403


def test_rotate_key_unknown_project(client, admin_auth):
    create_project(client, admin_auth)
    assert client.post("/v1/projects/ghost/rotate_key", auth=admin_auth).status_code == 400
