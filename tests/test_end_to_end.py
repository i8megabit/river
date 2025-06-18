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
    # собираем и запускаем River через install-test.sh
    install_script = os.path.join(
        os.path.dirname(__file__), "..", "analyzer-platform", "install-test.sh"
    )
    subprocess.run(
        ["bash", install_script],
        check=False,
        cwd=os.path.dirname(install_script),
    )

    # ждём, пока поднимется backend
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
        pytest.fail("Не удалось дождаться запуска backend")

    # готовим простой отчёт, как будто его создал Glacier
    report_path = tmp_path / "dummy_report.html"
    report_path.write_text(
        """
        <html>
            <head>
                <meta name="analyzer-report-hash" content="abc123" />
                <meta name="analyzer-report-id" content="1" />
                <meta name="analyzer-hostname" content="localhost" />
                <meta name="analyzer-generated-at" content="2024-01-01T00:00:00Z" />
            </head>
            <body><h1>dummy</h1></body>
        </html>
        """
    )

    # отправляем отчёт
    with report_path.open("rb") as fh:
        upload_resp = requests.post(
            "http://localhost:18000/api/v1/reports/upload",
            files={"file": fh},
        )
    assert upload_resp.status_code == 200
    upload_data = upload_resp.json()
    report_id = upload_data.get("id")
    assert report_id

    # проверяем, что отчёт появился в списке
    list_resp = requests.get("http://localhost:18000/api/v1/reports")
    assert list_resp.status_code == 200
    reports = list_resp.json().get("reports", [])
    assert any(r.get("id") == report_id for r in reports)

    # скачиваем отчёт и смотрим содержимое
    dl_resp = requests.get(f"http://localhost:18000/api/v1/reports/{report_id}/download")
    assert dl_resp.status_code == 200
    assert "<html" in dl_resp.text.lower()

    # останавливаем контейнеры
    subprocess.run([
        "docker", "compose", "-f", "analyzer-platform/docker-compose.test.yml", "down", "--volumes", "--remove-orphans"
    ])
