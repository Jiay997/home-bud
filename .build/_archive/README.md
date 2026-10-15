# _archive — 构建中间产物（已停用，仅保留备查）

2026-10-05 整理时从 `.build/` 移出，**未删除任何文件**。

| 文件 | 与在用品的关系 |
|---|---|
| `_tmp_sc0106.md` | 与 `../frag-sc0106.md` 字节完全相同（MD5 `0AD4C443…`） |
| `_tmp_sc2026.md` | 与 `../frag-sc2026.md` 字节完全相同（MD5 `A56A88A6…`） |
| `_tmp_pa_a.md` | 与 `../frag-pa_a.md` 字节完全相同（MD5 `CD223290…`） |
| `_tmp_pa_b.md` | 与 `../frag-pa_b.md` 字节完全相同（MD5 `D182CD96…`） |
| `_tmp_sc0712.md` | **旧迭代**，已被 `../frag-sc0712.md` 取代（内容不同） |
| `_tmp_sc1319.md` | **旧迭代**，已被 `../frag-sc1319.md` 取代（内容不同） |
| `__pycache__/` | Python 字节码缓存，可随时重新生成 |

`assemble.py` 只读取 `frag-*.md`，不引用本目录，因此在用构建链路不受影响。

> 若需彻底清理，删除本目录即可；需要还原，从 `D:\HomeBud\_backup_before_reorg_20261005.zip` 解压对应文件。
