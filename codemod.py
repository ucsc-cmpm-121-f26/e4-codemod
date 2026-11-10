#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["tree-sitter==0.25.2", "tree-sitter-typescript==0.23.2"]
# ///
"""Read Neon Warden's copy-pasted wave blocks and print them as a table.

Python reading TypeScript: this program never runs the game. It parses
game.ts into a syntax tree, recognizes each wave block by its shape, and
prints one table row per wave.

Usage: uv run --script codemod.py path/to/game.ts
"""

import sys

import tree_sitter_typescript
from tree_sitter import Language, Parser

WIDTH = 480  # playfield width; the table stores x as a fraction of it

# A block's shape: (spawn-tick condition, x expression), with every number
# written as # and the loop variable written as i.
FORMATIONS = {
    ("t===#", "#+(i-#)*#"): "line",
    ("t===#+Math.abs(i-#)*#", "#+(i-#)*#"): "vee",
    ("t===#+i*#", "#"): "column",
    ("t===#+Math.floor(i/#)*#", "i%#===#?-#:#"): "pincer",
}


def fingerprint(node, var):
    """`360 + Math.abs(n - 2) * 10` with var "n" -> ("#+Math.abs(i-#)*#", [360, 2, 10])."""
    numbers = []

    def walk(n):
        if n.type == "number":
            numbers.append(float(n.text))
            return "#"
        if n.type == "identifier" and n.text.decode() == var:
            return "i"
        if n.child_count == 0:
            return n.text.decode()
        return "".join(walk(child) for child in n.children)

    return walk(node), numbers


def nodes(node):
    """Every node of the tree under node, in source order."""
    yield node
    for child in node.children:
        yield from nodes(child)


def find(node, type_):
    """The first node of this type at or below node."""
    return next((n for n in nodes(node) if n.type == type_), None)


def wave(loop):
    """One `for`/`while` wave block -> one table row."""
    test = find(loop.child_by_field_name("condition"), "binary_expression")  # i < 4
    var, count = test.child_by_field_name("left").text.decode(), int(test.child_by_field_name("right").text)
    spawn_if = find(loop.child_by_field_name("body"), "if_statement")
    when, (ticks, *_) = fingerprint(spawn_if.child_by_field_name("condition").named_children[0], var)
    where, (x, *_) = fingerprint(find(spawn_if, "variable_declarator").child_by_field_name("value"), var)
    kind = find(find(spawn_if, "new_expression"), "string_fragment").text.decode()

    formation = FORMATIONS.get((when, where))
    if formation is None:
        sys.exit(f"game.ts:{loop.start_point.row + 1}: unrecognized wave shape {when!r}, {where!r}")
    row = f'{{ at: {ticks / 60:g}, kind: "{kind}", count: {count}, formation: "{formation}"'
    return row + (" }," if formation == "pincer" else f", x: {x / WIDTH:g} }},")


source = open(sys.argv[1], "rb").read()
root = Parser(Language(tree_sitter_typescript.language_typescript())).parse(source).root_node
method = next(n for n in nodes(root)
              if n.type == "method_definition" and n.child_by_field_name("name").text == b"updateProgression")

rows, sector = [], 0
branch = find(method, "if_statement")  # if (this.sector === 0) { … } else if (this.sector === 1) { … }
while branch:
    sector += 1
    rows.append(f"// sector {sector}")
    for statement in branch.child_by_field_name("consequence").named_children:
        if statement.type in ("for_statement", "while_statement"):
            rows.append(wave(statement))
    otherwise = branch.child_by_field_name("alternative")
    branch = otherwise.named_children[0] if otherwise else None

print("\n".join(rows))
