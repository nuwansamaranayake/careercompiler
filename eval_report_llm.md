# CareerCompiler key-gated extraction eval

model: google/gemini-2.5-flash
base claim_keys (14): ['action_built_backends', 'action_designed_ci_cd', 'action_led_migration', 'action_mentored_engineers', 'action_operated_postgresql', 'duration_five_years', 'magnitude_4_engineers', 'outcome_deploy_time_reduction', 'platform_github_actions', 'platform_kubernetes', 'platform_python_fastapi', 'scope_42_services', 'skill_backups', 'skill_replication']

| metric | value | bound | pass |
|---|---|---|---|
| planted-fact recall | 1.00 | >= 0.7 | PASS |
| paraphrase jaccard (min) | 0.92 | >= 0.6 | PASS |

contract: contracts/extraction-stability.yaml (threshold 0.6)
