# Command: test

Used by the `quality-sentinel` skill.

## Steps
1. Load the parent `SKILL.md` and read the repo's existing test style.
2. Write the failing case first, then the happy path.
3. Cover the boundaries the type system does not enforce: empty, one, many, null,
   unicode, concurrent, and one past the limit.
4. Run the suite and report the actual output.

## Outputs
- Test files, matching the repo's existing idiom exactly
- The run result, verbatim
- Coverage against the threshold, or "not measured" with the reason

## Rules
- Match the surrounding test style even where you would write it differently.
- Never report coverage you did not measure.
