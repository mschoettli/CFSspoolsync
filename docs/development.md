# Development

## Local setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Run app:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8080
```

## Tests

Run:

```bash
pytest -q
```

Test suite includes:
- API smoke tests (public route compatibility)
- Service unit tests (conversion and OCR parsing)

## Code structure

- `app/main.py`: app bootstrap + lifespan.
- `app/routers/`: API route groups.
- `app/schemas/`: request/response models.
- `app/services/`: integration and domain helpers.
- `app/models.py`: ORM entities.
- `app/database.py`: engine/session setup.
- `app/static/`: frontend assets.

## Docstring and comment standard

- Public Python functions/classes/methods must include PEP 257 docstrings.
- Use concise structure with `Args`, `Returns`, `Raises` where applicable.
- Add comments only for non-obvious rationale or constraints.
- Keep repository artifacts in English.

## CI

GitHub Actions:
- `docker.yml`: image build/publish flow.
- `test.yml`: dependency install and pytest execution.
