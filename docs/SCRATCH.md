# Encodings location (updated)

The official paper encodings are under **`qsage.encode`**, not `qsage.scratch`.

| API | Encoding | Implementation |
|-----|----------|----------------|
| `qsage.encode.encode_bwnib` | bwnib (grid) | `qsage.encode.paper` |
| `qsage.encode.encode_positional(..., "pg")` | path-based Hex | `qsage.encode.paper` |
| `encode_positional(..., "cp"\|"ibign")` | other Hex | still `legacy/` until ported |

`qsage.scratch` only re-exports the official API for old imports.

`legacy/` remains in the tree for reference / regenerating goldens / `cp`+`ibign`.
