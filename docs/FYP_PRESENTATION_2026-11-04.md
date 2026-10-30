# Presentation outline — 4 November 2026

**ReqQuality AI: AI-Powered Requirements & Software Quality Engineering Platform**<br>
Supervisor: **Maam Amina Ghulam Rasool**<br>
Muhammad Usman **28104** · Hassaan Majid **27916** · Hassan Shabbir **27915**

Suggested length: 8 minutes plus questions. Adjust to the department's allotted time.

| Slide | Time | Key message |
| --- | --- | --- |
| 1. Title and team | 20 s | Give the confirmed title, supervisor and three members |
| 2. Problem | 45 s | Unclear requirements and disconnected test drafts make review and change tracking difficult |
| 3. Objective and scope | 45 s | Assist Analysts and SQA with reviewable suggestions and linked evidence; retain human judgment |
| 4. Architecture | 45 s | React/Vite → Flask services → explicit SQLite/PostgreSQL; server → Gemini; credentials stay on server |
| 5. Human review workflow | 45 s | Requirement → analysis → scenarios → conversational revision → Pending Review → separate approval → report |
| 6. Prototype demonstration | 3 min | Use the exact script below; distinguish live AI from mocked regression evidence |
| 7. Evaluation plan | 45 s | Human reference judgments, unsupported assumptions, task success and stage timings; no invented accuracy claims |
| 8. Limitations and next steps | 35 s | Provider dependency, human semantic review, single project, current hosted blockers; invite questions |

## Demo script

Use the explicitly isolated demo configuration. Keep credentials in the local ignored
file; do not show the password file, environment files, terminal secrets or personal data.
Before the audience arrives, log in once and export a saved report to check availability
and warm the local renderer. This is rehearsal preparation, not a hosted speed claim.

1. **Analyst login.** Enter the local Analyst credentials once. Say: “This account can
   author requirements. It cannot approve SQA decisions.” Show its next-step guidance.
2. **Add a requirement.** Use: “A registered active user signs in with their valid email
   and password. Successful sign-in opens the user dashboard. Both fields are required;
   empty email or password is rejected without opening the dashboard.” Save the draft.
3. **Analyze.** Request AI analysis. Explain that suggestions do not overwrite the original.
   Inspect the refined text, missing-information questions, criteria, risk and scenarios.
   Save only after reading the proposal. Submit for SQA review.
4. **SQA login.** Log out and sign in with the separate SQA account. Open the requirement.
   Show criterion links and the saved scenario version.
5. **AI Review Assistant.** Choose one current case, click Request AI Revision, and ask:
   “Make this test case title clearer while preserving all steps and expected behavior.”
   Show the selected requirement/case context, saved/proposed comparison and explanation.
   Optional follow-up: “Keep the existing preconditions unchanged.”
6. **Acceptance and approval.** Accept the proposal. Point to Pending Review. Start the
   case review, then approve it separately. Review and approve the requirement through
   the SQA controls. Say: “This is a local human review record, not an automated test run.”
7. **Report.** Export the requirement PDF and CSV. Open the PDF and show the original,
   latest saved case, source links and review evidence. Show manual execution as Not Run
   unless a real observation was separately recorded. Do not label generated scenarios
   or SQA approval as tests passed.

## Startup and rehearsal commands

From the repository root, in PowerShell:

```powershell
# Explicitly separate demo database; preserves existing prepared demo records.
backend/.venv/Scripts/python.exe backend/prepare_demo.py
backend/.venv/Scripts/python.exe backend/run_demo.py
```

In another terminal:

```powershell
cd frontend
npm.cmd run dev -- --host 127.0.0.1 --port 5174 --strictPort
```

Use `http://127.0.0.1:5174`. Read credentials privately from
`backend/instance/verified-demo/credentials.txt`. Do not start the regular backend
against production for rehearsal: normal schema initialization could migrate it.
Do not clear/reseed existing user databases. If port 5174 is already occupied, inspect
the existing demo process instead of killing an unrelated service.

Reproducible disposable-database rehearsal (no production writes):

```powershell
backend/.venv/Scripts/python.exe audit/verify_fyp_flow.py --output audit/fyp-2026-11-04/rehearsal
# Optional: two real Gemini requests using synthetic data and provider quota.
backend/.venv/Scripts/python.exe audit/verify_fyp_flow.py --live --output audit/fyp-2026-11-04/rehearsal-live
```

## Failure fallback and honest answers

- If Gemini is unavailable, show the error/retry and preserved input. Then use previously
  saved, clearly identified evidence. Do not pretend a saved or mocked response is live.
- If hosted PostgreSQL remains unreachable, demonstrate the explicitly configured SQLite
  local prototype and state that hosted database-backed login is not verified.
- Use the working `www` domain only after checking it again; the bare domain failed DNS
  in this environment on 30 October. No DNS or hosting changes were authorized.
- If asked “Does it test our application?”, answer: “It generates and manages cases;
  execution evidence is recorded manually. It does not automatically execute the target.”
- If asked “Is coverage complete?”, answer: “Links and AI advice help review coverage;
  they do not establish exhaustive behavioral coverage.”
- If asked about evaluation results, describe the reproducible prototype checks and then
  the planned human evaluation. No research accuracy or productivity result is claimed.
- Do not claim multi-tenancy, successful production migration, confirmed email delivery,
  supervisor/committee approval, or completed future work.
