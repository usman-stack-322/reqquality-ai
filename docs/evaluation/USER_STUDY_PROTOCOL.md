# ReqQuality AI — WBS 3.5.4 Controlled Evaluation User Study Protocol

## 1. Study Objective & Scope

This protocol implements the human-centered evaluation component of **WBS 3.5.4 (Controlled Evaluation Study)** from the ReqQuality AI FYP proposal ([`docs/FYP_PROPOSAL_2026-11-04.md`](../FYP_PROPOSAL_2026-11-04.md)).

- **Cohort Size**: `N = 5–10` participants (software engineering students, QA engineers, or developers unfamiliar with the internal implementation).
- **Session Duration**: `15 minutes` per participant (individual moderated session; one facilitator + one participant).
- **Workflow Coverage**: End-to-end human-in-the-loop **Analyst authoring → AI analysis & `value_safety` review → SQA Reviewer case revision, independent approval, & report export**.
- **Ethics & Anonymization**: Participants receive anonymous study IDs (`P01`–`P10`). Sessions run strictly against an isolated synthetic demo database ([`backend/prepare_demo.py`](../../backend/prepare_demo.py) + [`backend/run_demo.py`](../../backend/run_demo.py)), never against production records or real credentials.

---

## 2. Facilitator Testbed Checklist

1. Start an isolated local backend and frontend instance:
   ```powershell
   backend\.venv\Scripts\python.exe backend\prepare_demo.py
   backend\.venv\Scripts\python.exe backend\run_demo.py
   ```
   ```powershell
   Set-Location frontend
   npm.cmd run dev -- --host 127.0.0.1 --port 5174 --strictPort
   ```
2. Open an incognito browser window to `http://127.0.0.1:5174/#home`.
3. Keep synthetic Analyst and SQA Reviewer credentials from `backend/instance/verified-demo/credentials.txt` privately ready for copy-paste without recording credentials on screen.
4. Prepare a stopwatch / timer and blank observation sheet matching Section 5 templates below.

---

## 3. Structured 15-Minute Analyst vs. SQA Reviewer Task Script

### Phase 0: Orientation & Consent (00:00 – 02:00)

- Read brief overview:
  > *"ReqQuality AI assists Requirements Analysts and SQA Engineers in refining software requirements and test cases while keeping humans accountable for every approval. You will complete realistic tasks in both roles over the next 10 minutes, followed by a short 10-item usability survey. Please think aloud as you work; we are evaluating the tool, not you."*
- Confirm verbal consent and record participant background (role experience in years).

### Phase 1: Analyst Role Tasks (02:00 – 07:00)

| Task ID | Participant Prompt & Observable Completion Criteria | Target Window |
| --- | --- | --- |
| **T1** | **Sign in & Create Ambiguous Requirement**: Sign in with the **Analyst** account. Open **New Requirement** (`#requirements`) and create a draft titled *"Export Audit Log"* with an intentionally underspecified description (e.g., *"Administrators should export filtered audit logs quickly for compliance review."*). Click **Analyze with AI**. **Pass**: Analysis completes or retries cleanly and displays structured findings. | 2.0 min |
| **T2** | **Inspect AI Diff, Ambiguities & `value_safety` Warnings**: Inspect the side-by-side **Original Requirement** vs. **Proposed Improvement**, identify any `[TO BE CONFIRMED: ...]` placeholders or **Introduced Values / Needs Confirmation** badges, edit one acceptance criterion to reflect human clarification, tick the review acknowledgment, and save the requirement. **Pass**: Original immutable requirement text remains unchanged; draft saves as `Draft`. | 2.0 min |
| **T3** | **Submit to SQA Queue & Verify Role Boundary**: Submit the requirement (`Ready for Review`) and check whether the **Analyst** account can approve its own requirement or SQA test cases. **Pass**: Requirement enters SQA Review Queue; self-approval is absent/blocked on the interface (`403` enforced server-side). Log out. | 1.0 min |

### Phase 2: SQA Reviewer Role Tasks (07:00 – 12:00)

| Task ID | Participant Prompt & Observable Completion Criteria | Target Window |
| --- | --- | --- |
| **T4** | **Review Queue & Traceability Inspection**: Sign in with the **SQA Engineer** account. Open the submitted *"Export Audit Log"* requirement from **Review Queue**. Use the top **Traceability Stepper** (`Draft → AI Analyzed → Pending SQA → Approved → Executed`) and tabs to verify acceptance criteria links (`AC-001`, …) and current test cases. **Pass**: Reviewer locates linked criteria and unapproved test cases cleanly. | 1.5 min |
| **T5** | **AI Review Assistant Revision & Separate Case Approval**: On the **Test Cases** tab, trigger **Request AI Revision** on one generated test case with feedback (e.g., *"Clarify preconditions and expected empty-result behavior without inventing row limits."*). Inspect the **Old vs. Proposed** comparison and click **Accept as Pending Review** (saving as `Pending Review`), then transition and approve that test case via SQA Case Review. **Pass**: Revised case enters `Pending Review` first before separate approval. | 2.0 min |
| **T6** | **Requirement Approval & Report Export**: Complete the SQA Requirement Review decision (`In Review` → `Approved`) with brief reviewer notes, then download both the requirement **PDF** and **CSV** reports. **Pass**: Traceability status updates cleanly and PDF/CSV downloads open without errors. | 1.5 min |

### Phase 3: SUS Survey & Debrief (12:00 – 15:00)

- Ask participant to complete the **10-question System Usability Scale (SUS)** immediately without overthinking each rating (Section 4).
- Ask 3 brief debrief questions (max 1 minute):
  1. *Which visual cue or workflow step made it clearest what AI suggested vs. what humans confirmed?*
  2. *Where, if anywhere, did you hesitate between Analyst and SQA Reviewer responsibilities?*
  3. *What is the single highest-impact improvement you would make for daily QA use?*

---

## 4. System Usability Scale (SUS) Questionnaire & Scoring

Rate each statement from **1 (Strongly Disagree)** to **5 (Strongly Agree)**:

| # | Statement | Scale (1 = Strongly Disagree … 5 = Strongly Agree) |
| --- | --- | --- |
| **Q1** | I think that I would like to use ReqQuality AI frequently in my requirements and QA workflow. | `1` · `2` · `3` · `4` · `5` |
| **Q2** | I found ReqQuality AI unnecessarily complex. | `1` · `2` · `3` · `4` · `5` |
| **Q3** | I thought ReqQuality AI was easy to use. | `1` · `2` · `3` · `4` · `5` |
| **Q4** | I think that I would need the support of a technical person to be able to use ReqQuality AI. | `1` · `2` · `3` · `4` · `5` |
| **Q5** | I found the various functions in ReqQuality AI (AI analysis, Review Assistant, traceability, exports) were well integrated. | `1` · `2` · `3` · `4` · `5` |
| **Q6** | I thought there was too much inconsistency in ReqQuality AI. | `1` · `2` · `3` · `4` · `5` |
| **Q7** | I would imagine that most people would learn to use ReqQuality AI very quickly. | `1` · `2` · `3` · `4` · `5` |
| **Q8** | I found ReqQuality AI very cumbersome to use. | `1` · `2` · `3` · `4` · `5` |
| **Q9** | I felt very confident using ReqQuality AI to review AI proposals without losing original requirements. | `1` · `2` · `3` · `4` · `5` |
| **Q10** | I needed to learn a lot of things before I could get going with ReqQuality AI. | `1` · `2` · `3` · `4` · `5` |

### Scoring Formula (Brooke, 1996)

For each participant:
- **Odd-numbered items** ($i \in \{1, 3, 5, 7, 9\}$):
  $$\text{contribution}_i = x_i - 1$$
- **Even-numbered items** ($i \in \{2, 4, 6, 8, 10\}$):
  $$\text{contribution}_i = 5 - x_i$$
- **Composite SUS Score** ($0$–$100$ scale):
  $$\text{SUS} = 2.5 \times \sum_{i=1}^{10} \text{contribution}_i$$

| SUS Score Range | Acceptability / Benchmark Interpretation |
| --- | --- |
| **85 – 100** | Excellent / Best Imaginable (Grade A) |
| **70 – 84** | Acceptable / Good (Grade B–C; above `68` industry average) |
| **51 – 69** | Marginal Usability — Targeted UI improvements recommended |
| **0 – 50** | Unacceptable — Major workflow revision required |

---

## 5. Thesis Results Table Templates

### Table A: Task Completion Rate & Time-on-Task (`N = 5–10`)

| Participant ID | Role Background | T1 Pass/Time | T2 Pass/Time | T3 Pass/Time | T4 Pass/Time | T5 Pass/Time | T6 Pass/Time | Total Errors / Hints |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `P01` | | | | | | | | |
| `P02` | | | | | | | | |
| `P03` | | | | | | | | |
| `P04` | | | | | | | | |
| `P05` | | | | | | | | |
| `P06` *(opt.)* | | | | | | | | |
| `P07` *(opt.)* | | | | | | | | |
| `P08` *(opt.)* | | | | | | | | |
| `P09` *(opt.)* | | | | | | | | |
| `P10` *(opt.)* | | | | | | | | |
| **Summary (Mean / Rate)** | — | | | | | | | |

### Table B: System Usability Scale (SUS) Scores

| Participant | Q1 | Q2 | Q3 | Q4 | Q5 | Q6 | Q7 | Q8 | Q9 | Q10 | Sum (0–40) | **SUS Score (`Sum × 2.5`)** |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `P01` | | | | | | | | | | | | |
| `P02` | | | | | | | | | | | | |
| `P03` | | | | | | | | | | | | |
| `P04` | | | | | | | | | | | | |
| `P05` | | | | | | | | | | | | |
| `P06` *(opt.)* | | | | | | | | | | | | |
| `P07` *(opt.)* | | | | | | | | | | | | |
| `P08` *(opt.)* | | | | | | | | | | | | |
| `P09` *(opt.)* | | | | | | | | | | | | |
| `P10` *(opt.)* | | | | | | | | | | | | |
| **Aggregate Mean ± SD** | — | — | — | — | — | — | — | — | — | — | — | |
| **Median / Min / Max** | — | — | — | — | — | — | — | — | — | — | — | |

### Table C: Qualitative Observations & Usability Findings Log

| Finding ID | Observed Task | Theme (`AI Transparency` / `RBAC Clarity` / `Traceability` / `Exports`) | Participant Notes & Severity (`Minor` / `Moderate` / `Critical`) | Action Taken / Future Work |
| --- | --- | --- | --- | --- |
| `OBS-01` | | | | |
| `OBS-02` | | | | |
| `OBS-03` | | | | |
