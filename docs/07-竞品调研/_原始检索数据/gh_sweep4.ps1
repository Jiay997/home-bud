$H = @{ "User-Agent" = "dsh-research"; "Accept" = "application/vnd.github+json" }
$out = "D:\HomeBud\_research\sweep4_results.txt"
"SEARCH PASS 4" | Out-File -FilePath $out -Encoding UTF8

$queries = Get-Content "D:\HomeBud\_research\queries4.txt" -Encoding UTF8
foreach ($q in $queries) {
  $enc = [uri]::EscapeDataString($q)
  $url = "https://api.github.com/search/repositories?q=$enc" + "&sort=stars&order=desc&per_page=10"
  $r = $null
  for ($t = 1; $t -le 3; $t++) { try { $r = Invoke-RestMethod -Uri $url -Headers $H -TimeoutSec 40; break } catch { Start-Sleep -Seconds 40 } }
  if ($r -eq $null) { "=== Q: $q | FAILED ===" | Out-File -FilePath $out -Encoding UTF8 -Append; continue }
  "=== Q: $q | total=$($r.total_count) ===" | Out-File -FilePath $out -Encoding UTF8 -Append
  foreach ($it in $r.items) {
    $lic = if ($it.license) { $it.license.spdx_id } else { "NONE" }
    $desc = if ($it.description) { $it.description -replace "\s+"," " } else { "" }
    if ($desc.Length -gt 200) { $desc = $desc.Substring(0,200) }
    ($it.full_name + " | stars=" + $it.stargazers_count + " | pushed=" + $it.pushed_at + " | lic=" + $lic + " | lang=" + $it.language + " | " + $desc) | Out-File -FilePath $out -Encoding UTF8 -Append
  }
  Start-Sleep -Seconds 8
}

"--- RAW README EXISTENCE TESTS ---" | Out-File -FilePath $out -Encoding UTF8 -Append
foreach ($t in @("nutriverse/growthstandards","nutriverse/zscorer","nutriverse/gigs","WorldHealthOrganization/anthro","hsongra11/mychild-app","twastvedt/Baby-Skill-Tree")) {
  $found = "NOT FOUND"
  foreach ($br in @("main","master")) {
    try { $x = Invoke-WebRequest -Uri "https://raw.githubusercontent.com/$t/$br/README.md" -Headers @{ "User-Agent"="dsh-research" } -TimeoutSec 20 -UseBasicParsing; $found = "OK " + $br + " len=" + $x.Content.Length; break } catch { }
  }
  ($t + " :: " + $found) | Out-File -FilePath $out -Encoding UTF8 -Append
}
"DONE4" | Out-File -FilePath $out -Encoding UTF8 -Append
