"""Static checks on docker-compose.yml. Cheap, run in CI. The LIVE equivalent is scripts/verify-containment.sh."""
from pathlib import Path

import pytest
import yaml

COMPOSE = yaml.safe_load((Path(__file__).resolve().parents[1] / "docker-compose.yml").read_text())
SVC, NETS = COMPOSE["services"], COMPOSE["networks"]


def test_backend_network_is_internal():
    assert NETS["backend"].get("internal") is True


@pytest.mark.parametrize("name", ["qdrant", "ollama"])
def test_data_and_model_services_only_on_internal_network(name):
    assert SVC[name]["networks"] == ["backend"]


@pytest.mark.parametrize("name", ["qdrant", "ollama"])
def test_data_and_model_services_publish_no_ports(name):
    assert "ports" not in SVC[name]


def test_only_app_bridges_networks():
    bridging = [n for n, s in SVC.items() if len(s.get("networks", [])) > 1]
    assert bridging == ["app"]


def test_published_ports_bind_loopback_only():
    for s in SVC.values():
        for p in s.get("ports", []):
            assert str(p).startswith("127.0.0.1:"), p


def test_only_the_setup_job_touches_the_egress_network():
    users = [n for n, s in SVC.items() if "egress" in s.get("networks", [])]
    assert users == ["pull"] and SVC["pull"]["profiles"] == ["setup"]


def test_qdrant_requires_api_key_and_has_no_telemetry():
    env = SVC["qdrant"]["environment"]
    assert "QDRANT__SERVICE__API_KEY" in env and env["QDRANT__SERVICE__API_KEY"].startswith("${QDRANT_API_KEY:?")
    assert env["QDRANT__TELEMETRY_DISABLED"] == "true"


def test_secrets_are_mandatory_not_defaulted():
    assert SVC["app"]["environment"]["JWT_SECRET"].startswith("${JWT_SECRET:?")


def test_app_container_is_hardened():
    app = SVC["app"]
    assert app["read_only"] is True
    assert app["cap_drop"] == ["ALL"]
    assert "no-new-privileges:true" in app["security_opt"]
    assert all(v.endswith(":ro") for v in app["volumes"] if v.startswith("./"))  # host mounts read-only
