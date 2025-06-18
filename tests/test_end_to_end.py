import os
import subprocess
import time

import requests
import shutil
import pytest


def has_docker():
    return shutil.which("docker") is not None


@pytest.mark.skipif(not has_docker(), reason="Docker is not available")
def test_run_river_and_upload_report(tmp_path):
    # Build and run River using existing install script
    install_script = os.path.join(os.path.dirname(__file__), "..", "analyzer-platform", "install-test.sh")
    subprocess.run(
        ["bash", install_script],
        check=True,
        cwd=os.path.dirname(install_script),
    )

    # Wait for backend health
    timeout = int(os.environ.get("RIVER_TEST_TIMEOUT", "30"))
    for _ in range(timeout):
        try:
            resp = requests.get("http://localhost:18000/health", timeout=5)
            if resp.status_code == 200 and "healthy" in resp.text.lower():
                break
        except Exception:
            pass
        time.sleep(2)
    else:
        pytest.fail("Backend health check failed")

    # Generate a dummy report as Glacier would produce
    report_path = tmp_path / "dummy_report.html"
    report_path.write_text("<html><body><h1>dummy</h1></body></html>")

    # Upload the report
    with report_path.open("rb") as fh:
        upload_resp = requests.post(
            "http://localhost:18000/api/v1/reports/upload",
            files={"file": fh},
        )
    assert upload_resp.status_code == 200
    upload_data = upload_resp.json()
    report_id = upload_data.get("id")
    assert report_id

    # Verify report exists
    list_resp = requests.get("http://localhost:18000/api/v1/reports")
    assert list_resp.status_code == 200
    reports = list_resp.json().get("reports", [])
    assert any(r.get("id") == report_id for r in reports)

    # Download and inspect report content
    dl_resp = requests.get(f"http://localhost:18000/api/v1/reports/{report_id}/download")
    assert dl_resp.status_code == 200
    assert "<html" in dl_resp.text.lower()
