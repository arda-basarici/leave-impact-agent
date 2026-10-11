# The one-call rounds' `false` emissions by carrier

World `b7ec45636101…`, the two live rounds' capture details, read by `false_by_carrier.py`. A cell is `predicate/placement: count`, placement by the carrier's document in the sealed filler pool (`filler`), among the scenario-owned documents (`owned`), or a comment.

## one-call-single-shot

| scenario | false emissions |
|---|---|
| scenario_009 | requires/filler: 56 |
| scenario_010 | requires/filler: 50 |
| scenario_013 | requires/filler: 48 |
| scenario_014 | requires/filler: 60 |
| scenario_018 | requires/filler: 44 |
| scenario_023 | requires/filler: 44 |
| scenario_028 | requires/filler: 56 |
| **total** | **requires/filler: 358** |

## one-call-full-context

| scenario | false emissions |
|---|---|
| scenario_009 | owns_work_item/owned: 1, requires/filler: 48 |
| scenario_010 | requires/filler: 48 |
| scenario_013 | requires/filler: 48 |
| scenario_014 | requires/filler: 48 |
| scenario_018 | requires/filler: 48 |
| scenario_023 | requires/filler: 48 |
| scenario_028 | requires/filler: 48 |
| **total** | **owns_work_item/owned: 1, requires/filler: 336** |

## One filler example, read by eye

`clause_031`, quoted: Implementation of Data retention policy: Farrowmoor requires one person with experience in Terraform.

The sealed section: Implementation of Data retention policy: Farrowmoor requires one person with experience in Terraform. Maintenance of the policy requires one person with experience in Google Cloud.
