# Denominance Lab

Run 3 complete.

A local batch-model prototype now has 12 passing tests. It covers declaration
parsing, same-origin conflict handling, disjoint declarations, recoloring
rejection, missing output origins, zero-value origins, and born-burned outputs.

Key rule: same-origin declarations reject as a group instead of first-wins.
Output origin follows the inscription's resolved location rather than a second
explicit selector.

Next: connect the model to real Ord fixtures before adding persistent tables.
