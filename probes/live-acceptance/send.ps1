# Drives the live path's acceptance sampler on the app host over SSM under the
# administrator profile, one action a call: `check` runs the worker's Access check and
# saves its lines under $dir, starting nothing; `start` leaves the detached sampling loop
# running at -cadence seconds and saves the host's header with the work directory under $dir; `stop` ends the
# loop and saves its account; `fetch` pulls samples.jsonl slice by slice as base64 (SSM cuts
# a command's stdout at 24,000 characters) and writes the bytes reassembled to
# $dir\<name>-samples.jsonl with no byte-order mark, so the reducer reads what the host
# wrote. The payload is host.sh with the action, the work directory, the offset, the
# cadence, the memory baseline's sampler and the Access check spliced in. PowerShell 5.1; the CLI's Python reads the
# invocation in UTF-8 (the SSM gotcha of 2026-10-23). The tick-cost sender is the precedent.
#
#   .\send.ps1 -action check -dir <capture dir>
#   .\send.ps1 -action start -dir <capture dir> [-cadence 2]          (prints "work /tmp/...")
#   .\send.ps1 -action stop  -dir <capture dir> -work /tmp/live-acceptance.XXXXXX
#   .\send.ps1 -action fetch -dir <capture dir> -work /tmp/live-acceptance.XXXXXX -name runs
param(
    [Parameter(Mandatory = $true)][ValidateSet("check", "start", "stop", "fetch")][string]$action,
    [Parameter(Mandatory = $true)][string]$dir,
    [string]$work = "",
    [string]$name = "samples",
    [ValidateRange(1, 60)][int]$cadence = 5
)
$ErrorActionPreference = "Continue"
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$profile_ = "leave-impact"
$region = "eu-central-1"
if (($action -in @("stop", "fetch")) -and ($work -eq "")) { throw "-work is the directory the start action printed" }
New-Item -ItemType Directory -Force $dir | Out-Null
$sampler = [Convert]::ToBase64String([IO.File]::ReadAllBytes("$here\..\memory-baseline\sampler.py"))
$accessCheck = [Convert]::ToBase64String([IO.File]::ReadAllBytes("$here\access_check.py"))
$template = [IO.File]::ReadAllText("$here\host.sh")
$instance = aws ec2 describe-instances --profile $profile_ --region $region --filters "Name=tag:Name,Values=leave-agent-app" "Name=instance-state-name,Values=running" --query "Reservations[].Instances[].InstanceId" --output text
Write-Output "instance $instance"

function Send-HostScript([string]$script, [string]$comment, [int]$timeoutSeconds) {
    $payload = @{ commands = @($script); executionTimeout = @("$timeoutSeconds") } | ConvertTo-Json -Compress
    $payloadPath = Join-Path $env:TEMP "live-acceptance.payload.json"
    [IO.File]::WriteAllText($payloadPath, $payload, (New-Object Text.UTF8Encoding $false))
    $cid = aws ssm send-command --profile $profile_ --region $region --instance-ids $instance --document-name AWS-RunShellScript --comment $comment --parameters "file://$payloadPath" --query Command.CommandId --output text
    $status = "Pending"
    $deadline = (Get-Date).AddSeconds($timeoutSeconds + 60)
    while (($status -eq "Pending") -or ($status -eq "InProgress") -or ($status -eq "Delayed")) {
        if ((Get-Date) -gt $deadline) { Write-Output "no terminal status by the deadline"; break }
        Start-Sleep -Seconds 4
        $status = aws ssm get-command-invocation --profile $profile_ --region $region --command-id $cid --instance-id $instance --query Status --output text
    }
    $err = aws ssm get-command-invocation --profile $profile_ --region $region --command-id $cid --instance-id $instance --query StandardErrorContent --output text
    if ($err -and ($err.Trim() -ne "") -and ($err.Trim() -ne "None")) { Write-Output "stderr: $($err.Trim())" }
    return (aws ssm get-command-invocation --profile $profile_ --region $region --command-id $cid --instance-id $instance --query StandardOutputContent --output text)
}

function Render([string]$offset) {
    return $template.Replace("<action>", $action).Replace("<work>", $work).Replace("<offset>", $offset).Replace("<cadence>", "$cadence").Replace("<base64 of sampler.py>", $sampler).Replace("<base64 of access_check.py>", $accessCheck)
}

switch ($action) {
    "check" {
        $out = Send-HostScript (Render "0") "live-acceptance access check" 120
        [IO.File]::WriteAllText("$dir\$name-check.out.txt", $out, (New-Object Text.UTF8Encoding $false))
        Write-Output $out
    }
    "start" {
        $out = Send-HostScript (Render "0") "live-acceptance sampler start" 120
        [IO.File]::WriteAllText("$dir\$name-start.out.txt", $out, (New-Object Text.UTF8Encoding $false))
        Write-Output $out
    }
    "stop" {
        $out = Send-HostScript (Render "0") "live-acceptance sampler stop" 120
        [IO.File]::WriteAllText("$dir\$name-stop.out.txt", $out, (New-Object Text.UTF8Encoding $false))
        Write-Output $out
    }
    "fetch" {
        $stream = New-Object IO.MemoryStream
        $offset = 0
        $total = -1
        do {
            $out = Send-HostScript (Render "$offset") "live-acceptance sampler fetch $offset" 120
            $slice = $null
            foreach ($line in ($out -split "`n")) {
                $trimmed = $line.Trim()
                if ($trimmed.StartsWith("bytes ")) { $total = [int]$trimmed.Substring(6) }
                if ($trimmed.StartsWith("slice ")) { $slice = $trimmed.Substring(6) }
            }
            if ($null -eq $slice) { throw "no slice line in the host's output: $out" }
            $bytes = [Convert]::FromBase64String($slice)
            $stream.Write($bytes, 0, $bytes.Length)
            $offset += $bytes.Length
            Write-Output "fetched $offset of $total bytes"
        } while (($offset -lt $total) -and ($bytes.Length -gt 0))
        $path = "$dir\$name-samples.jsonl"
        [IO.File]::WriteAllBytes($path, $stream.ToArray())
        $lines = ([IO.File]::ReadAllText($path) -split "`n" | Where-Object { $_.Trim() -ne "" }).Count
        Write-Output "written $path, $lines samples, $($stream.Length) bytes"
    }
}
