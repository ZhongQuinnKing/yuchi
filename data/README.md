# 数据来源与许可

本目录的平仄与韵书数据来自开源项目，按其许可使用并注明来源：

- `Word_Tune.json`（汉字平仄，含多音字标注）
- `Pingshui_Rhyme.json`（平水韵）
- `Cilin_Rhyme.json`（词林正韵）

来源：[charlesix59/chinese_word_rhyme](https://github.com/charlesix59/chinese_word_rhyme)，许可 MIT。
数据用于字→平仄与字→韵部的查询；未作改动。
（已知缺口：上游 `Pingshui_Rhyme.json` 上声部缺「三讲」一韵，共 105 韵部；
命令行与网页用同一份数据，行为一致。）

- `Ci_Tunes.json`（词谱：818 词牌，含渊源小记与多体逐字平仄谱，带句读与韵位标记）
- `Ci_Word_Tune.json`（词用字调与词林正韵韵部）

同出 charlesix59/chinese_word_rhyme，MIT。词谱数据已随仓库入库（clone 即用）。

- `Zhongyuan_Yinyun.tsv`（中原音韵原文表，繁体）＋ `Zhongyuan_Rhyme.json`（字→声调/韵部，5347 字，供曲模式）

来源：[nk2028/zhongyuan-data](https://github.com/nk2028/zhongyuan-data)，许可 CC0-1.0（公有领域奉献）。
生成时把用字与韵部名转简体（zhconv）；生成脚本＝`make_zhongyuan_data.py`（读 TSV 可复跑）。
