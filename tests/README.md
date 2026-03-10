# Tests

## Documentation Navigation

- [Repository README](../README.md)
- [Documentation index](../docs/README.md)
- [Testing docs index](../docs/testing/README.md)
- [Runbooks index](../docs/runbooks/README.md)
- [API README](../apps/api/README.md)

## Coherence Integration Tests

These tests validate coherence rule logic directly and should run without the full API app.

PowerShell:

```powershell
$env:PYTHONPATH='apps/api'
$env:DATABASE_URL='sqlite+aiosqlite:///./test.db'
$env:SUPABASE_URL='http://localhost'
$env:SUPABASE_ANON_KEY='test'
$env:SUPABASE_SERVICE_ROLE_KEY='test'
$env:JWT_SECRET_KEY='testsecretkeytestsecretkeytestsecretkey'
pytest tests/integration/coherence/test_engine_logic.py --confcutdir=tests/integration/coherence
```
