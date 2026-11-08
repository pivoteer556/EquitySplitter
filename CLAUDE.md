# EquitySplitter

## Compact instructions

The backlog lives in `BACKLOG.md`; update it in the same commit that finishes an item.

When compacting, keep the backlog (ordered list of remaining tasks and known gaps), the MAGI rotation pointer
(`.claude/magi/rotation.md`, currently the next agent in Balthazar -> Melchior -> Casper), and all open decisions
awaiting the user. Also keep: the repo and Azure facts needed to continue (resource names, Terraform outputs, GitHub
repo variables, what is verified vs unverified), the standing "minimum verifiable change" standard, and the rule that
the user runs `terraform apply` and must be asked before anything touching their Azure or GitHub account.

## Keeping docs current

The design docs live in `docs/specs/` (Feature 1 and Feature 2 handoff specs as .docx, schema pages as .html, plus `docs/specs/README.md` as the index). Any change to the schema, the API, auth behavior or roles updates them in the same commit, with a dated amendment, and unbuilt ideas are labelled planned. `BACKLOG.md` is updated the same way: finished items are struck through, never deleted. Tell every agent that does such work about both rules.
