from typer.testing import CliRunner

from issuebot.cli import app

runner = CliRunner()


def test_version():
    assert runner.invoke(app, ["version"]).exit_code == 0


def test_solve_without_key_exits_cleanly(seed_repo, monkeypatch):
    from issuebot import config

    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    config.get_settings.cache_clear()
    r = runner.invoke(app, ["solve", "--repo", str(seed_repo), "--issue", "bug"])
    config.get_settings.cache_clear()
    assert r.exit_code == 2
