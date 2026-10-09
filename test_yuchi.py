#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""玉尺工具测试（stdlib unittest，零依赖）。

运行：python3 -m unittest test_yuchi -v
覆盖：文本长度保护、误伤词回归、引文剥离、诗/词/联三模式、边界输入。
"""
import os
import tempfile
import unittest

import yuchi


def _tmp(text):
    f = tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8")
    f.write(text)
    f.close()
    return f.name


class TestProse(unittest.TestCase):
    def test_empty_analyze_does_not_crash(self):
        r = yuchi.analyze("")
        self.assertIsInstance(r["score"], int)

    def test_too_short_render_hint(self):
        p = _tmp("短。")
        try:
            self.assertIn("太短", yuchi.render(p, "短"))
        finally:
            os.unlink(p)

    def test_vague_minutes_regression(self):
        # “十分钟”里的“十分”不算虚词（跨词误匹配回归）
        r = yuchi.analyze("我等了十分钟。雨还在下，一只猫从墙头走过，尾巴扫过瓦片。"
                          "后来风起了，灯晃了一下，屋子里的纸页哗哗地响，"
                          "他坐着没动。")
        self.assertEqual(r["vague_total"], 0)

    def test_quote_strip(self):
        # 引号里的套话不计入作者口吻
        a = yuchi.analyze("他说“值得注意的是，综上所述”。雨停了，院子里只剩水滴的声音。")
        self.assertEqual(a["glue_hits"], [])

    def test_good_prose_scores_high(self):
        r = yuchi.analyze("林子里安静。鸟叫了一声，又没了。他坐着，看光从叶缝里落下来，"
                          "一点点挪过脚背。后来起了风。他站起来，把帽子扣上，走了。")
        self.assertGreaterEqual(r["score"], 60)


class TestPoem(unittest.TestCase):
    def test_flat_block_detected(self):
        r = yuchi.analyze_poem("春天的风轻轻吹过大地\n夏天的大地充满了生机\n"
                               "秋天的天空飘着白云朵\n冬天的白雪覆盖了世界")
        self.assertGreaterEqual(r["flat_run"], 3)
        self.assertTrue(any("豆腐块" in i for i in r["issues"]))

    def test_breathing_poem_clean(self):
        r = yuchi.analyze_poem("雨停在半空\n瓦片亮了一下\n巷子深处的猫叫，拖得很长\n\n"
                               "我把伞收起来\n又撑开\n像一句没说出口的话")
        self.assertFalse(any("豆腐块" in i for i in r["issues"]))


class TestRegulatedAndCiLian(unittest.TestCase):
    def test_regulated_detection(self):
        self.assertTrue(yuchi.is_regulated([7, 7, 7, 7]))
        self.assertTrue(yuchi.is_regulated([5, 5, 5, 5, 5, 5, 5, 5]))
        self.assertFalse(yuchi.is_regulated([5, 7, 7, 7]))
        self.assertFalse(yuchi.is_regulated([7, 7, 7]))

    def test_ci_spec_lookup(self):
        out = yuchi.render_ci("", "测", "忆江南")
        self.assertIn("忆江南", out)
        self.assertIn("平中仄", out)  # 谱首行

    def test_lian_rules(self):
        p = _tmp("雨过山村添翠色\n风来竹院送清声\n")
        try:
            out = yuchi.render_lian(p, "测")
            self.assertIn("仄起平收", out)
            self.assertIn("合格", out)
        finally:
            os.unlink(p)


if __name__ == "__main__":
    unittest.main()
