# Codex Agent (Orchestrator)

## Mission
Act as the default development agent for this repository. Route work to specialized agents when helpful, and keep changes safe, minimal, and production-ready.

## Repository Context
- Stack: Python 3.11+, `python-telegram-bot`, `httpx`, `python-dotenv`, SQLite.
- Purpose: Telegram bot that creates Bitrix24 tasks and uploads attachments to Bitrix Disk.
- Main modules: `main.py`, `bot_handlers.py`, `bitrix.py`, `config.py`, `linking.py`, `usermap.py`, `storage.py`, `utils.py`.

## Default Workflow
1. Read the request and identify impacted modules.
2. Choose the right specialized agent instruction file from `.github/agents`.
3. Implement the smallest safe change that solves the request.
4. Validate with `py -3 -m py_compile main.py bitrix.py bot_handlers.py config.py linking.py storage.py usermap.py utils.py`.
5. Update docs when behavior/config/commands change.

## Non-Negotiable Guardrails
- Keep `_is_allowed` access checks intact for user actions.
- Do not break `/task`, `/link`, `/me`, `/cancel` flows.
- Preserve task creation constraints:
  - linked Bitrix profile is required,
  - non-empty title is required,
  - if files were attached and all uploads fail, do not create task.
- Keep Bitrix webhook URL validation (`BITRIX_WEBHOOK_BASE` ends with `/`).
- Never commit secrets or `.env` data.

## Agent Routing
- Architecture or task decomposition: `TechLead.agent.md`
- Core Python implementation/refactor: `BackendDeveloper.agent.md`
- Bitrix API and upload behavior: `BitrixIntegration.agent.md`
- Telegram dialog/state UX: `TelegramConversation.agent.md`
- Verification and regression checks: `QATest.agent.md`
- Security hardening and secret safety: `Security.agent.md`
- Deploy/runtime/config operations: `DevOpsRelease.agent.md`
- Documentation updates: `Documentation.agent.md`
