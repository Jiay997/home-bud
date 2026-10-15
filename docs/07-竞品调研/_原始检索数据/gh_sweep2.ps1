$ErrorActionPreference = "Continue"
$H = @{ "User-Agent" = "dsh-research"; "Accept" = "application/vnd.github+json" }
$out = "D:\HomeBud\_research\sweep2_results.txt"
"SEARCH PASS 2" | Out-File -FilePath $out -Encoding UTF8

$queries = Get-Content "D:\HomeBud\_research\queries2.txt" -Encoding UTF8
$seen = @{}
foreach ($q in $queries) {
  $enc = [uri]::EscapeDataString($q)
  $url = "https://api.github.com/search/repositories?q=$enc&sort=stars&order=desc&per_page=25"
  $r = $null
  for ($try = 1; $try -le 3; $try++) {
    try { $r = Invoke-RestMethod -Uri $url -Headers $H -TimeoutSec 40; break }
    catch { Start-Sleep -Seconds 45 }
  }
  if ($r -eq $null) { "=== QUERY: $q | FAILED ===" | Out-File -FilePath $out -Encoding UTF8 -Append; continue }
  "=== QUERY: $q | total=$($r.total_count) ===" | Out-File -FilePath $out -Encoding UTF8 -Append
  foreach ($it in $r.items) {
    if ($seen.ContainsKey($it.full_name)) { continue }
    $seen[$it.full_name] = 1
    $lic = if ($it.license) { $it.license.spdx_id } else { "NONE" }
    $desc = if ($it.description) { $it.description -replace "\s+", " " } else { "" }
    if ($desc.Length -gt 260) { $desc = $desc.Substring(0, 260) }
    "$($it.full_name) | stars=$($it.stargazers_count) | pushed=$($it.pushed_at) | created=$($it.created_at) | lic=$lic | lang=$($it.language) | forks=$($it.forks_count) | $desc" | Out-File -FilePath $out -Encoding UTF8 -Append
  }
  Start-Sleep -Seconds 8
}
"TOTAL UNIQUE PASS2: $($seen.Count)" | Out-File -FilePath $out -Encoding UTF8 -Append
"DONE2" | Out-File -FilePath $out -Encoding UTF8 -Append
