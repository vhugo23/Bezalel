from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_pages():
    for path in ["/", "/plan", "/session/x", "/report/x", "/lesson/x", "/season"]:
        assert client.get(path).status_code == 200


def test_api_stubs():
    assert client.post("/api/plans", json={"job_posting": "j", "resume": "r"}).status_code == 200
    plan = client.post("/api/plans", json={"job_posting": "j", "resume": "r"}).json()
    sid = client.post("/api/sessions", json={"plan_id": plan["plan_id"]}).json()["session_id"]
    assert client.post(f"/api/sessions/{sid}/turns", json={"answer": "hi"}).status_code == 200
    assert client.post("/api/sessions/x/probe", json={"node": "n1"}).status_code == 200
    assert client.post("/api/sessions/x/end").status_code == 200
    assert client.get("/api/sessions/x/report").status_code == 200
    assert client.get("/api/lessons/x").status_code == 200
    assert client.post("/api/retests", json={"topics": []}).status_code == 200
    assert client.get("/api/season").status_code == 200
