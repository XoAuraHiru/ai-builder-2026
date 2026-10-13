"""Starting the live checks: one at a time, one an hour, through the Cloud Run job."""
from app.config import get_settings
from app.governance import launcher

OMAR = {"X-Dev-User": "omar@atrium.demo"}
JOB = "projects/p/locations/us-central1/jobs/atrium-evals"


def test_with_no_job_configured_the_free_tier_runs_in_process(client, staff):
    started = client.post("/governance/evals/run", headers=OMAR)
    assert started.status_code == 202 and started.json()["tier"] == "free" and started.json()["status"] == "finished"
    assert started.json()["trigger"] == "local" and started.json()["requested_by"] == "Omar Haddad"
    assert client.get("/governance/runs", headers=OMAR).json()[0]["id"] == started.json()["id"]


def test_the_button_starts_the_job_once_and_then_waits(client, staff, monkeypatch):
    monkeypatch.setattr(get_settings(), "evals_job", JOB)
    launched = []
    monkeypatch.setattr(launcher, "launch_job", lambda name: launched.append(name) or "exec-1")
    first = client.post("/governance/evals/run", headers=OMAR)
    assert first.status_code == 202 and first.json()["status"] == "running" and launched == [JOB]
    second = client.post("/governance/evals/run", headers=OMAR)
    assert second.status_code == 409 and "still going" in second.json()["detail"]
    assert launched == [JOB]


def test_a_job_that_cannot_start_marks_the_run_failed(client, staff, monkeypatch):
    monkeypatch.setattr(get_settings(), "evals_job", JOB)

    def refuse(name):
        raise launcher.LaunchError("permission denied")

    monkeypatch.setattr(launcher, "launch_job", refuse)
    response = client.post("/governance/evals/run", headers=OMAR)
    assert response.status_code == 503 and "could not be started" in response.json()["detail"]
    assert client.get("/governance/runs", headers=OMAR).json()[0]["status"] == "failed"


def test_monitoring_is_for_compliance(client, staff):
    assert client.get("/governance/monitoring", headers={"X-Dev-User": "mei@atrium.demo"}).status_code == 403
    body = client.get("/governance/monitoring", headers=OMAR).json()
    assert "agreement" in body and body["agreement"]["reconciler_agent"]["rate"] is None


def test_runs_are_for_compliance_and_one_run_lists_its_suites(client, staff):
    assert client.get("/governance/runs", headers={"X-Dev-User": "mei@atrium.demo"}).status_code == 403
    assert client.post("/governance/evals/run", headers={"X-Dev-User": "mei@atrium.demo"}).status_code == 403
    run = client.post("/governance/evals/run", headers=OMAR).json()
    one = client.get(f"/governance/runs/{run['id']}", headers=OMAR).json()
    assert one["id"] == run["id"] and one["suites"] and {"model_key", "kind", "tier", "metric"} <= set(one["suites"][0])
    assert client.get("/governance/runs/nope", headers=OMAR).status_code == 404
    assert len(client.get("/governance/runs?limit=1", headers=OMAR).json()) == 1


def test_a_model_card_keeps_each_suites_cases_apart(client, staff):
    client.post("/governance/evals/run", headers=OMAR)
    card = client.get("/governance/models/lead_score", headers=OMAR).json()
    golden_free = [s for s in card["suites"] if s["kind"] == "golden" and s["tier"] == "free"]
    assert len(golden_free) == 2
    by_bar = {s["bar"]: [c["case_id"] for c in s["cases"]] for s in golden_free}
    auc = next(ids for bar, ids in by_bar.items() if "AUC" in bar)
    twins = next(ids for bar, ids in by_bar.items() if "twin" in bar)
    assert auc == ["holdout-auc"] and len(twins) == 8 and "holdout-auc" not in twins


def test_the_launcher_uses_the_metadata_token_and_the_run_api(monkeypatch):
    import io
    import json

    seen = []

    class Response(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def fake_urlopen(request, timeout=0):
        seen.append((request.full_url, dict(request.header_items())))
        if "metadata" in request.full_url:
            return Response(json.dumps({"access_token": "tok"}).encode())
        return Response(json.dumps({"name": "operations/exec-9"}).encode())

    monkeypatch.setattr(launcher.urllib.request, "urlopen", fake_urlopen)
    assert launcher.launch_job(JOB) == "operations/exec-9"
    assert seen[0][1].get("Metadata-flavor") == "Google"
    assert seen[1][0] == f"https://run.googleapis.com/v2/{JOB}:run" and seen[1][1]["Authorization"] == "Bearer tok"

    def down(request, timeout=0):
        raise OSError("no metadata server")

    monkeypatch.setattr(launcher.urllib.request, "urlopen", down)
    try:
        launcher.launch_job(JOB)
    except launcher.LaunchError as e:
        assert "no metadata server" in str(e)
    else:
        raise AssertionError("expected a LaunchError")
