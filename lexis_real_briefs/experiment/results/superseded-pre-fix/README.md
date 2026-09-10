# Superseded — run against the pre-fix Gym

Nothing in this directory is a result. It is kept only so the fixes can be shown
to have been necessary, and because deleting evidence of a void run is how a void
run gets forgotten.

Three defects were found and repaired after these were produced:

1. **`unhashable type: 'list'`** — the guard rejecting a malformed `unitId`
   tested set membership before type, so a model answering with a list killed
   the run. One run here died of it (`2x2-gpt-gpt/F003-mutant`).
2. **The record cap** — a hard-coded 6,000 characters per material meant an
   attached record reached the model as its first two pages. F007's
   record-support gold label was unscoreable in every run here.
3. **The exhibit boundary** — an inline "See attached Exhibit 2" in a page's
   opening lines was read as the start of the attachments. It does not affect
   these runs, whose fixtures were pre-split, but it is repaired in the same pass.

The `2x2-gpt-gpt` and `2x2-ds-ds` directories are also incomplete: they were
stopped mid-cell when the decision to re-run was taken.

No adjudication was performed against any of this, and the blind worksheet built
from it was deleted rather than carried forward.
