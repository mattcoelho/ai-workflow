# Job scoring feedback loop

The feedback loop keeps daily scoring deterministic while building a human-labeled benchmark for prompt and rule changes.

## Label a job

Find recent Feedback IDs:

```bash
python3 feedback_cli.py list --sent-only --limit 20
```

Attach a label and preserve the job, description, original score, model, and analyzer version:

```bash
python3 feedback_cli.py label 'Company::job-id' strong_match --notes 'Direct support-agent platform fit.'
```

Application outcomes can be recorded separately from fit:

```bash
python3 feedback_cli.py label 'Company::job-id' strong_match --outcome interviewed
```

Use `feedback_cli.py import` for a labeled posting that was not captured by the daily monitor. An imported job remains out of baseline metrics until `evaluate --rescore` gives it a model prediction.

Supported labels:

- `bullseye`: should score 9-10
- `strong_match`: should score 8
- `competitive_match`: should score 7
- `applied`: should score 8-10
- `interviewed`: should score 9-10
- `maybe`: should score 5-6
- `bad_match`: should score 1-4
- `wrong_role`: should score 1-4
- `wrong_location`: should score 1-5
- `ignored`: should score 1-6
- `bad_url`: calibrates URL quality but is excluded from fit evaluation

Labels continue to adjust daily scores through `data/feedback.json`. Saved snapshots remain unchanged, so later scoring changes can be compared against the same examples.

## Evaluate scoring

Generate an offline baseline report with no Gemini calls:

```bash
python3 feedback_cli.py evaluate
```

The report contains:

- Bullseye precision: share of jobs scored 9-10 that have a positive label
- Competitive precision: share scored 7-10 that have a positive label
- Competitive recall: share of positively labeled jobs that scored at least 7
- Range accuracy: share whose score falls inside the expected range for its label

To replay every labeled job through the current Gemini analyzer and compare it with its saved baseline:

```bash
python3 feedback_cli.py evaluate --rescore
```

`--rescore` uses one Gemini call per labeled job that has a saved description. The default command never calls Gemini.
