# H2v3 data

Канонические маленькие файлы появляются после `bash bin/copy-from-v2.sh`:

| file | role |
|---|---|
| `d0_slice.jsonl` | 60 query, замороженный срез D0 |
| `gold_useful.jsonl` | agent-labeled useful-списки, NOT human gold |
| `gold_useful.manifest.json` | манифест разметчика D0 |

Крупный корпус ABCD — `bash bin/sync_h1_data.sh` из
`standalone/h1-experience-cards/data/`. В git не дублируем.

Сборка 320+60: `python3 bin/build_phase_c_inputs.py`
(скрипт появится после copy-from-v2).

Не золото H2 и не вход тегера/судьи: `unlock`, `unlock_guideline`.
