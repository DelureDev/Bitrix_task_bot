# Bitrix Integration Agent

## Mission
Own reliability and correctness of Bitrix24 REST integration, especially task creation and file upload flows.

## Primary Scope
- `bitrix.py`
- Bitrix-related sections in `bot_handlers.py`
- Bitrix config in `config.py`

## Integration Rules
- Keep `BitrixError` usage consistent and actionable.
- Preserve two-stage upload strategy:
  1. `fileContent`
  2. `uploadUrl` fallback
- Maintain `UF_TASK_WEBDAV_FILES` format as `n<file_id>`.
- Keep CREATED_BY fallback behavior for task creation.
- Do not silently swallow API errors; surface enough detail for debugging.

## Reliability Checklist
1. Validate required payload fields before API calls.
2. Keep timeout behavior explicit for normal vs upload paths.
3. Ensure malformed Bitrix responses are handled safely.
4. Preserve partial upload behavior messaging.

## Done Criteria
- Bitrix contract remains compatible.
- Upload and create-task failure paths are deterministic.
