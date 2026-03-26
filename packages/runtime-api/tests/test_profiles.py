"""Tests for the YAML-based profile loader."""

import tempfile
from pathlib import Path

import pytest

from runtime_api.profiles import load_profiles, get_profile, PROFILE_DEFAULTS


@pytest.fixture
def profiles_yaml(tmp_path):
    content = """
profiles:
  web-server:
    image: "nginx:alpine"
    resources:
      cpu_limit: "500m"
      memory_limit: "512Mi"
    idle_timeout: 0
    auto_remove: false
    ports:
      "80/tcp": {}
    max_per_user: 3

  worker:
    image: "python:3.12-slim"
    idle_timeout: 900
    auto_remove: true
"""
    path = tmp_path / "profiles.yaml"
    path.write_text(content)
    return str(path)


def test_load_profiles(profiles_yaml):
    profiles = load_profiles(profiles_yaml)
    assert "web-server" in profiles
    assert "worker" in profiles
    assert len(profiles) == 2


def test_profile_defaults_applied(profiles_yaml):
    profiles = load_profiles(profiles_yaml)
    worker = profiles["worker"]
    # Should have default values for fields not specified
    assert worker["gpu"] is False
    assert worker["node_selector"] == {}
    assert worker["mounts"] == []


def test_profile_resources_merged(profiles_yaml):
    profiles = load_profiles(profiles_yaml)
    web = profiles["web-server"]
    assert web["resources"]["cpu_limit"] == "500m"
    assert web["resources"]["memory_limit"] == "512Mi"
    # Defaults for unspecified resource fields
    assert web["resources"]["shm_size"] == 0


def test_profile_ports(profiles_yaml):
    profiles = load_profiles(profiles_yaml)
    web = profiles["web-server"]
    assert "80/tcp" in web["ports"]


def test_missing_file():
    profiles = load_profiles("/nonexistent/path.yaml")
    assert profiles == {}


def test_get_profile_returns_none_for_unknown(profiles_yaml):
    load_profiles(profiles_yaml)
    assert get_profile("nonexistent") is None
