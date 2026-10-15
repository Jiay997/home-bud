$ErrorActionPreference = "Continue"
$H = @{ "User-Agent" = "dsh-research"; "Accept" = "application/vnd.github+json" }
$out = "D:\HomeBud\_research\sweep3_results.txt"
"SEARCH PASS 3" | Out-File -FilePath $out -Encoding UTF8

$queries = @(
  "llm-guard user:protectai",
  "PurpleLlama user:meta-llama",
  "ShieldLM user:thu-coai",
  "Safety-Prompts user:thu-coai",
  "BeaverTails user:PKU-Alignment",
  "growthstandards user:nutriverse",
  "zscorer user:nutriverse",
  "MedMCQA",
  "medical QA dataset Chinese",
  "developmental milestones dataset",
  "child safety dataset",
  "suicide risk detection Chinese dataset"
)
foreach ($q in $queries) {
  $enc = [uri]::EscapeDataString($q)
  $url = "https://api.github.com/search/repositories?q=$enc&sort=stars&order=desc&per_page=8"
  $r = $null
  for ($try = 1; $try -le 3; $try++) {
    try { $r = Invoke-RestMethod -Uri $url -Headers $H -TimeoutSec 40; break } catch { Start-Sleep -Seconds 40 }
  }
  if ($r -eq $null) { "=== Q: $q | FAILED ===" | Out-File -FilePath $out -Encoding UTF8 -Append; continue }
  "=== Q: $q | total=$($r.total_count) ===" | Out-File -FilePath $out -Encoding UTF8 -Append
  foreach ($it in $r.items) {
    $lic = if ($it.license) { $it.license.spdx_id } else { "NONE" }
    $desc = if ($it.description) { $it.description -replace "\s+"," " } else { "" }
    if ($desc.Length -gt 230) { $desc = $desc.Substring(0,230) }
    "$($it.full_name) | stars=$($it.stargazers_count) | pushed=$($it.pushed_at) | lic=$lic | lang=$($it.language) | $desc" | Out-File -FilePath $out -Encoding UTF8 -Append
  }
  Start-Sleep -Seconds 8
}
"DONE3" | Out-File -FilePath $out -Encoding UTF8 -Append
