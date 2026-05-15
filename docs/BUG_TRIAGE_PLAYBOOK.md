# TrainPlex Studio — Bug Triage Playbook

**Owner:** Claude (executor), Founder (decision-maker on priority).

**Purpose:** every bug that hits production walks through this funnel.
The output is always (a) a root-cause fix, (b) a regression test, and
(c) an `INCIDENT_LOG.md` entry. No symptom patches. No "we'll fix it
later". Per founder rule (`feedback_one_shot_root_fix.md`).

---

## Funnel

```
   Report             Reproduce            Diagnose
  (WA, Sentry,        (in dev)           (one root cause)
   trainer ack)
      │                 │                    │
      ▼                 ▼                    ▼
  → Severity  →    Repro recipe   →    Root-cause line
                                              │
                                              ▼
                                        Fix on branch
                                              │
                                              ▼
                                  Regression test added
                                              │
                                              ▼
                                  Verify on staging
                                              │
                                              ▼
                                  Ship to prod
                                              │
                                              ▼
                                  INCIDENT_LOG.md append
```

Every node has a definition-of-done. If you can't tick the box, you
haven't finished that step.

---

## Severity ladder

| Severity | Definition | Response time | Example |
|----------|------------|---------------|---------|
| **SEV-1** | Platform-wide outage or data loss | < 15 min | Login broken for all trainers |
| **SEV-2** | Major feature broken | < 1 hour | Submit fails for >10% of trainers |
| **SEV-3** | Workaround exists, customer impact | < 1 day | Dashboard count off by 1 |
| **SEV-4** | Cosmetic, no business impact | next sprint | Hindi label truncated on iPhone SE |

If unsure → escalate one level. Cost of being wrong on SEV-3-vs-SEV-2
is one phone call; cost of being wrong on SEV-2-vs-SEV-1 is downtime.

---

## Reproduce (definition of done)

* You can paste a sequence of HTTP requests OR a Playwright spec OR a
  pytest snippet that demonstrates the bug **on a clean dev container**.
* The repro lives in a branch (`bug/<sev>-<one-word>`) so it survives
  a Claude session restart.
* The repro does NOT depend on prod data. If it does, you've found a
  symptom, not a cause.

---

## Diagnose (definition of done)

A single sentence in this format:

> "Bug: <one-line symptom>.
> Root cause: <one specific line of code / config / data>.
> Why now: <what changed; usually a recent commit, deploy, or load event>."

Example:

> "Bug: Trainers in MH see 0 tasks in their batch.
> Root cause: `_TRAINER_ROSTER` in `core/services/bulk_assign.py:42`
> uses `state='MAH'` not `'MH'`, so the filter drops them silently.
> Why now: Phase 1 ships mock data; MH trainers never showed up until
> the demo on 2026-05-14 with real trainers."

If your diagnosis has "or" / "and possibly" in it → keep digging. The
fix lands only when there's ONE clear root cause.

---

## Fix (definition of done)

* The fix touches the **root cause line**, not a downstream symptom.
* The fix does not add a feature flag to hide the bug (that's a
  symptom patch).
* The fix's diff is < 50 lines unless the root cause is genuinely a
  refactor.
* No `// TODO: fix properly` comments. The fix IS the proper fix.

---

## Regression test (definition of done)

* New pytest case (preferred) or Playwright spec.
* Without the fix applied, the test **fails**.
* With the fix applied, the test **passes**.
* The test is fast (< 5s pytest, < 30s Playwright).
* The test name + docstring describe the bug in plain words, e.g.

```python
def test_mh_trainers_show_up_in_filter_when_state_is_two_letter_code():
    """Regression: bulk-assign filter used 'MAH' instead of 'MH' so all
    Maharashtra trainers were silently dropped from the result set.
    Fixed 2026-05-15 in core/services/bulk_assign.py."""
```

The docstring is the ONLY documentation the next debugger sees when
they grep for "MH" three months from now.

---

## Verify on staging (definition of done)

* The fix is merged + deployed to staging.
* You manually reproduce the original symptom on staging → no longer
  reproducible.
* Sentry shows the issue auto-resolved (matching error fingerprint
  count went to 0).
* Load test suite (`loadtest/k6/scenarios/full_workflow.js`) still
  passes — the fix didn't regress an unrelated path.

---

## Ship to prod (definition of done)

* Founder approves (WA reply `SHIP` on the PR link).
* Merge to `main` triggers `deploy-prod.yml`.
* Health endpoint returns ok after deploy.
* The original reporter (founder, trainer via WA, Sentry) is notified
  the fix is live.

---

## INCIDENT_LOG.md entry (definition of done)

```
## 2026-05-15T18:23:00Z — BUG_FIX_RELEASED
* severity: SEV-2
* report: trainer Geeta in WA "0 tasks dikh rahe hain"
* root cause: state='MAH' not 'MH' in _TRAINER_ROSTER
* fix sha: a1b2c3d
* regression test: test_mh_trainers_show_up_in_filter_when_state_is_two_letter_code
* verified by: founder login as Geeta on staging
```

Plus the 3-line Hindi recap (founder rule
`feedback_bug_fix_plain_explanation.md`).

---

## Anti-patterns (what NOT to do)

* **Don't** retry the same failing command in a sleep loop. Diagnose
  the root cause (memory rule).
* **Don't** add a feature flag to "hide" the bug from one cohort.
  That makes future debugging harder.
* **Don't** ship a fix without a regression test — guaranteed return
  in 6 months.
* **Don't** patch the symptom in 3 places. There is ONE root cause;
  find it.

---

## 3-line Hindi recap for founder

* **Kya bug tha:** Bug ane pe har baar alag-alag tarike se handle hote the — kabhi feature flag se hide, kabhi sirf log-level pe band, kabhi regression test bina ship. Founder rule (`feedback_one_shot_root_fix.md`) systematically follow nahi ho raha tha.
* **Usse kya ho rha tha:** Same bug 3-3 baar wapas aate the, kyunki root cause vs symptom ka structured distinction nahi tha. Severity classification ad-hoc tha; SEV-2 jaise treatment SEV-1 ko milta tha + vice versa.
* **Ab fix ke baad kya hoga:** `BUG_TRIAGE_PLAYBOOK.md` ek single funnel define karta hai — Report → Reproduce → Diagnose (root cause ek hi line me) → Fix → Regression test (without-fix-fails, with-fix-passes) → Staging verify → Prod ship → Incident log. Har step ke "definition of done" clear hain. SEV-1 to SEV-4 ladder + 4 anti-patterns explicit listed. Founder bina socke ek bug ka complete journey trace kar sakta hai.
