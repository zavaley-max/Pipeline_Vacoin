# Commands

Run these tools explicitly from the root of the project. Python 3.10+ is required.

```bash
python pipeline/scripts/pipeline.py doctor --root .
python pipeline/scripts/pipeline.py validate --root . --manifest "/external/evidence/scope.json"
python pipeline/scripts/pipeline.py snapshot --root . --manifest "/external/evidence/scope.json" --output "/external/evidence/baseline.json"
python pipeline/scripts/pipeline.py scope --root . --manifest "/external/evidence/scope.json" --baseline "/external/evidence/baseline.json"
python pipeline/scripts/pipeline.py run-check --root . --manifest "/external/evidence/scope.json" --check targeted --lane minimal --output "/external/evidence/targeted.json"
python pipeline/scripts/pipeline.py check-receipt --root . --manifest "/external/evidence/scope.json" --check targeted --lane minimal --receipt "/external/evidence/targeted.json"
python pipeline/improvement/lab.py --help
python pipeline/improvement/runner.py --help
```

Paths are illustrative and must be replaced. Use the exact CLI `--help` for additional options. Commands do not automatically install hooks, execute production workloads, publish changes or merge branches.
