# Fresh-clone dry run

The rubric gives five points for "teaching staff can run it". This is the
record of someone doing exactly that, following `README.md` and nothing
else, on a machine that had never seen the project.

Run on **Sunday 25 October 2026, 09:55**, against commit `51` on `main`.

## What was done

Cloned into an empty directory with no access to the development copy, then
ran the four commands the README gives, in the order it gives them.

```bash
git clone https://github.com/pprasad19/mgt409-skincare-auditor.git
cd mgt409-skincare-auditor
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
python build_db.py
python -m uvicorn app:app --port 8000
```

## What happened

| Step | Result |
|---|---|
| Clone | 51 commits, 1.6 MB |
| Virtual environment | created, no errors |
| `pip install -r requirements.txt` | installed clean |
| `build_db.py` | compiled the rules, validated every selector, printed per-language alias coverage at 32/32 for each of ko, ja, zh, fr |
| `test_robustness.py` | 13 checks passed |
| `test_i18n.py` | 37 checks passed |
| `test_storyboard.py` | 117 checks passed |
| `test_urls.py` | 33 checks passed |
| `uvicorn app:app` | started, `GET /` returned 200 |

Nothing needed editing, no path had to be corrected, and no dependency had
to be installed by hand.

## What `build_db.py` prints, and why it is not a failure

The build ends with:

```
66 rows still marked review: pending.
These are not evidence until a human checks them.
Translations in ingredient_aliases.yaml are unverified too.
```

That is the intended output, not a warning that something is wrong. The
rule tables were drafted rather than sourced, and the build says so every
time it runs so that nobody — including us — can quietly start treating
them as verified. See `docs/verification-checklist.md`.

## The one thing a grader still needs

An API key. `PORTKEY_API_KEY` is read from a `.env` file; `.env.example`
lists the variable with no value. The app boots and serves the upload page
without one — only running an audit needs it.
