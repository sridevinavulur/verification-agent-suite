from assertion_mutation_agent.lexer import code_tokens, tokenize


def test_line_col_tracking():
    src = "a=1;\nbb = 22;"
    toks = tokenize(src)
    # find the '22' number on line 2
    nums = [t for t in toks if t.kind == "number"]
    assert nums[0].value == "1" and nums[0].line == 1
    assert nums[1].value == "22" and nums[1].line == 2 and nums[1].col == 6


def test_sized_literal_is_single_number():
    toks = code_tokens(tokenize("x <= 8'hFF;"))
    values = [t.value for t in toks]
    assert "8'hFF" in values


def test_multichar_operators():
    toks = code_tokens(tokenize("a <= b && c == d;"))
    ops = [t.value for t in toks if t.kind == "op"]
    assert "<=" in ops and "&&" in ops and "==" in ops


def test_comments_and_strings_not_code():
    src = '// hi\nx = 1; /* block */ "str"'
    toks = tokenize(src)
    kinds = {t.kind for t in toks}
    assert "comment" in kinds and "string" in kinds
    code = code_tokens(toks)
    assert all(t.is_code for t in code)


def test_directive_does_not_crash():
    toks = code_tokens(tokenize("`define W 8\nreg [`W-1:0] x;"))
    assert any(t.value == "`define" for t in toks)


def test_unrecognized_char_raises():
    import pytest

    with pytest.raises(ValueError):
        tokenize("\x01")
