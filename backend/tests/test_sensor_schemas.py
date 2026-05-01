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


def test_sensor_create_accepts_empty_community():
    # v1.27: community is now optional. Some SNMP devices accept
    # unauthenticated reads; empty string passes through to pysnmp.
    sensor = SensorCreate(name="t", host="h", community=SecretStr(""))
    assert sensor.community.get_secret_value() == ""


def test_sensor_create_no_public_default():
    # v1.27: still no "public" default — empty SecretStr is the only fallback.
    # PITFALLS N-7's disclosure-risk concern applied to "public" specifically;
    # an empty community sends no useful auth secret over the wire.
    field = SensorCreate.model_fields["community"]
    default = field.default
    assert default is not None and default.get_secret_value() == "", (
        "community default must remain SecretStr('') — never 'public' (PITFALLS N-7)."
    )
