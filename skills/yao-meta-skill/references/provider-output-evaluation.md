# Provider Output Evaluation

The governed provider matrix lives at `evals/output/provider_matrix.json`. It fixes DeepSeek V4 Flash and DeepSeek V4 Pro, non-thinking mode, temperature 0, and 3,000 maximum output tokens. The matrix caps one evaluation at 40 provider calls, 250,000 total tokens, and 60 seconds per call. Only `DEEPSEEK_API_KEY` is read from the environment.

Run the matrix through the trusted evidence entrypoint:

```bash
python3 scripts/yao.py evidence-build . --run-id <run-id> --self
```

When the credential is missing, the run records `external-required` and keeps quality promotion pending. When the credential is present, the run executes 10 frozen cases across two models and two variants. Raw outputs stay under `.yao/runs/<run-id>/raw-outputs`. Committed or published reports contain hashes, provider and model metadata, observed tokens, duration, response identifiers, and a redacted structural summary.

Successful execution creates 20 shuffled A/B pairs and separate templates for Reviewer A, Reviewer B, and Reviewer C. Blind-pack entries use cryptographically random A/B assignments and role-neutral filenames under the run's `review-materials` directory. The role mapping stays in `.yao/runs/<run-id>/private/provider_output_answer_key.json`; the public artifact contains only its SHA-256 commitment. Each reviewer completes all 20 pairs independently through a controlled submission before finalization.

```bash
python3 scripts/yao.py evidence-finalize-review . \
  --source-run <run-id> \
  --decisions <reviewer-a.json> \
  --decisions <reviewer-b.json> \
  --decisions <reviewer-c.json> \
  --reviewer-registry <controlled-registry.json> \
  --run-id <final-run-id> \
  --self \
  --publish
```

If finalization is interrupted after a named run is created, repeat the command with `--resume`. The command verifies the source commit, blind-pack commitment, role-neutral output hashes, reviewer packet hashes, and controlled identity registry before completing the same run.

The reviewer registry binds each registered reviewer identity, controlled submission id, timestamp, and exact packet SHA-256. Quality promotion requires at least 15 with-skill pair wins, at least 7 wins for each model's 10 pairs, zero critical failures, and Fleiss' kappa of at least 0.40. This promotion is internal quality evidence. The world-class ledger stays pending until its independent acceptance process is complete.

Model contract references: [DeepSeek Models & Pricing](https://api-docs.deepseek.com/quick_start/pricing/) and [DeepSeek API Changelog](https://api-docs.deepseek.com/updates/).
