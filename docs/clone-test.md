# Fresh-clone dry run

The rubric gives five points for "teaching staff can run it". This is the
record of someone doing exactly that, following `README.md` and nothing
else, in an empty directory with no access to the development copy.

Run twice. The second run is the one that counts, because fifteen commits
landed between them.

| | |
|---|---|
| **First run** | 25 October 2026, 09:55, 51 commits |
| **Second run** | 25 October 2026, 16:10, 65 commits |

## What was done

```bash
git clone https://github.com/pprasad19/mgt409-skincare-auditor.git
cd mgt409-skincare-auditor
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
python build_db.py
python -m uvicorn app:app --port 8000
```

## Second run, at 65 commits

| Step | Result |
|---|---|
| Clone | 65 commits, 1.9 MB |
| Virtual environment | created, no errors |
| `pip install -r requirements.txt` | installed clean |
| `build_db.py` | compiled, every selector valid |
| `test_robustness.py` | passed |
| `test_i18n.py` | 226 checks passed |
| `test_storyboard.py` | 117 checks passed |
| `test_urls.py` | 33 checks passed |
| `test_mcp.py` | 21 checks passed |
| `uvicorn app:app` | started, `GET /` returned 200 |

Nothing needed editing, no path had to be corrected, no dependency had to
be installed by hand.

## What the second run caught

The first run reported alias coverage at 32/32 in every language. The
second reported **32/36**, naming the four ingredients added during the
day — allantoin, bisabolol, ascorbyl palmitate and titanium dioxide — as
missing from all four languages.

Nothing else would have surfaced that. The test suites passed in both
runs, because they test the aliases that exist rather than the ones that
should. It was the build's own coverage report, which prints per-language
counts on every run precisely so a gap is visible rather than inferred,
that caught it. Coverage is back to 36/36 and the two new substring cases
are pinned in `test_i18n.py`.

Those counts are this run's, not today's: six more ingredients have been
added since and coverage currently reads **42/42** in all four languages.
`python build_db.py` prints the live figure, which is the point of
printing it.

That is the argument for re-running this against the actual submitted
commit rather than trusting an earlier run.

## What `build_db.py` prints, and why it is not a failure

The build ends with a provenance summary:

```
  provenance
      33  verified   checked against a published source
      36  reasoned   reviewed, no source for this specific
                     claim, kept on a recorded mechanism

  Only verified rows are presented to the user as settled.
  Translations in ingredient_aliases.yaml remain unchecked.
```

That is intended output. The rule tables were drafted and then reviewed
row by row; the build says which rows have a published source behind them
and which rest on a recorded mechanism, every time it runs, so that
nobody — including us — starts treating the second kind as the first.

## The one thing a grader still needs

An API key. `PORTKEY_API_KEY` is read from a `.env` file and
`.env.example` lists the variable with no value. The app boots and serves
the upload page without one; only running an audit needs it.
