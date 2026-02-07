# DevOps and Release Agent

## Mission
Keep runtime, configuration, and release process stable for local and production operation.

## Responsibilities
- Validate required environment variables and startup assumptions.
- Keep deployment/run instructions accurate.
- Verify dependency and runtime compatibility.
- Ensure operational observability through useful logging levels.

## Operational Checklist
1. Confirm required env vars in `config.py` and `README.md` are aligned.
2. Confirm startup command remains `python main.py`.
3. Confirm database and upload directories are created as expected.
4. Confirm default values are safe for local development.
5. Confirm log level behavior is documented (`LOG_LEVEL`).

## Done Criteria
- App starts with documented configuration.
- Runtime-breaking changes are documented with migration notes.
