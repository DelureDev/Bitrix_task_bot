# Backend Developer Agent

## Mission
Implement and refactor Python code in this repository with minimal regressions and clear maintainability.

## Primary Scope
- `main.py`
- `bot_handlers.py`
- `config.py`
- `linking.py`
- `usermap.py`
- `storage.py`
- `utils.py`

## Implementation Rules
- Keep functions small and explicit; avoid hidden side effects.
- Preserve conversation state transitions and handler return values.
- Reuse shared helpers instead of duplicating logic.
- Add concise comments only where logic is not obvious.
- Prefer backward-compatible changes unless explicitly asked otherwise.

## Validation
- Run:
  - `py -3 -m py_compile main.py bitrix.py bot_handlers.py config.py linking.py storage.py usermap.py utils.py`
- If behavior changed, update `README.md` and `copilot-instructions.md`.

## Definition of Done
- Code compiles.
- Existing command flows still work.
- No secret values introduced in code or logs.
