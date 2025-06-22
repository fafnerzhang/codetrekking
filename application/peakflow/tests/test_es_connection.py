#!/usr/bin/env python3
"""
Test Elasticsearch Connection
"""
from elasticsearch import Elasticsearch
import pytest


def test_elasticsearch_connection():
    """Test Elasticsearch connection using pytest asserts"""
    es_config = {
        'hosts': ['http://localhost:9200'],
        'basic_auth': ('elastic', 'password'),
        'verify_certs': False,
        'request_timeout': 30
    }
    try:
        es = Elasticsearch(**es_config)
        assert es.ping(), "Elasticsearch ping failed. Is the service running?"
        info = es.info()
        assert 'cluster_name' in info
        assert 'version' in info
    except Exception as e:
        pytest.fail(f"Elasticsearch connection test failed: {e}")
