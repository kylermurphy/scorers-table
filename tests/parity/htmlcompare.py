"""Compare the markup of a stage 3 specimen with the markup an include rendered.

Both sides are parsed with the standard library, normalised as below and compared node by node. The first
difference is reported with its path and both snippets.

THE RULES (everything not listed here is compared exactly):

1. Elements: tag names equal, same number of children, in the same order.
2. Attributes are all compared, except:
   * `class`: compared as a set (order does not matter);
   * `style`: whitespace around `:` and `;` and a trailing `;` are ignored;
   * `href`: only its presence is compared (the specimens use `#`, the includes real site paths);
   * `id`, `hidden`, `aria-labelledby`: ignored. An id exists only to be pointed at (the specimen makes one per
     layout, theme and sport, the include one fixed id), and `hidden` is how the include renders the theme
     button until site.js runs.
3. Text: whitespace runs collapse to one space. A text node loses its leading/trailing space at the edge of its
   parent and next to a block-level element, and keeps one next to an inline element or text; a
   whitespace-only node is kept (as one space) only between two inline neighbours, dropped elsewhere. So
   `</span> <span>` must match, and indentation between `<div>`s does not matter.
4. Entities are decoded before comparing (`&#x27;` and `&#39;` are the same).
5. The theme button (`button.st-theme-toggle`) in the DARK header: its `aria-label` and contents are ignored,
   because the specimen draws the sun there and the include always draws the moon, which site.js swaps. The
   light header and the theme-button part compare it in full.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from html.parser import HTMLParser

VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}
INLINE = {"a", "abbr", "b", "strong", "i", "em", "span", "code", "small", "svg", "img", "br", "button", "label",
          "sup", "sub", "time", "mark", "circle", "path", "g", "rect", "line", "polyline", "polygon", "ellipse"}
IGNORED_ATTRS = {"id", "hidden", "aria-labelledby"}


@dataclass
class Node:
    tag: str
    attrs: dict = field(default_factory=dict)
    children: list = field(default_factory=list)   # Node | str


class _Builder(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = Node("#root")
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        node = Node(tag, {k: ("" if v is None else v) for k, v in attrs})
        self.stack[-1].children.append(node)
        if tag not in VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        node = Node(tag, {k: ("" if v is None else v) for k, v in attrs})
        self.stack[-1].children.append(node)

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                return

    def handle_data(self, data):
        self.stack[-1].children.append(data)


def parse(html: str) -> Node:
    b = _Builder()
    b.feed(html)
    b.close()
    return b.root


def _is_inline(x) -> bool:
    return isinstance(x, str) or x.tag in INLINE


def _clean_children(node: Node) -> list:
    """The node's children with text collapsed (rule 3): Node objects and strings."""
    kids = node.children
    out: list = []
    for i, k in enumerate(kids):
        if isinstance(k, Node):
            out.append(k)
            continue
        text = re.sub(r"\s+", " ", k)
        prev = kids[i - 1] if i else None
        nxt = kids[i + 1] if i + 1 < len(kids) else None
        inline_prev = prev is not None and _is_inline(prev)
        inline_next = nxt is not None and _is_inline(nxt)
        if text.strip() == "":
            if text and inline_prev and inline_next:
                out.append(" ")
            continue
        if not inline_prev:
            text = text.lstrip()
        if not inline_next:
            text = text.rstrip()
        out.append(text)
    # merge adjacent strings (a dropped comment or entity could split one)
    merged: list = []
    for x in out:
        if isinstance(x, str) and merged and isinstance(merged[-1], str):
            merged[-1] += x
        else:
            merged.append(x)
    return merged


def _attrs(node: Node, mask_toggle: bool) -> dict:
    out = {}
    for k, v in node.attrs.items():
        if k in IGNORED_ATTRS:
            continue
        if mask_toggle and k == "aria-label":
            continue
        if k == "class":
            out[k] = tuple(sorted(set(v.split())))
        elif k == "style":
            s = re.sub(r"\s*([:;])\s*", r"\1", v.strip()).rstrip(";")
            out[k] = s
        elif k == "href":
            out[k] = "*"
        else:
            out[k] = re.sub(r"\s+", " ", v).strip()
    return out


def _label(node: Node) -> str:
    cls = node.attrs.get("class", "").split()
    return node.tag + ("".join("." + c for c in cls[:3]) if cls else "")


def snippet(x, limit: int = 260) -> str:
    if isinstance(x, str):
        return repr(x)
    parts = [f"<{x.tag}" + "".join(f' {k}="{v}"' for k, v in x.attrs.items() if k != "d") + ">"]
    for c in x.children:
        parts.append(snippet(c, limit) if isinstance(c, Node) else re.sub(r"\s+", " ", c))
        if sum(map(len, parts)) > limit:
            parts.append("...")
            break
    parts.append(f"</{x.tag}>")
    out = "".join(parts)
    return out if len(out) <= limit + 20 else out[:limit] + "..."


def first_difference(a, b, path: str = "", mask_toggle: bool = False):
    """None when the two nodes match, else (path, message, snippet_a, snippet_b)."""
    if isinstance(a, str) or isinstance(b, str):
        if a != b:
            return (path, "text differs", snippet(a), snippet(b))
        return None
    here = f"{path} > {_label(a)}" if path else _label(a)
    if a.tag != b.tag:
        return (here, f"tag differs: {a.tag} vs {b.tag}", snippet(a), snippet(b))
    toggle = mask_toggle and a.tag == "button" and "st-theme-toggle" in a.attrs.get("class", "")
    aa, ab = _attrs(a, toggle), _attrs(b, toggle)
    if aa != ab:
        keys = sorted(set(aa) | set(ab))
        bad = [k for k in keys if aa.get(k) != ab.get(k)]
        return (here, "attributes differ: " + ", ".join(f"{k}: {aa.get(k)!r} vs {ab.get(k)!r}" for k in bad),
                snippet(a), snippet(b))
    if toggle:
        return None
    ka, kb = _clean_children(a), _clean_children(b)
    for i in range(max(len(ka), len(kb))):
        if i >= len(ka) or i >= len(kb):
            return (here, f"child count differs: {len(ka)} vs {len(kb)} (first extra: child {i})",
                    snippet(a), snippet(b))
        xa, xb = ka[i], kb[i]
        if isinstance(xa, str) != isinstance(xb, str):
            return (here, f"child {i} is text on one side only", snippet(xa), snippet(xb))
        d = first_difference(xa, xb, here, mask_toggle)
        if d:
            return d
    return None


def children_of(html: str) -> list:
    """The cleaned top-level children of a fragment."""
    return _clean_children(parse(html))


def compare_fragments(expected_html: str, actual_html: str, mask_toggle: bool = False,
                      drop_expected: tuple = ()):
    """None, or (path, message, expected snippet, actual snippet) for the first difference.

    drop_expected: ((tag, class), ...) children of the expected side's outer wrapper to leave out (a
    specimen's demo-only element that has no include, such as the top-scorer tile)."""
    ea, aa = parse(expected_html), parse(actual_html)
    if drop_expected:
        wrapper = next(k for k in ea.children if isinstance(k, Node))
        wrapper.children = [
            k for k in wrapper.children
            if not (isinstance(k, Node) and any(k.tag == t and c in k.attrs.get("class", "").split()
                                                for t, c in drop_expected))]
    return first_difference(ea, aa, "", mask_toggle)
