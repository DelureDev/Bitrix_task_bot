# Workflow Guide: Agents and Skills

This file explains how to work in this repository using the agent files in `.github/agents` and installed Codex skills.

## 1) Default Working Loop

1. Define the task clearly:
   - Goal
   - Constraints
   - Affected files
   - Definition of done
2. Start with `Codex.agent.md` as orchestrator.
3. Route to one or more specialized agents only when needed.
4. Implement the smallest safe change.
5. Validate (`py_compile`, behavior check).
6. Update docs if behavior/config changed.

Recommended validation command:

```powershell
py -3 -m py_compile main.py bitrix.py bot_handlers.py config.py linking.py storage.py usermap.py utils.py
```

## 2) Which Agent To Use

- `Codex.agent.md`: default entry point and routing.
- `TechLead.agent.md`: scope, risks, acceptance criteria, implementation plan.
- `BackendDeveloper.agent.md`: Python implementation and refactoring.
- `BitrixIntegration.agent.md`: Bitrix REST contract, upload strategy, task creation behavior.
- `TelegramConversation.agent.md`: Telegram command/state machine UX and flow safety.
- `QATest.agent.md`: regression checks and behavior validation.
- `Security.agent.md`: security checks (secrets, access control, input handling).
- `DevOpsRelease.agent.md`: environment config and runtime/release readiness.
- `Documentation.agent.md`: sync README/instructions with code behavior.

## 3) Which Skill To Use

Use skills only when the task matches the skill scope.

- `gh-fix-ci`: inspect and fix failing GitHub Actions checks.
- `gh-address-comments`: address open PR review comments.
- `security-best-practices`: explicit secure-coding review request.
- `security-threat-model`: explicit threat-modeling request.
- `create-plan`: when you explicitly want a concise plan.
- `codex-readiness-unit-test`: readiness unit-style report.
- `codex-readiness-integration-test`: end-to-end readiness integration loop.
- `doc`: `.docx` creation/editing tasks.

## 4) Recommended Sequences

### New Feature
1. `TechLead` -> define scope and acceptance criteria.
2. `BackendDeveloper` (+ `BitrixIntegration` or `TelegramConversation` as needed).
3. `QATest`.
4. `Security` (if auth/input/storage/API touched).
5. `Documentation`.

### Bug Fix
1. `BackendDeveloper` (minimal fix).
2. `QATest` (repro + regression).
3. `Documentation` (if user-visible behavior changed).

### Release Readiness
1. `DevOpsRelease`.
2. `QATest`.
3. `Security`.

### Security Review
1. `Security.agent.md`.
2. Skill: `security-best-practices` (or `security-threat-model` if threat modeling is requested).

## 5) Copy-Paste Prompt Templates

### Plan a feature
```text
Use TechLead.agent.md to plan this change:
Goal: <goal>
Constraints: <constraints>
Files likely touched: <files>
Done when: <acceptance criteria>
```

### Implement a backend/API change
```text
Use BackendDeveloper.agent.md and BitrixIntegration.agent.md.
Implement: <feature/fix>
Keep unchanged: <non-goals>
Then run compile validation and summarize file-level changes.
```

### Implement a Telegram flow change
```text
Use BackendDeveloper.agent.md and TelegramConversation.agent.md.
Change command/flow: <details>
Preserve existing /cancel and access control behavior.
Validate state transitions and summarize.
```

### QA pass only
```text
Use QATest.agent.md.
Check regressions for: <areas>
Report findings ordered by severity with file references.
```

### Security pass only
```text
Use Security.agent.md with security-best-practices.
Review changed files for risks and propose minimal mitigations.
```

### CI failure triage
```text
Use gh-fix-ci.
Inspect failing GitHub checks, summarize root cause, propose fix plan, then implement after confirmation.
```

### PR comments cleanup
```text
Use gh-address-comments.
Fetch unresolved PR comments, apply fixes, and summarize what was addressed.
```

## 6) Team Conventions

- Keep changes narrow and reversible.
- Do not commit secrets (`.env`, tokens, webhook keys).
- Preserve critical bot invariants:
  - Access control checks remain in place.
  - Linked Bitrix user required for task creation.
  - Non-empty title required.
  - If files were attached and all uploads fail, do not create task.
- Update docs in the same change when behavior or configuration changes.

