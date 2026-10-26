# Runs the publication-digests check on the app host over SSM under the administrator
# profile and prints what the host printed: one line per published replay and the count
# that reproduce (`python -m leaveimpact.app verify-publications`, the demo milestone's
# live-path step). The host line is the deploy's own compose invocation from the app
# directory, so the command reads the instance's stores under the deployed image's code.
# The output names public ids, run ids, formats and counts, never a digest's value.
# PowerShell 5.1; the CLI's Python reads the invocation in UTF-8 (the SSM gotcha of
# 2026-10-23). Usage, after `aws sso login --profile leave-impact`:
#     powershell -File scripts\verify_publications.ps1
$ErrorActionPreference = "Continue"
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
$profile_ = "leave-impact"
$region = "eu-central-1"
$script = "cd /srv/app && docker compose run --rm app python -m leaveimpact.app verify-publications"
$payload = @{ commands = @($script); executionTimeout = @("900") } | ConvertTo-Json -Compress
$payloadPath = Join-Path $env:TEMP "verify-publications.payload.json"
[IO.File]::WriteAllText($payloadPath, $payload, (New-Object Text.UTF8Encoding $false))
$instance = aws ec2 describe-instances --profile $profile_ --region $region --filters "Name=tag:Name,Values=leave-agent-app" "Name=instance-state-name,Values=running" --query "Reservations[].Instances[].InstanceId" --output text
Write-Output "instance $instance"
$cid = aws ssm send-command --profile $profile_ --region $region --instance-ids $instance --document-name AWS-RunShellScript --comment "verify-publications" --parameters "file://$payloadPath" --query Command.CommandId --output text
Write-Output "command $cid sent at $(Get-Date -Format o)"
$status = "Pending"
$deadline = (Get-Date).AddMinutes(16)
while (($status -eq "Pending") -or ($status -eq "InProgress") -or ($status -eq "Delayed")) {
    if ((Get-Date) -gt $deadline) { Write-Output "no terminal status by the deadline; the command may still run"; break }
    Start-Sleep -Seconds 10
    $status = aws ssm get-command-invocation --profile $profile_ --region $region --command-id $cid --instance-id $instance --query Status --output text
    Write-Output "$(Get-Date -Format T) $status"
}
aws ssm get-command-invocation --profile $profile_ --region $region --command-id $cid --instance-id $instance --query "[Status,ExecutionElapsedTime]" --output text
Write-Output "----- stdout -----"
aws ssm get-command-invocation --profile $profile_ --region $region --command-id $cid --instance-id $instance --query StandardOutputContent --output text
Write-Output "----- stderr -----"
aws ssm get-command-invocation --profile $profile_ --region $region --command-id $cid --instance-id $instance --query StandardErrorContent --output text
