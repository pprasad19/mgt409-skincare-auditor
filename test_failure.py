"""What a tester sees when something breaks.

Fifteen of the hundred points are "it works", and a model call that
times out or returns something unparseable is the most likely way an
audit fails in front of a stranger. The handling reads well. Reading is
not the same as exercising it, and three of today's findings were things
that read correctly and did not behave.

Drives the real route with the real app, failing one agent at a time.
No API calls: the agents are replaced.
"""

import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from fastapi.testclient import TestClient  # noqa: E402

import app as app_module  # noqa: E402

failures: list[str] = []
checks = 0

client = TestClient(app_module.app, raise_server_exceptions=False)
TYPED = {"typed": "CeraVe Foaming Facial Cleanser\n  water, niacinamide"}


def check(label: str, cond: bool, detail: str = "") -> None:
    global checks
    checks += 1
    if not cond:
        failures.append(f"{label}{': ' + detail if detail else ''}")


def temp_dirs() -> set:
    root = Path(tempfile.gettempdir())
    return {p for p in root.glob("shelf-*") if p.is_dir()}


def with_failing(name: str, exc: Exception):
    """Replace one agent with something that raises, then restore it."""
    original = getattr(app_module, name)

    async def boom(*a, **k):
        raise exc

    setattr(app_module, name, boom)
    try:
        before = temp_dirs()
        r = client.post("/audit", data=TYPED)
        return r, before
    finally:
        setattr(app_module, name, original)


# --- the shelf reader dies -------------------------------------------
for label, exc in (
    ("a timeout", TimeoutError("upstream timed out")),
    ("a transport error", ConnectionError("connection reset")),
    ("unparseable model output", ValueError("3 validation errors")),
    ("something nobody anticipated", RuntimeError("?")),
):
    r, before = with_failing("read_shelf", exc)
    check(f"read_shelf / {label}: returns a page", r.status_code == 500,
          f"status {r.status_code}")
    body = r.text
    check(f"read_shelf / {label}: no stack trace", "Traceback" not in body)
    check(f"read_shelf / {label}: no exception text",
          str(exc) not in body, "the raw exception message reached the page")
    check(f"read_shelf / {label}: says something useful",
          "failed partway through" in body)
    check(f"read_shelf / {label}: no temp dir left behind",
          not (temp_dirs() - before), f"leaked {temp_dirs() - before}")

# --- the narrator dies after the engine has already decided ----------
#
# The interesting one. By this point the audit exists and is correct;
# only the prose is missing. Falling over loses work that was already
# done and already paid for.
r, before = with_failing("explain_audit", RuntimeError("narrator fell over"))
check("explain_audit: the audit survives it", r.status_code == 200,
      f"status {r.status_code} — the engine had already decided everything")
check("explain_audit: no stack trace", "Traceback" not in r.text)
check("explain_audit: no temp dir left behind", not (temp_dirs() - before))
check("explain_audit: the findings are still shown",
      "SKA-" in r.text or "Nothing to fix" in r.text)
check("explain_audit: the reader is told the prose is missing",
      "could not be generated" in r.text)

# --- nothing to audit at all ------------------------------------------
r = client.post("/audit", data={"typed": ""})
check("empty submission: not a 500", r.status_code != 500, f"status {r.status_code}")
check("empty submission: no stack trace", "Traceback" not in r.text)

# --- a file that is not an image --------------------------------------
r = client.post(
    "/audit",
    files={"photos": ("notes.txt", b"this is not a photograph", "text/plain")},
)
check("non-image upload: not a 500", r.status_code != 500, f"status {r.status_code}")
check("non-image upload: no stack trace", "Traceback" not in r.text)

# --- the landing page still works -------------------------------------
r = client.get("/")
check("landing page", r.status_code == 200)
check("health", client.get("/health").status_code == 200)

for p in temp_dirs():
    shutil.rmtree(p, ignore_errors=True)

if failures:
    print(f"FAILED {len(failures)} of {checks} checks\n")
    for f in failures:
        print(f"  {f}")
    raise SystemExit(1)

print(f"ok  {checks} checks passed")
print("    every agent failing in turn gives a sentence, not a stack trace,")
print("    and leaves no temp directory behind")
