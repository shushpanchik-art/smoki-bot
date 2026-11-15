"""Billing identifiers are validated before SQL interpolation."""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from google.cloud import bigquery

import config
from services import billing


@pytest.mark.parametrize("part", ["project", "dataset", "table"])
@pytest.mark.parametrize("unsafe", ["bad` UNION SELECT 1 --", "bad.name", "bad\nname"])
def test_rejects_unsafe_billing_identifier(monkeypatch, part, unsafe):
    project = unsafe if part == "project" else "my-project"
    dataset = unsafe if part == "dataset" else "billing_export"
    table = unsafe if part == "table" else "gcp_billing_export_v1_123"
    monkeypatch.setattr(config, "GOOGLE_CLOUD_PROJECT", project)
    monkeypatch.setattr(config, "BILLING_DATASET", dataset)
    monkeypatch.setattr(config, "BILLING_TABLE_PREFIX", "")
    client = Mock()
    client.list_tables.return_value = [SimpleNamespace(table_id=table)]
    monkeypatch.setattr(bigquery, "Client", Mock(return_value=client))
    assert billing._sync_fetch()["available"] is False
    client.query.assert_not_called()


def test_valid_billing_identifiers_keep_parameterized_date(monkeypatch):
    monkeypatch.setattr(config, "GOOGLE_CLOUD_PROJECT", "my-project")
    monkeypatch.setattr(config, "BILLING_DATASET", "billing_export")
    monkeypatch.setattr(config, "BILLING_TABLE_PREFIX", "gcp_")
    client = Mock()
    client.list_tables.return_value = [SimpleNamespace(table_id="gcp_export_v1_123")]
    client.query.return_value.result.return_value = []
    monkeypatch.setattr(bigquery, "Client", Mock(return_value=client))
    assert billing._sync_fetch()["available"] is True
    args, kwargs = client.query.call_args
    assert "FROM `my-project.billing_export.gcp_export_v1_123`" in args[0]
    assert "@month_start" in args[0]
    assert kwargs["job_config"].query_parameters[0].name == "month_start"
