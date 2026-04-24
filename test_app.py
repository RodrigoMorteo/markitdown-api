import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from app import app

client = TestClient(app)

def test_unsupported_extension():
    """Test that submitting a file with an unsupported extension returns a 400 Bad Request."""
    response = client.post(
        "/convert",
        files={"file": ("test.exe", b"dummy content", "application/octet-stream")}
    )
    assert response.status_code == 400
    assert "Unsupported file extension" in response.json()["detail"]

def test_missing_filename():
    """Test that a file uploaded without a valid filename defaults to an unnamed upload and fails extension checks."""
    response = client.post(
        "/convert",
        # Passing None as the filename to simulate missing filename metadata
        files={"file": (None, b"dummy content", "application/octet-stream")}
    )
    assert response.status_code == 422
    assert "Expected UploadFile" in response.json()["detail"]

@patch("app.md.convert")
def test_successful_conversion(mock_convert):
    """Test the happy path where a supported file is correctly passed to MarkItDown and parsed."""
    mock_result = MagicMock()
    mock_result.text_content = "# Success"
    mock_convert.return_value = mock_result

    response = client.post(
        "/convert",
        files={"file": ("test.pdf", b"dummy pdf content", "application/pdf")}
    )
    assert response.status_code == 200
    assert response.json() == {"text": "# Success"}
    mock_convert.assert_called_once()

@patch("app.md.convert")
def test_file_size_exceeded(mock_convert):
    """Test that passing a payload exceeding the clamped size limit returns a 413 Payload Too Large."""
    # Passing a max_size_mb of 0 so that any chunk size > 0 triggers the limit
    response = client.post(
        "/convert?max_size_mb=0",
        files={"file": ("test.pdf", b"dummy content", "application/pdf")}
    )
    assert response.status_code == 413
    assert "exceeds requested/clamped limit" in response.json()["detail"]
    mock_convert.assert_not_called()

@patch("app.md.convert")
def test_empty_content_error(mock_convert):
    """Test that the API returns a 500 error if the converter successfully runs but returns empty content."""
    mock_result = MagicMock()
    mock_result.text_content = ""  # Emulates a silent failure or empty parsed content
    mock_convert.return_value = mock_result

    response = client.post(
        "/convert",
        files={"file": ("test.pdf", b"dummy content", "application/pdf")}
    )
    assert response.status_code == 500
    assert "Document parsing failed" in response.json()["detail"]

@patch("app.md.convert")
def test_conversion_exception(mock_convert):
    """Test that the API handles underlying parser exceptions gracefully and returns a 500 error."""
    mock_convert.side_effect = Exception("Underlying parsing error")

    response = client.post(
        "/convert",
        files={"file": ("test.pdf", b"dummy content", "application/pdf")}
    )
    assert response.status_code == 500
    assert "Document parsing failed" in response.json()["detail"]