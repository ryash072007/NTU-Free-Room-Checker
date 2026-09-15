# Room location catalog

The location browser adds a classification layer over canonical timetable room identifiers. It does not rename, trim, or otherwise normalize those identifiers. Unknown codes stay unmapped.

"Anywhere on campus" is a browsing scope, not a catalog location. It uses the global physical-room availability query and intentionally includes unmapped rooms without classifying them.

## Evidence and supported locations

NTU's official [Facility Location and Capacity list](https://wis.ntu.edu.sg/pls/webexe88/FBSDOCU.FBSLOCATN) is the primary source. It groups facilities by spine/building and supplies their physical addresses.

| ID | Display name | Official name / aliases | Rules |
| --- | --- | --- | --- |
| `the-arc` | The Arc | Learning Hub North, LHN | anchored `LHN-` prefix |
| `north-spine` | North Spine | NS | explicit `LT1`–`LT20` variants and the listed `TR+1`–`TR+37` subsets; `TRX43`, `TRX44`, `TCT-LT` |
| `the-hive` | The Hive | Learning Hub South, LHS | anchored `LHS-` prefix |
| `south-spine` | South Spine | SS | explicit `LT22`–`LT29` and the listed `TR+61`–`TR+166` subsets; `LKC-LT`, `TR102`, `TR103`, `TR120`, `TR121` |

The same official list places `TR+17` under **North Spine** at `NS4-05-95`, but places `LHN-TR+17` under **The Arc** at `LHN-L1-05`. An official NTU event listing also describes [LHN-TR+08 as The Arc – Learning Hub North](https://www.ntu.edu.sg/computing/news-events/events/detail/2021/11/22/default-calendar/scse-computing-challenge-2022). Another official NTU page gives the location as [The Arc–Learning Hub North (LHN)](https://www.ntu.edu.sg/innovates/innovationport). These establish both the meaning of LHN and why its prefix is physically significant.

For Learning Hub South, the official facilities list gives `LHS-*` physical addresses followed by “THE HIVE”. NTU also describes an event venue as [The Hive (Learning Hub South – LHS)](https://www.ntu.edu.sg/ncpa/news-events/events/detail/2025/07/18/default-calendar/generative-ai-utility-in-research--opportunities-and-challenges).

## Important distinctions

- `LHN-TR+17` → The Arc; `TR+17` → North Spine. They are never collapsed.
- `LHS-TR+24` → The Hive, even though the facilities directory presents The Hive within its broader South Spine section.
- Plain `TR+` identifiers are assigned only when their exact number appears in NTU's official North/South Spine lists. There is no generic `TR+*` rule.
- Prefix matching is anchored. A code merely containing `LHN` or `LHS` does not match.

## Profile of the AY2026–27 Semester 1 database

The normalized database contains 532 physical-room identifiers. Major families include 43 `LHN-` rooms, 37 `LHS-` rooms (including `LHS-LT`), 57 plain `TR+` rooms, 30 plain `LT` rooms, 49 `NIE*` rooms, 38 `ART-*` rooms, 30 `S4-*` rooms, and 10 `S3-*` rooms. It also contains school-specific families such as `SPMS-*`, `SBS-*`, `SCI-*`, and many isolated lab/studio names.

With the conservative rules above, the real database currently assigns 43 rooms to The Arc, 52 to North Spine, 37 to The Hive, and 53 to South Spine. The remainder stay unmapped.

Ambiguous or deliberately unmapped families include school/building codes (`ART-*`, `ABS-*`, `S3-*`, `S4-*`, `NIE*`, `SPMS-*`, `SBS-*`), generic labs/studios, and malformed source values beginning `//`. A future mapping should add these only with comparable evidence; proximity must not be inferred from a shared substring.
