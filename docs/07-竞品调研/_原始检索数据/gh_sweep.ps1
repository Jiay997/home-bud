$ErrorActionPreference = "Continue"
$H = @{ "User-Agent" = "dsh-research"; "Accept" = "application/vnd.github+json" }
$out = "D:\HomeBud\_research\sweep_results.txt"
"" | Set-Content $out

$queries = @(
  "parenting assistant",
  "baby tracker",
  "pediatric",
  "child safety content moderation",
  "topic:parenting",
  "topic:baby",
  "infant care",
  "parenting knowledge base",
  "child abuse detection NLP",
  "self-harm detection",
  "llm guardrails",
  "topic:pediatric",
  "baby log AI",
  "developmental milestone",
  "child growth tracking",
  "medication dosage safety LLM",
  "parenting agent",
  "WHO guidelines dataset",
  "temperament assessment",
  "育儿",
  "母婴",
  "儿童 健康",
  "未成年人 保护 审核",
  "baby monitor AI",
  "RAG medical QA",
  "topic:infant",
  "newborn",
  "mother and baby",
  "Content moderation dataset Chinese",
  "crisis intervention chatbot"
)

$seen = @{}
$i = 0
foreach ($q in $queries) {
  $i++
  if ($i % 9 -eq 0) { Start-Sleep -Seconds 65 }
  $enc = [uri]::EscapeDataString($q)
  $url = "https://api.github.com/search/repositories?q=$enc&sort=stars&order=desc&per_page=25"
  try {
    $r = Invoke-RestMethod -Uri $url -Headers $H -TimeoutSec 40
    "=== QUERY: $q | total=$($r.total_count) ===" | Add-Content $out
    foreach ($it in $r.items) {
      if ($seen.ContainsKey($it.full_name)) { continue }
      $seen[$it.full_name] = 1
      $lic = if ($it.license) { $it.license.spdx_id } else { "NONE" }
      $desc = if ($it.description) { $it.description -replace "\s+", " " } else { "" }
      if ($desc.Length -gt 260) { $desc = $desc.Substring(0, 260) }
      "$($it.full_name) | stars=$($it.stargazers_count) | pushed=$($it.pushed_at) | created=$($it.created_at) | lic=$lic | lang=$($it.language) | forks=$($it.forks_count) | $desc" | Add-Content $out
    }
  } catch {
    "=== QUERY: $q | ERROR: $($_.Exception.Message) ===" | Add-Content $out
  }
}
"TOTAL UNIQUE: $($seen.Count)" | Add-Content $out
"DONE" | Add-Content $out
