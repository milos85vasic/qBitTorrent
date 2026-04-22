from pathlib import Path

import pytest
import yaml

COMPOSE_PATH = Path(__file__).resolve().parent.parent.parent / "docker-compose.quality.yml"


@pytest.fixture
def quality_compose():
    with open(COMPOSE_PATH) as f:
        return yaml.safe_load(f)


def test_file_exists():
    assert COMPOSE_PATH.is_file(), f"{COMPOSE_PATH} not found"


def test_parseable_as_yaml(quality_compose):
    assert isinstance(quality_compose, dict)
    assert "services" in quality_compose


def test_sonarqube_service_exists(quality_compose):
    services = quality_compose["services"]
    assert "sonarqube" in services


def test_sonarqube_has_healthcheck(quality_compose):
    sq = quality_compose["services"]["sonarqube"]
    assert "healthcheck" in sq
    hc = sq["healthcheck"]
    assert "test" in hc
    assert any("9000" in str(part) for part in hc["test"])


def test_sonarqube_depends_on_sonar_db(quality_compose):
    sq = quality_compose["services"]["sonarqube"]
    deps = sq.get("depends_on", {})
    assert "sonar-db" in deps
    assert deps["sonar-db"].get("condition") == "service_healthy"


def test_sonarqube_jdbc_config(quality_compose):
    sq = quality_compose["services"]["sonarqube"]
    env = sq.get("environment", {})
    jdbc_url = env.get("SONAR_JDBC_URL", "")
    assert "sonar-db" in jdbc_url
    assert "5432" in jdbc_url
    assert "sonar" in jdbc_url


def test_sonar_db_service_exists(quality_compose):
    services = quality_compose["services"]
    assert "sonar-db" in services


def test_sonar_db_has_healthcheck(quality_compose):
    db = quality_compose["services"]["sonar-db"]
    assert "healthcheck" in db
    hc = db["healthcheck"]
    assert "test" in hc
    assert any("pg_isready" in str(part) for part in hc["test"])


def test_sonar_db_postgres_credentials(quality_compose):
    db = quality_compose["services"]["sonar-db"]
    env = db.get("environment", {})
    assert env.get("POSTGRES_DB") == "sonar"
    assert "sonar" in str(env.get("POSTGRES_USER", ""))


def test_scanner_services_exist(quality_compose):
    services = quality_compose["services"]
    required = ["snyk", "semgrep", "trivy", "gitleaks"]
    for name in required:
        assert name in services, f"scanner service '{name}' missing"


def test_at_least_four_scanner_services(quality_compose):
    scanner_names = {"snyk", "semgrep", "trivy", "gitleaks"}
    services = quality_compose["services"]
    found = scanner_names & set(services.keys())
    assert len(found) >= 4


def test_scanners_mount_project_readonly(quality_compose):
    services = quality_compose["services"]
    scanners = ["snyk", "semgrep", "trivy", "gitleaks"]
    for name in scanners:
        vols = services[name].get("volumes", [])
        ro_mounts = [v for v in vols if ":ro" in str(v)]
        assert len(ro_mounts) >= 1, f"{name} missing read-only project mount"


def test_scanners_mount_artifacts(quality_compose):
    services = quality_compose["services"]
    scanners = ["snyk", "semgrep", "trivy", "gitleaks"]
    for name in scanners:
        vols = services[name].get("volumes", [])
        artifact_mounts = [v for v in vols if "artifacts" in str(v)]
        assert len(artifact_mounts) >= 1, f"{name} missing artifacts mount"


def test_sonarqube_port_9000(quality_compose):
    sq = quality_compose["services"]["sonarqube"]
    ports = sq.get("ports", [])
    assert any("9000" in str(p) for p in ports)


def test_volumes_defined(quality_compose):
    volumes = quality_compose.get("volumes", {})
    assert "sonarqube_data" in volumes or any("sonarqube_data" in str(k) for k in volumes)
    assert "sonar_db_data" in volumes or any("sonar_db_data" in str(k) for k in volumes)
