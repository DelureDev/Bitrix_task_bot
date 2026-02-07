# Development Agents

This folder defines role-based agents for development tasks in this repository.

## Agent List
- `Codex.agent.md`: Default orchestrator and routing agent.
- `TechLead.agent.md`: Planning, scoping, architecture tradeoffs.
- `BackendDeveloper.agent.md`: Python implementation and refactoring.
- `BitrixIntegration.agent.md`: Bitrix REST contracts and upload reliability.
- `TelegramConversation.agent.md`: Telegram dialogs, states, and UX flow.
- `QATest.agent.md`: Regression checks and validation focus.
- `Security.agent.md`: Secret safety, access control, and hardening checks.
- `DevOpsRelease.agent.md`: Runtime config and release readiness.
- `Documentation.agent.md`: README and instruction sync.

## Recommended Usage
1. Start with `Codex.agent.md`.
2. Route to one specialized agent for implementation.
3. Run `QATest.agent.md` and `Security.agent.md` before merge.
4. Finish with `Documentation.agent.md` if behavior/config changed.
