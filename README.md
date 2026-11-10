# Neon Warden, read by a program

In E4.b step 4 you turned 35 copy-pasted wave blocks in `src/game.ts` into one
table, deleting about 800 lines by hand. This repository shows the core of a
**codemod**, a program that reads source code so a refactoring can be done
mechanically. It goes with the reading
[Refactoring with Codemods to Automate API Changes](https://martinfowler.com/articles/codemods-api-refactoring.html)
by Juntao Qiu (on martinfowler.com, 2025).

You do not need to run anything here. Read this page and
[`codemod.py`](codemod.py) (about 60 lines of code). Everything quoted below
came from actually running it; [Evidence](#evidence) shows how.

## Two languages, two levels

The game is written in **TypeScript**. The codemod is written in **Python** on
purpose, so the two levels never blur:

| | Language | Runs when | Its job |
| --- | --- | --- | --- |
| `game.ts` (the subject) | TypeScript | in the browser, every frame | fly ships, spawn enemies |
| `codemod.py` (the tool) | Python | once, on a developer's machine | read `game.ts`, print a table |

The codemod never runs the game. To Python, `game.ts` is only data: a tree of
syntax.

## What it does

It takes the hardest part of step 4, *recognizing* what each of the 35 blocks
means, and does it for all 35 at once. The output is the table you built by
hand ([`examples/table.txt`](examples/table.txt)):

```text
// sector 1
{ at: 1, kind: "drone", count: 4, formation: "line", x: 0.5 },
{ at: 6, kind: "drone", count: 5, formation: "vee", x: 0.35 },
{ at: 11, kind: "drone", count: 5, formation: "vee", x: 0.65 },
...
```

It stops there. Pasting the rows into `route.ts` and writing the loop that reads
them are still a person's job. A full codemod would also do that rewriting:
Qiu's examples parse, modify the tree, and write the code back out.

## How it reads TypeScript

1. **Parse.** [tree-sitter](https://tree-sitter.github.io/tree-sitter/), a
   parser used for syntax highlighting and code navigation in many editors and
   on GitHub, turns `game.ts` into a tree of nodes like `for_statement`,
   `if_statement`, and `new_expression`. The codemod walks the tree instead of
   searching the text.
2. **Fingerprint.** For each wave block, it takes the spawn condition and the
   `x` expression and reduces each one to a *fingerprint*: numbers become `#`,
   and the loop variable becomes `i`. Here are two real blocks: one from
   sector 1 (a `for` loop over `i`) and one from sector 4 (written in another
   style, as a `while` loop over `n`):

   ```text
   game.ts:467  t === 360 + Math.abs(i - 2) * 10    ->  "t===#+Math.abs(i-#)*#"  [360, 2, 10]
   game.ts:897  t === 360 + Math.abs(n - 2.5) * 10  ->  "t===#+Math.abs(i-#)*#"  [360, 2.5, 10]
   ```

   Different text, same fingerprint. Renaming the loop variable is what makes
   the two styles match.
3. **Look up.** A four-entry dictionary, `FORMATIONS`, maps fingerprints to
   formation names. The numbers it pulled out supply the rest: 360 ticks is
   6 seconds, and an x of 168 is 0.35 of the 480-pixel screen.

Reading order for `codemod.py`: `FORMATIONS`, then `fingerprint`, then `wave`,
then the loop at the bottom that walks the sector branches.

## What it gets wrong, on purpose

This is close to the simplest version that works, so its gaps show clearly.
Qiu's section on pitfalls is about exactly these.

- **An unknown shape stops the run.** Add `+ 1` to one block's `x` and it
  prints nothing but this:

  ```text
  game.ts:466: unrecognized wave shape 't===#+Math.abs(i-#)*#', '#+(i-#)*#+#'
  ```

  Stopping is the safe failure: no partly correct table.
- **A shape it knows, with the wrong numbers, slips through.** Change that
  block's spacing from `* 44` to `* 45` and the table comes out *unchanged*.
  The fingerprint still says "vee", and the codemod never checks the spacing,
  so the table quietly describes different behavior from the code it read.
  Fixing that means comparing every number with what `layout()` would
  produce, or, as Qiu recommends, writing test cases first and checking the
  codemod against real code before trusting it.
- **It reads only what it needs.** It ignores comments, and the
  `enemy2`/`enemy3` slip never comes up, because it doesn't look at that line.
  That's fine for printing a table. A codemod that *rewrote* `game.ts` would
  have to account for every line it deletes.

Each fix makes the tool longer, and that's the real cost of a codemod. A
program like this can be ready in an afternoon; one you can trust on code
you've never seen takes much longer.

## Was a codemod worth it here?

Honestly, no, not for this job alone. Step 4 is 35 changes in one file. You can
read every one of them, and the self-play line tells you if you got any wrong.
That's why E4 had you do it by hand. Before this short version, a fuller one
was written that also rewrote `game.ts`, passed `deno task ci`, and reproduced
the self-play line exactly. It ran to about 400 lines of Python: more than
the roughly 200 lines of TypeScript it produced, and far more machinery to
trust than a careful hand edit of one file.

The trade-off flips with scale. If the same 35-block pattern were spread
across 100 files, or across many teams' repositories (Qiu's situation, rolling
out a design-system change at Atlassian), editing by hand would be slow and
error-prone. Then the cost of building and testing a codemod pays for itself,
and that cost is spread over every file it fixes.

Coding agents shift the break-even point. Both versions of this codemod were
written quickly with an agent's help. When a throwaway codemod costs minutes
instead of days, it can make sense at much smaller scales, even for one file.
The cost moves from *writing* the tool to *checking* it: you still need
evidence, like the table comparison below or an unchanged self-play line, that
the tool did what you meant.

## Code that writes code, both directions

A confession: the 35 blocks you cleaned up were never typed by hand. The
instructor, working with an AI coding agent, built the clean game first. A small
Python program then read `route.ts` and generated the copy-pasted blocks from
it, slip and lying comments included, to make the E4 starter. That program and
this one run in opposite directions over the same TypeScript: table to blocks,
then blocks back to table. Running that generator on the clean code, then
`deno fmt`, reproduces the starter's `game.ts` byte for byte.

## Evidence

The input, [`examples/before/game.ts`](examples/before/game.ts), is Neon
Warden as it stands after E4 steps 1–3, taken from the instructor's E4
development repository (tag `before-step-4`).

```console
$ uv run --script codemod.py examples/before/game.ts > examples/table.txt
$ diff <(git show before-step-5:src/route.ts | grep -o '{ at:.*') \
       <(grep -o '{ at:.*' examples/table.txt) && echo identical
identical
```

All 35 rows match, in order, the table the instructor's clean game uses
(`src/route.ts` at tag `before-step-5`, the state right after step 4).

## Files

| File | What it is |
| --- | --- |
| [`codemod.py`](codemod.py) | The codemod; its dependencies are declared inline, so `uv` installs them on first run |
| [`examples/before/game.ts`](examples/before/game.ts) | Input: Neon Warden after E4 steps 1–3 |
| [`examples/table.txt`](examples/table.txt) | Output: one row per wave |

## Credits

Written for CMPM 121 (UC Santa Cruz, Fall 2026). The codemod and this page were
written by the instructor with authorized Anthropic Claude agent assistance,
and checked by running them as described above.
