# Intentional CI break patterns (for your own public test repos)

Create a throwaway public repo and break CI on purpose so you own ground truth:

1. **Broken pin** — set `pydantic==1.10.13` alongside FastAPI 0.115+ → `dependency_conflict`
2. **Missing secret** — reference `${{ secrets.DOES_NOT_EXIST }}` → `misconfiguration`
3. **Flaky sleep race** — assert on shared state without a lock → `flaky_test` (often green on retry)
4. **OOM build** — Node heap tiny + large webpack build → `resource_exhaustion`

After failures appear in Actions, either:
- Point a webhook at your deployed API, or
- `python backend/scripts/fetch_public_failures.py --repos YOU/test-repo --limit 5`
then label cases into `data/eval/ground_truth.json` and re-run `run_eval.py`.
