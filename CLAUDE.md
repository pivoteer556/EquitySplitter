# EquitySplitter

## Compact instructions

The backlog lives in `BACKLOG.md`; update it in the same commit that finishes an item.

When compacting, keep the backlog (ordered list of remaining tasks and known gaps), the MAGI rotation pointer
(`.claude/magi/rotation.md`, currently the next agent in Balthazar -> Melchior -> Casper), and all open decisions
awaiting the user. Also keep: the repo and Azure facts needed to continue (resource names, Terraform outputs, GitHub
repo variables, what is verified vs unverified), the standing "minimum verifiable change" standard, and the rule that
the user runs `terraform apply` and must be asked before anything touching their Azure or GitHub account.
