import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scripts import run_for_users


@pytest.mark.unit
def test_orchestrator_empty_payload(capsys):
    with patch.dict(os.environ, {"USERS_PAYLOAD": "[]"}):
        run_for_users.main()
        captured = capsys.readouterr()
        assert "No users in payload" in captured.out


@pytest.mark.unit
def test_orchestrator_invalid_json(capsys):
    with patch.dict(os.environ, {"USERS_PAYLOAD": "invalid-json"}):
        run_for_users.main()
        captured = capsys.readouterr()
        assert "Failed to decode USERS_PAYLOAD" in captured.out


@pytest.mark.unit
@patch("scripts.run_for_users.download_resume")
@patch("scripts.run_for_users.subprocess.run")
@patch("scripts.run_for_users.update_user_sheet_metrics")
@patch("scripts.run_for_users.send_admin_summary")
def test_orchestrator_success_flow(
    mock_send_summary, mock_update_metrics, mock_sub_run, mock_download
):
    mock_sub_run.return_value.returncode = 0
    mock_payload = json.dumps([
        {
            "slug": "john_doe",
            "name": "John Doe",
            "email": "john@example.com",
            "job_title": "QA Engineer",
            "location": "Remote",
            "gdrive_file_id": "file123"
        }
    ])
    
    expected_resume_path = str(Path("workspace_tmp") / "john_doe_resume.pdf")
    
    with patch.dict(
        os.environ,
        {
            "USERS_PAYLOAD": mock_payload,
            "GDRIVE_SA_KEY_PATH": "dummy_key.json",
            "GOOGLE_SHEET_ID": "dummy_sheet_id",
            "ADMIN_EMAIL": "admin@example.com",
            "USER_SLEEP_SECONDS": "0"
        }
    ):
        run_for_users.main()
        
        mock_download.assert_called_once_with("file123", expected_resume_path, "dummy_key.json")
        mock_sub_run.assert_called_once()
        mock_update_metrics.assert_called_once_with("john@example.com", "dummy_sheet_id", "dummy_key.json")
        mock_send_summary.assert_called_once_with(
            [{"user": "John Doe", "status": "success", "email": "john@example.com"}],
            "admin@example.com"
        )
