param([string[]]$Repos, [int]$Chars = 1400)
$H = @{ "User-Agent" = "dsh-research" }
foreach ($t in $Repos) {
  $done = $false
  foreach ($br in @("main","master")) {
    if ($done) { continue }
    foreach ($fn in @("README.md","readme.md","README.rst")) {
      if ($done) { continue }
      try {
        $r = Invoke-WebRequest -Uri "https://raw.githubusercontent.com/$t/$br/$fn" -Headers $H -TimeoutSec 25 -UseBasicParsing
        $c = $r.Content
        $c = $c -replace "`r",""
        if ($c.Length -gt $Chars) { $c = $c.Substring(0, $Chars) + "`n...[TRUNCATED]" }
        "########## $t ($br/$fn) len=$($r.Content.Length) ##########"
        $c
        $done = $true
      } catch { }
    }
  }
  if (-not $done) { "########## $t :: NO README FOUND ##########" }
}
