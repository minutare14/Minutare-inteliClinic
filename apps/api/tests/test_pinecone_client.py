"""Tests for PineconeClient."""
from __future__ import annotations


def test_pinecone_client_import():
    from app.core.pinecone_client import PineconeClient

    assert PineconeClient is not None


def test_pinecone_is_available_false_without_key(monkeypatch):
    """Without PINECONE_API_KEY set, is_available should be False."""
    # Ensure the env var is not set
    monkeypatch.delenv("PINECONE_API_KEY", raising=False)
    from app.core.pinecone_client import PineconeClient

    client = PineconeClient()
    assert client.is_available() is False


def test_pinecone_is_available_false_with_empty_key(monkeypatch):
    """With PINECONE_API_KEY set to empty string, is_available should be False."""
    monkeypatch.setenv("PINECONE_API_KEY", "")
    from app.core.pinecone_client import PineconeClient

    client = PineconeClient()
    assert client.is_available() is False


def test_pinecone_index_name_comes_from_settings():
    """index_name property returns settings.pinecone_index."""
    from app.core.config import settings

    from app.core.pinecone_client import PineconeClient

    client = PineconeClient()
    assert client.index_name == settings.pinecone_index


def test_pinecone_namespace_uses_clinic_id():
    """namespace property returns settings.clinic_id."""
    from app.core.config import settings

    from app.core.pinecone_client import PineconeClient

    client = PineconeClient()
    assert client.namespace == settings.clinic_id