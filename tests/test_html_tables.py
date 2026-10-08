import pytest
from html_tables import wrap_tables


def test_table_wrapping_is_idempotent_and_preserves_surrounding_bytes():
    original = '<p>Before</p>\n<table class="data"><tr><th>A</th></tr></table>\n<p>Between</p><table><tr><th>B</th></tr></table><p>After</p>'
    result = wrap_tables(original, 'A & "B"')
    assert wrap_tables(result, 'A & "B"') == result
    assert result.count('class="dasc-table-scroll"') == 2
    assert 'table 1"' in result and 'table 2"' in result
    assert result.startswith("<p>Before</p>") and result.endswith("<p>After</p>")
    assert '<table class="data"><tr><th>A</th></tr></table>' in result


@pytest.mark.parametrize(
    "source", ["<table><table></table></table>", "<table>", "</table>", "<table/>"]
)
def test_unsupported_or_incomplete_tables_fail_explicitly(source):
    with pytest.raises(ValueError):
        wrap_tables(source, "Page")


def test_table_looking_text_in_comments_and_scripts_is_preserved():
    source = (
        '<!-- <table>example</table> --><script>const example = "<table>text</table>";</script>'
    )
    assert wrap_tables(source, "Page") == source


def test_existing_wrapped_table_is_not_wrapped_again():
    source = '<div class="dasc-table-scroll" role="region" tabindex="0" aria-label="Existing"><table><tr><th>A</th></tr></table></div>'
    assert wrap_tables(source, "Page") == source
