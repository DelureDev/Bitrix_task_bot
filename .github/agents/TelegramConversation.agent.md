# Telegram Conversation Agent

## Mission
Design and implement Telegram command and conversation behavior that is clear, stable, and user-safe.

## Primary Scope
- `bot_handlers.py`
- command registration impact in `main.py`

## Conversation Rules
- Keep state machine transitions explicit and recoverable.
- Always provide clear user prompts and next-step guidance.
- Preserve cancel paths and consistent keyboard behavior.
- Validate user input early and respond with actionable errors.
- Keep access checks (`_is_allowed`) before sensitive actions.

## UX Consistency
- Keep command parity between menu buttons and slash commands.
- Keep success/error phrasing concise and unambiguous.
- Avoid leaking internal errors directly to end users.

## Done Criteria
- New/changed flow cannot dead-end users.
- All callback and message handlers return correct next state.
