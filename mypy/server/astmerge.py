"""Merge a new version of a module AST and symbol table to older versions of those.

When the source code of a module has a change in fine-grained incremental mode,
we build a new AST from the updated source. However, other parts of the program
may have direct references to parts of the old AST (namely, those nodes exposed
in the module symbol table). The merge operation changes the identities of new
AST nodes that have a correspondance in the old AST to the old ones so that
existing cross-references in other modules will continue to point to the correct
nodes. Also internal cross-references within the new AST are replaced. AST nodes
that aren't externally visible will get new, distinct object identities. This
applies to most expression and statement nodes, for example.

We perform this merge operation so that we don't have to update all
external references (which would be slow and fragile) or always perform
translation when looking up references (which would be hard to retrofit).

The AST merge operation is performed after semantic analysis. Semantic
analysis has to deal with potentionally multiple aliases to certain AST
nodes (in particular, MypyFile nodes). Type checking assumes that we
don't have multiple variants of a single AST node visible to the type
checker.

Discussion of some notable special cases:

* If a node is replaced with a different kind of node (say, a function is
  replaced with a class), we don't perform the merge. Fine-grained dependencies
  will be used to rebind all references to the node.

* If a function is replaced with another function with an identical signature,
  call sites continue to point to the same object (by identity) and don't need
  to be reprocessed. Similary, if a class is replaced with a class that is
  sufficiently similar (MRO preserved, etc.), class references don't need any
  processing. A typical incremental update to a file only changes a few
  externally visible things in a module, and this means that often only few
  external references need any processing, even if the modified module is large.

* A no-op update of a module should not require any processing outside the
  module, since all relevant object identities are preserved.

* The AST diff operation (mypy.server.astdiff) and the top-level fine-grained
  incremental logic (mypy.server.update) handle the cases where the new AST has
  differences from the old one that may need to be propagated to elsewhere in the
  program.

See the main entry point merge_asts for more details.
"""

from typing import Dict, List, Optional

from mypy.nodes import (
    MypyFile, SymbolTable, SymbolNode, TypeInfo, MDEF
)
from mypy.util import get_prefix


def merge_asts(old: MypyFile, old_symbols: SymbolTable,
               new: MypyFile, new_symbols: SymbolTable) -> None:
    """Merge a new version of a module AST to a previous version.

    The main idea is to preserve the identities of externally visible
    nodes in the old AST (that have a corresponding node in the new AST).
    All old node state (outside identity) will come from the new AST.

    When this returns, 'old' will refer to the merged AST, but 'new_symbols'
    will be the new symbol table. 'new' and 'old_symbols' will no longer be
    valid.
    """
    assert new.fullname() == old.fullname()
    # Find the mapping from new to old node identities for all nodes
    # whose identities should be preserved.
    replacement_map = replacement_map_from_symbol_table(
        old_symbols, new_symbols, prefix=old.fullname())
    # Also replace references to the new MypyFile node.
    replacement_map[new] = old

    for src, dst in replacement_map.items():
        selfify(dst, src)


def replacement_map_from_symbol_table(
        old: SymbolTable, new: SymbolTable, prefix: str) -> Dict[SymbolNode, SymbolNode]:
    """Create a new-to-old object identity map by comparing two symbol table revisions.

    Both symbol tables must refer to revisions of the same module id. The symbol tables
    are compared recursively (recursing into nested class symbol tables), but only within
    the given module prefix. Don't recurse into other modules accessible through the symbol
    table.
    """
    replacements = {}  # type: Dict[SymbolNode, SymbolNode]
    for name, node in old.items():
        if (name in new and (node.kind == MDEF
                             or node.node and get_prefix(node.node.fullname()) == prefix)):
            new_node = new[name]
            if (type(new_node.node) == type(node.node)  # noqa
                    and new_node.node and node.node and
                    new_node.node.fullname() == node.node.fullname() and
                    new_node.kind == node.kind):
                replacements[new_node.node] = node.node
                if isinstance(node.node, TypeInfo) and isinstance(new_node.node, TypeInfo):
                    type_repl = replacement_map_from_symbol_table(
                        node.node.names,
                        new_node.node.names,
                        prefix)
                    replacements.update(type_repl)
    return replacements


def selfify(new: object, old: object) -> None:
    if new.__dict__ is old.__dict__: return
    new.__dict__.clear()
    new.__dict__.update(old.__dict__)
    old.__dict__ = new.__dict__
