"""Start the atrium-evals Cloud Run job with the service's own identity (the metadata server), never local
credentials."""
import json
import urllib.request

METADATA_TOKEN = "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token"


class LaunchError(RuntimeError):
    pass


def _token() -> str:
    request = urllib.request.Request(METADATA_TOKEN, headers={"Metadata-Flavor": "Google"})
    with urllib.request.urlopen(request, timeout=5) as response:
        return json.load(response)["access_token"]


def launch_job(job_name: str) -> str:
    """Run the job (projects/<p>/locations/<r>/jobs/<name>) and return the execution it started (the operation's
    metadata names it; the operation's own name when it does not), so the run can be tied to that execution."""
    try:
        request = urllib.request.Request(f"https://run.googleapis.com/v2/{job_name}:run", data=b"{}", method="POST",
                                         headers={"Authorization": f"Bearer {_token()}",
                                                  "Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=15) as response:
            operation = json.load(response)
        return (operation.get("metadata") or {}).get("name") or operation.get("name", "")
    except Exception as e:
        raise LaunchError(str(e)) from e
