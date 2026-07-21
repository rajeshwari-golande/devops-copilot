"""Unit tests for log parsing."""

from app.services.log_parser import chunk_logs, extract_error_summary


def test_extract_error_summary_finds_error_lines():
    logs = "ok line\nERROR: something broke\ntrail\n"
    summary = extract_error_summary(logs)
    assert "ERROR" in summary


def test_chunk_logs_overlaps():
    text = "a" * 4000
    chunks = chunk_logs(text, chunk_size=1500, overlap=200)
    assert len(chunks) > 1
    assert chunks[0].startswith("a")
