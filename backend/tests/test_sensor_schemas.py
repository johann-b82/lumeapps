"""Unit tests for v1.15 sensor Pydantic schemas — SecretStr + no-echo contract.

Locks the contract for PITFALLS C-3 (never echo community) and N-7 (no "public"
default — admin must explicitly type the community).
"""
import pytest
from pydantic import SecretStr, ValidationError

from app.schemas import SensorCreate, SensorRead


def test_sensor_create_community_is_secret():
    c = SensorCreate(
        name="t", host="h", community=SecretStr("mysecret"),
        temperature_oid=None, humidity_oid=None,
    )
    # str(model) and JSON serialization redact
    assert "mysecret" not in str(c)
    assert "mysecret" not in c.model_dump_json()
    # But the secret is retrievable server-side via get_secret_value()
    assert c.community.get_secret_value() == "mysecret"


def test_sensor_read_omits_community():
    # PITFALLS C-3: SensorRead MUST NOT contain a community field. Response shape
    # is admin-facing config read; community is write-only.
    assert "community" not in SensorRead.model_fields


def test_sensor_create_rejects_empty_community():
    # PITFALLS N-7: no default, min_length=1 — admin must type it.
    with pytest.raises(ValidationError):
        SensorCreate(name="t", host="h", community=SecretStr(""))


def test_sensor_create_no_public_default():
    field = SensorCreate.model_fields["community"]
    assert field.is_required(), (
        "community must be required with no default — 'public' default is a "
        "disclosure bug (PITFALLS N-7)."
    )
