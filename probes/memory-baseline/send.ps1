# Sends the memory baseline's host script to the app host over SSM under the
# administrator profile, polls to the end (the eight levels take about nine minutes,
# past what `aws ssm wait` allows), and saves what the host printed under $dir. The
# payload is host.sh with loader.py and sampler.py spliced in as base64, written to the
# temp directory; the outputs hold memory figures, container names and the deployed sha,
# nothing secret, so $dir is the capture directory in the tree. PowerShell 5.1. The
# CLI's Python reads the invocation in UTF-8 (the SSM gotcha of 2026-10-23).
param([Parameter(Mandatory = $true)][string]$dir)
$ErrorActionPreference = "Continue"
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$profile_ = "leave-impact"
$region = "eu-central-1"
New-Item -ItemType Directory -Force $dir | Out-Null
$loader = [Convert]::ToBase64String([IO.File]::ReadAllBytes("$here\loader.py"))
$sampler = [Convert]::ToBase64String([IO.File]::ReadAllBytes("$here\sampler.py"))
$script = ([IO.File]::ReadAllText("$here\host.sh")).Replace("<base64 of loader.py>", $loader).Replace("<base64 of sampler.py>", $sampler)
$payload = @{ commands = @($script); executionTimeout = @("1800") } | ConvertTo-Json -Compress
$payloadPath = Join-Path $env:TEMP "memory-baseline.payload.json"
[IO.File]::WriteAllText($payloadPath, $payload, (New-Object Text.UTF8Encoding $false))
$instance = aws ec2 describe-instances --profile $profile_ --region $region --filters "Name=tag:Name,Values=leave-agent-app" "Name=instance-state-name,Values=running" --query "Reservations[].Instances[].InstanceId" --output text
Write-Output "instance $instance"
$cid = aws ssm send-command --profile $profile_ --region $region --instance-ids $instance --document-name AWS-RunShellScript --comment "memory-baseline probe" --parameters "file://$payloadPath" --query Command.CommandId --output text
Write-Output "command $cid sent at $(Get-Date -Format o); the levels take about nine minutes"
$status = "Pending"
$deadline = (Get-Date).AddMinutes(32)
while (($status -eq "Pending") -or ($status -eq "InProgress") -or ($status -eq "Delayed")) {
    if ((Get-Date) -gt $deadline) { Write-Output "no terminal status by the deadline; the command may still run"; break }
    Start-Sleep -Seconds 20
    $status = aws ssm get-command-invocation --profile $profile_ --region $region --command-id $cid --instance-id $instance --query Status --output text
    Write-Output "$(Get-Date -Format T) $status"
}
aws ssm get-command-invocation --profile $profile_ --region $region --command-id $cid --instance-id $instance --query "[Status,ExecutionElapsedTime]" --output text
aws ssm get-command-invocation --profile $profile_ --region $region --command-id $cid --instance-id $instance --query StandardOutputContent --output text | Out-File -FilePath "$dir\host.out.txt" -Encoding utf8
aws ssm get-command-invocation --profile $profile_ --region $region --command-id $cid --instance-id $instance --query StandardErrorContent --output text | Out-File -FilePath "$dir\host.err.txt" -Encoding utf8
$length = (Get-Content "$dir\host.out.txt" -Raw).Length
Write-Output "stdout $length characters saved (SSM truncates at 24,000; the host's work directory on the first line holds the files)"
Get-Content "$dir\host.out.txt" -TotalCount 30
Get-Content "$dir\host.err.txt" -TotalCount 20
