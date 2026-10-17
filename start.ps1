$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) { python -m venv .venv }
& '.\.venv\Scripts\python.exe' -m pip install -r backend/requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Python bağımlılıkları kurulamadı.' }
if (-not (Test-Path -LiteralPath 'node_modules')) {
    npm.cmd ci
    if ($LASTEXITCODE -ne 0) { throw 'Node bağımlılıkları kurulamadı.' }
}
npm.cmd run build
if ($LASTEXITCODE -ne 0) { throw 'React derlemesi başarısız.' }
Write-Host 'Site: http://127.0.0.1:8000'
Write-Host 'Panel: http://127.0.0.1:8000/admin'
Write-Host 'İlk giriş bilgileri: .local/admin.txt'
& '.\.venv\Scripts\python.exe' backend/app.py
