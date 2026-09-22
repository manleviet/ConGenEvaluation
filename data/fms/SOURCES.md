# Provenance of the feature models in `data/fms/`

The paper's evaluation uses five configuration knowledge bases **derived from real-world feature
models published on UVLHub**, the open feature-model data repository:

> Romero-Organvidez, Galindo, Sundermann, Horcas and Benavides.
> *UVLHub: A feature model data repository using UVL and open science principles.*
> Journal of Systems and Software 216 (2024) 112150. <https://doi.org/10.1016/j.jss.2024.112150>

All files are in **UVL** (Universal Variability Language) and are parsed by flamapy's UVL reader.

| file | paper label | features | cross-tree constraints | used in the paper |
|---|---|---|---|---|
| `REAL-FM-7.uvl` | KB_1 | 14 | 2 | yes |
| `fqa.uvl` | KB_2 | 179 | 9 | yes |
| `arcade-game.uvl` | KB_3 | 65 | 34 | yes |
| `REAL-FM-4.uvl` | KB_4 | 291 | 21 | yes |
| `busybox-1.18.0.uvl` | KB_5 | 854 | 67 | yes |
| `ea2468.uvl` | — | 1,408 | 1,281 | no — scalability discussion only |
| `linux-2.6.33.3.uvl` | — | 6,467 | 7,650 | no — scalability discussion only |

Feature and constraint counts are reproduced from `README.md` in this directory; the paper's
`|C_tau|` and `|B|` figures are computed by the pipeline from these files, not transcribed.

## What this file does and does not establish

It records the **collection** the models come from and the state in which they are shipped here. It
does **not** record a per-file retrieval date or a UVLHub record identifier: those were not captured
when the models were added to the repository, and this file will not invent them. A reader who needs
to match a specific file against its UVLHub record should search UVLHub by the file name, which was
preserved unchanged.

`ea2468.uvl` and `linux-2.6.33.3.uvl` are kept because the repository's scalability notes refer to
them. Neither contributes a **result** to any table: no acquisition run completed on either, and the
evaluation config lists exactly the five knowledge
bases above. `ea2468` does contribute its **bias composition** — n, the hierarchical candidates, k
and `|B| = 2,047,362` — as the last row of the paper's bias-composition table, which is the model on
which the study reached its size limit. Those figures are computed from `ea2468.uvl` and
`data/bias-config/ea2468.yaml` by the same pipeline as every other row.

## Licensing

UVLHub content is published under open-science terms; the individual models carry the licences of
their upstream projects (for example, busybox is GPL-licensed software and its feature model
describes that project's configuration space). No model here has been modified beyond the UVL
conversion in which it was published.
