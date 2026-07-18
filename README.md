# **Q-sage**
QBF encoder for various 2-player games including Positional games (like hex), Connect4, Breakthrough, Domineering etc.
Generates lifted QBF encodings for finding winning strategies of bounded depth.

## New package (`qsage/`) — rewrite in progress

Smaller modular code for students and future work. See `docs/DESIGN.md` and the backlog in `docs/ISSUES.md`.  
**Priority:** match encoding output (QCIR) first; solvers/UI later.  
Legacy `Q-sage.py` remains the reference encoder until encodings are ported.

```bash
pip install -e ".[dev]"
qsage parse --domain Benchmarks/SAT2023_GDDL/GDDL_models/httt/domain.ig \
            --problem Benchmarks/SAT2023_GDDL/GDDL_models/httt/3x3_9_tic.ig
qsage parse --problem Benchmarks/B-Hex/hein_04_3x3-05.pg
qsage encode --domain Benchmarks/SAT2023_GDDL/GDDL_models/httt/domain.ig \
             --problem Benchmarks/SAT2023_GDDL/GDDL_models/httt/3x3_3_domino.ig \
             -e bwnib --normalize --out /tmp/out.qcir
pytest tests/parse tests/encode -q
```

## Positional Games, lifted Hex encodings:
## Usage:

Generating Hex QBF Instances:

    python3 Q-sage.py -e [pg | cp | eg | ew] --problem ./testcases/Hein-hex-Lifted/hein_04_3x3-05.pg --run 0 --encoding_out [path-to-out-file]

Solving Hex QBF Instances:

    python3 Q-sage.py -e [pg | cp | eg | ew] --problem ./testcases/Hein-hex-Lifted/hein_04_3x3-05.pg --run 2 --encoding_out [path-to-out-file]


help:

    python3 Q-sage.py -h

_Input:_  pg format positional game inputs for Hex like games.

_Output:_  generates a qbf instances that encodes the existence of bounded winning strategy
           or solves hex puzzle and finding winning move if exists.

## Interactive game play:

You can play Hex game with QBF solver using the following command:


    python3 interactive_play.py --problem Benchmarks/B-Hex/hein_04_3x3-05.pg

Sample output:

![smaple_play](https://user-images.githubusercontent.com/37924323/215714804-6fff96c3-21b7-44c1-951f-15587202581f.png)


## Non-Positional Games:
Given a GDDL model (domain+problem) file, one could use the following command to generate the corresponding QBF encoding for existence of winning strategy:
## Usage:
Example: to generate a breakthrough instance:

    python3 Q-sage.py --game_type general -e bwnib --ib_domain Benchmarks/SAT2023_GDDL/GDDL_models/breakthrough/domain.ig --ib_problem Benchmarks/SAT2023_GDDL/GDDL_models/breakthrough/2x4_13.ig --encoding_out [path-to-out-file]

We also provide interactive play for general grid games.
For a demo of interactive validation of a 4x4 httt tic winning strategy:

    python3 general_interactive_play.py


## Dependencies:
For visualization of qcir encoding generated, we use pyvis.network

Install using:

    pip install pyvis

## Author:

    Irfansha Shaik
    Aarhus
