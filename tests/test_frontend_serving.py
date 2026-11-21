"""The React SPA is public, but build-adjacent files must never be served."""
import pytest
import stardew_agent.server as server


@pytest.fixture
def frontend(tmp_path, monkeypatch):
    root = tmp_path / 'dist'
    (root / 'assets').mkdir(parents=True)
    (root / 'index.html').write_text('<div id="root"></div>', encoding='utf-8')
    (root / 'assets/app.js').write_text('export {}', encoding='utf-8')
    (tmp_path / '.env').write_text('synthetic-secret', encoding='utf-8')
    monkeypatch.setattr(server, 'FRONTEND_DIST', root)
    return root


@pytest.mark.parametrize('path', ['/', '/chat', '/chat/a-task', '/graph', '/plans', '/knowledge'])
def test_spa_deep_links(frontend, path):
    assert server.frontend_file(path) == frontend / 'index.html'


@pytest.mark.parametrize('path', ['/../.env', '/%2e%2e/.env', '/..%5c.env', '/assets/missing.js', '/src/main.tsx', '/unknown'])
def test_build_boundary(frontend, path):
    assert server.frontend_file(path) is None


def test_actual_asset(frontend):
    assert server.frontend_file('/assets/app.js') == frontend / 'assets/app.js'
