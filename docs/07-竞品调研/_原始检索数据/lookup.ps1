$H = @{ "User-Agent" = "dsh-research"; "Accept" = "application/vnd.github+json" }
$repos = @(
  "protectai/llm-guard",
  "meta-llama/PurpleLlama",
  "thu-coai/ShieldLM",
  "thu-coai/Safety-Prompts",
  "PKU-Alignment/BeaverTails",
  "nutriverse/growthstandards",
  "nutriverse/zscorer",
  "WorldHealthOrganization/anthro",
  "UNICEFECAR/parenting-app-bebbo-mobile",
  "jiangnanboy/pediatrics_llm_qa",
  "Lucius1105/daihaowa-ai-parenting-expert",
  "houbb/sensitive-word",
  "konsheng/Sensitive-lexicon",
  "guardrails-ai/guardrails",
  "NVIDIA-NeMo/Guardrails"
)
foreach ($r in $repos) {
  try {
    $d = Invoke-RestMethod -Uri "https://api.github.com/repos/$r" -Headers $H -TimeoutSec 30
    $lic = if ($d.license) { $d.license.spdx_id } else { "NONE" }
    $desc = if ($d.description) { ($d.description -replace "\s+"," ") } else { "" }
    "$($d.full_name) | stars=$($d.stargazers_count) | forks=$($d.forks_count) | pushed=$($d.pushed_at) | created=$($d.created_at) | lic=$lic | lang=$($d.language) | archived=$($d.archived) | $desc"
  } catch { "FAILED $r :: $($_.Exception.Message)" }
}
