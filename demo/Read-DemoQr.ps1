param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^(DEMO|MY-TEST|MY-DEMO|BROWSER)-[A-Za-z0-9_-]{1,40}$')]
    [string]$Reference,
    [switch]$Copy
)

$ErrorActionPreference = 'Stop'
$demoRoot = Split-Path -Parent $PSScriptRoot
$encodedReference = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($Reference))
$pythonSource = @"
import os, base64
from django_tenants.utils import schema_context
from api.models import Prescription
from api.case_commands import qr_token
if os.environ.get('CABINET_SIMULATION') != '1':
    raise RuntimeError('This helper is restricted to the synthetic demo.')
reference = base64.b64decode('$encodedReference').decode('utf-8')
with schema_context('simlab'):
    order = Prescription.objects.get(patient_ref=reference)
    print('QR_CONTENT:' + qr_token(order))
"@

Push-Location -LiteralPath $demoRoot
try {
    $qrOutput = & docker compose -p cabinet-virtual-lab -f compose.demo.yml exec -T backend python manage.py shell --verbosity 0 -c $pythonSource
    if ($LASTEXITCODE -ne 0) { throw 'Could not read the demo label. Check the running demo and the exact case reference.' }
    $qrLines = @($qrOutput | Where-Object { $_ -like 'QR_CONTENT:*' })
    if ($qrLines.Count -ne 1) { throw 'Expected exactly one signed demo label.' }
    $token = $qrLines[0].Substring('QR_CONTENT:'.Length)
    if ($Copy) { Set-Clipboard -Value $token }
    Write-Output $token
} finally {
    Pop-Location
}
