from app.environment import load_environment, settings


def test_backend_fallback_root_priority_and_explicit_disable(tmp_path, monkeypatch):
    (tmp_path / 'backend').mkdir()
    (tmp_path / 'backend' / '.env').write_text(
        'PREPCREW_ENV_TEST_ONLY=backend\nPREPCREW_ENV_TEST_CONFLICT=backend\n'
        'PREPCREW_ENV_TEST_DISABLED=backend\n', encoding='utf-8')
    (tmp_path / '.env').write_text(
        'PREPCREW_ENV_TEST_CONFLICT=root\nPREPCREW_ENV_TEST_DISABLED=\n', encoding='utf-8')
    for key in ('ONLY', 'CONFLICT', 'DISABLED'):
        monkeypatch.delenv('PREPCREW_ENV_TEST_' + key, raising=False)
    monkeypatch.chdir(tmp_path / 'backend')
    result = settings(tmp_path)
    assert result['PREPCREW_ENV_TEST_ONLY'] == 'backend'
    assert result['PREPCREW_ENV_TEST_CONFLICT'] == 'root'
    assert result['PREPCREW_ENV_TEST_DISABLED'] == ''
    monkeypatch.setenv('PREPCREW_ENV_TEST_CONFLICT', 'process')
    monkeypatch.setenv('PREPCREW_ENV_TEST_ONLY', '')
    load_environment(tmp_path)
    assert settings(tmp_path)['PREPCREW_ENV_TEST_CONFLICT'] == 'process'
    assert settings(tmp_path)['PREPCREW_ENV_TEST_ONLY'] == ''


def test_missing_files_do_not_create_settings(tmp_path, monkeypatch):
    monkeypatch.delenv('PREPCREW_ENV_TEST_MISSING', raising=False)
    assert 'PREPCREW_ENV_TEST_MISSING' not in settings(tmp_path)
