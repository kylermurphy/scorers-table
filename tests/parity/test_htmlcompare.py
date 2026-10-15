"""The comparer itself: it must see the differences the parity test exists to catch, and only those."""
from tests.parity.htmlcompare import compare_fragments as cmp


def same(a, b, **kw):
    return cmp(a, b, **kw) is None


def test_whitespace_between_blocks_and_indentation_do_not_matter():
    assert same("<div><p>a</p><p>b</p></div>", "<div>\n  <p>a</p>\n  <p>b</p>\n</div>")


def test_a_space_between_inline_elements_matters():
    assert not same("<p><span>a</span> <span>b</span></p>", "<p><span>a</span><span>b</span></p>")


def test_text_spaces_collapse_and_edges_trim_at_block_boundaries():
    assert same("<p>a   b</p>", "<p> a b </p>")
    assert not same("<p>a b</p>", "<p>a  c</p>")


def test_class_order_is_free_but_the_set_is_not():
    assert same('<i class="a b">x</i>', '<i class="b a">x</i>')
    assert not same('<i class="a b">x</i>', '<i class="a">x</i>')


def test_href_by_presence_id_and_hidden_ignored_other_attributes_not():
    assert same('<a href="#" id="x">t</a>', '<a href="/p/">t</a>')
    assert not same('<a href="#">t</a>', "<a>t</a>")
    assert same("<button hidden>t</button>", "<button>t</button>")
    assert not same('<i aria-label="a">t</i>', '<i aria-label="b">t</i>')
    assert not same('<i style="width:5%">t</i>', '<i style="width:6%">t</i>')
    assert same('<i style="width: 5%;">t</i>', '<i style="width:5%">t</i>')


def test_the_dark_header_toggle_is_masked():
    moon = '<button class="st-theme-toggle" aria-label="Switch to dark theme"><svg></svg></button>'
    sun = '<button class="st-theme-toggle" aria-label="Switch to light theme"><svg><g></g></svg></button>'
    assert not same(sun, moon)
    assert same(sun, moon, mask_toggle=True)


def test_the_difference_is_reported_with_a_path():
    path, message, a, b = cmp('<div><ul class="l"><li>a</li></ul></div>', '<div><ul class="l"><li>b</li></ul></div>')
    assert "ul.l" in path and "li" in path and "text differs" in message
