from __future__ import annotations

import importlib

import pytest
import httpx


def _reload_cli(monkeypatch, provider: str | None, token: str | None):
    if provider is None:
        monkeypatch.delenv("ACTIVE_MATCH_PROVIDER", raising=False)
    else:
        monkeypatch.setenv("ACTIVE_MATCH_PROVIDER", provider)
    if token is None:
        monkeypatch.delenv("SPORTMONKS_API_TOKEN", raising=False)
    else:
        monkeypatch.setenv("SPORTMONKS_API_TOKEN", token)

    import app.core.settings as settings_module
    importlib.reload(settings_module)

    import app.cli.matchvote as cli_module
    return importlib.reload(cli_module)


def test_shadow_exits_when_provider_not_sportmonks(monkeypatch, capsys):
    cli = _reload_cli(monkeypatch, provider="openligadb", token=None)
    result = cli._run_shadow_inplay(cli.argparse.Namespace(limit=5))
    out = capsys.readouterr().out
    assert result == 0
    assert "provider != sportmonks" in out


def test_shadow_fails_fast_without_token_when_provider_sportmonks(monkeypatch):
    cli = _reload_cli(monkeypatch, provider="sportmonks", token=None)
    with pytest.raises(RuntimeError):
        cli._run_shadow_inplay(cli.argparse.Namespace(limit=5))


def test_shadow_handles_connect_timeout(monkeypatch, capsys):
    cli = _reload_cli(monkeypatch, provider="sportmonks", token="token")
    def _raise(*args, **kwargs):
        raise httpx.ConnectTimeout("handshake")
    monkeypatch.setattr(cli, "fetch_inplay_readonly", _raise)
    result = cli._run_shadow_inplay(cli.argparse.Namespace(limit=5))
    out = capsys.readouterr().out
    assert result == 0
    assert "sportmonks fetch failed: ConnectTimeout" in out


def test_shadow_logs_no_live_matches_and_status(monkeypatch, capsys):
    cli = _reload_cli(monkeypatch, provider="sportmonks", token="token")
    def _ok(*args, **kwargs):
        return ({}, 503, 12)
    monkeypatch.setattr(cli, "fetch_inplay_readonly", _ok)
    result = cli._run_shadow_inplay(cli.argparse.Namespace(limit=5))
    out = capsys.readouterr().out
    assert result == 0
    assert "inplay: status=503" in out
    assert "no live matches right now" in out
    assert "reason=http_error" in out
