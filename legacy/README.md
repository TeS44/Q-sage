# Legacy Q-sage tree

This directory holds the **original** Q-sage code (pre-`qsage/` package rewrite).

It is kept for:

- reproducing older scripts and encodings
- the current `bwnib` backend (still calls into `legacy/q_encodings`)
- terminal interactive play scripts

**Prefer** the new CLI from the repo root:

```bash
pip install -e ".[dev]"
qsage parse|encode|solve …
```

## Run legacy tools

From the **repository root** (so `Benchmarks/` and `solvers/` resolve):

```bash
# Encoder
python legacy/Q-sage.py -h

# Hex interactive play
python legacy/interactive_play.py --problem Benchmarks/B-Hex/hein_04_3x3-05.pg

# Certificate / grid interactive play
pip install python-sat
python legacy/general_interactive_play.py
```

Add the legacy tree to `PYTHONPATH` if imports fail:

```bash
# macOS / Linux
export PYTHONPATH="$PWD/legacy${PYTHONPATH:+:$PYTHONPATH}"

# Windows PowerShell
$env:PYTHONPATH = "$PWD\legacy;$env:PYTHONPATH"
```

Do not add new features here; extend `qsage/` instead.
