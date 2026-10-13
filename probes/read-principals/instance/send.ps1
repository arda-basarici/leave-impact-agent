# Sends the instance probe to the app host over SSM under the administrator profile and
# saves what it printed. The payload is host.sh with probe.py spliced in as base64, so the
# host fetches nothing; the host script exports the five vendor parameters into the probe's
# container environment and never prints a value. PowerShell 5.1; `$dir` is a scratch
# directory outside the tree, since the stdout holds vendor hostnames and request ids.
param([Parameter(Mandatory = $true)][string]$dir)
$ErrorActionPreference = "Continue"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$profile_ = "leave-impact"
$region = "eu-central-1"
$probe = [Convert]::ToBase64String([IO.File]::ReadAllBytes("$here\probe.py"))
$script = ([IO.File]::ReadAllText("$here\host.sh")).Replace("<base64 of probe.py>", $probe)
$payload = @{ commands = @($script) } | ConvertTo-Json -Compress
[IO.File]::WriteAllText("$dir\payload.json", $payload, (New-Object Text.UTF8Encoding $false))
$instance = aws ec2 describe-instances --profile $profile_ --region $region --filters "Name=tag:Name,Values=leave-agent-app" "Name=instance-state-name,Values=running" --query "Reservations[].Instances[].InstanceId" --output text
Write-Output "instance $instance"
$cid = aws ssm send-command --profile $profile_ --region $region --instance-ids $instance --document-name AWS-RunShellScript --comment "read-principals instance probe" --parameters "file://$dir\payload.json" --query Command.CommandId --output text
Write-Output "command $cid sent at $(Get-Date -Format o)"
aws ssm wait command-executed --profile $profile_ --region $region --command-id $cid --instance-id $instance
aws ssm get-command-invocation --profile $profile_ --region $region --command-id $cid --instance-id $instance --query "[Status,ExecutionElapsedTime]" --output text
aws ssm get-command-invocation --profile $profile_ --region $region --command-id $cid --instance-id $instance --query StandardOutputContent --output text | Out-File -FilePath "$dir\probe.out.txt" -Encoding utf8
aws ssm get-command-invocation --profile $profile_ --region $region --command-id $cid --instance-id $instance --query StandardErrorContent --output text | Out-File -FilePath "$dir\probe.err.txt" -Encoding utf8
Get-Content "$dir\probe.out.txt"
Get-Content "$dir\probe.err.txt" -TotalCount 60
