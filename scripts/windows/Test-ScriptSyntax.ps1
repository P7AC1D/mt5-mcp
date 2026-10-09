#Requires -Version 5.1
# Read-only parser test. Can also run under PowerShell 7 on Linux without MT5.
[CmdletBinding()]
param()
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$failed = $false
Get-ChildItem -LiteralPath $PSScriptRoot -Filter '*.ps1' -File | ForEach-Object {
    $tokens = $null
    $errors = $null
    $null = [Management.Automation.Language.Parser]::ParseFile($_.FullName, [ref]$tokens, [ref]$errors)
    if (@($errors).Count -gt 0) {
        $failed = $true
        foreach ($parseError in $errors) {
            Write-Output "$($_.Name):$($parseError.Extent.StartLineNumber): $($parseError.Message)"
        }
    }
    else { Write-Output "PASS $($_.Name)" }
}
if ($failed) { exit 1 }
exit 0
