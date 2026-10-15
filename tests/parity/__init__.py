"""Parity harness for tests/test_parity.py: the stage 3 specimens against the Jekyll includes.

htmlcompare.py   parse two HTML fragments and compare them (the rules are in its docstring)
site.py          build the throwaway Jekyll site: the repo's includes, the converted sample data, one page per
                 (layout, sport), one block per part case
cases.py         the part cases: which specimen, which case template, which layouts and sports, what is skipped
cases/*.html     one Liquid template per part: the specimen's own scaffolding with the includes in it
"""
