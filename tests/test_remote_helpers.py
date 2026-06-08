from backend.app.remote import sh_quote


def test_sh_quote_handles_single_quotes():
    assert sh_quote("a'b") == "'a'\"'\"'b'"


def test_sh_quote_empty_string():
    assert sh_quote("") == "''"

