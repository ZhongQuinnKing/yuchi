#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""玉尺工具测试（stdlib unittest，零依赖）。

运行：python3 -m unittest test_yuchi -v
覆盖：文本长度保护、误伤词回归、引文剥离、诗/词/联三模式、边界输入。
"""
import json
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

    def test_web_copy_hard_wrap_merged(self):
        # 网页复制来的硬换行（行尾逗号）应与下一行并段
        txt = ("这是一段文字，\n行尾是逗号，\n所以三行该并成一段。\n\n"
               "第二段是完整的一句。\n")
        r = yuchi.analyze(txt)
        self.assertEqual(r["n_para"], 2)

    def test_percentile_bounds(self):
        self.assertGreaterEqual(yuchi.percentile_of(100), 95)
        self.assertLessEqual(yuchi.percentile_of(0), 5)
        self.assertTrue(0 <= yuchi.percentile_of(80) <= 100)

    def test_json_output_parses(self):
        p = _tmp("林子里安静。鸟叫了一声，又没了。他坐着，看光从叶缝里落下来，"
                 "一点点挪过脚背。后来起了风。他站起来，把帽子扣上，走了。")
        try:
            data = json.loads(yuchi.render_json(yuchi.analyze(yuchi.read_text(p))))
            self.assertIn("score", data)
            self.assertIn("percentile", data)
            self.assertIsInstance(data["sentences"], list)
        finally:
            os.unlink(p)

    def test_batch_table(self):
        p1 = _tmp("林子里安静。鸟叫了一声，又没了。他坐着，看光从叶缝里落下来，"
                  "一点点挪过脚背。后来起了风。他站起来，把帽子扣上，走了。")
        p2 = _tmp("他在当今社会中高度重视此项工作的重要性。首先，值得注意。"
                  "其次，综上所述。此外，让我们共同努力。")
        try:
            out = yuchi.render_batch([p1, p2])
            self.assertIn("分数", out)
            self.assertIn("结构", out)
        finally:
            os.unlink(p1)
            os.unlink(p2)

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

    def test_rhyme_after_punctuation(self):
        # 带标点的诗：韵脚取字必须先剥标点（修「取到句号」bug 的回归）
        p = _tmp("雨过山村草木新，\n溪流绕屋水粼粼。\n白云一片松间去，\n留得清凉与路人。\n")
        try:
            out = yuchi.render_poem(p, "诗")
            self.assertIn("第 2 句尾「粼」：十一真", out)
            self.assertIn("第 4 句尾「人」：十一真", out)
            self.assertNotIn("句尾「。」", out)  # 不能把标点当韵脚字
        finally:
            os.unlink(p)


class TestForm(unittest.TestCase):
    def test_structured_form_detected(self):
        # 条目/模板文本：识别为 structured，render 不给散文分
        t = ("一、会议时间\n2026 年 10 月 1 日\n二、参会人员\n张三、李四、王五\n"
             "三、会议内容\n讨论了项目排期与分工。\n四、待办事项\n1. 张三跟进排期\n2. 李四整理纪要")
        r = yuchi.analyze(t)
        self.assertEqual(r["form"], "structured")
        p = _tmp(t)
        try:
            out = yuchi.render(p, "纪要")
            self.assertIn("文体识别", out)
            self.assertNotIn("总评", out)
        finally:
            os.unlink(p)

    def test_prose_form_untouched(self):
        r = yuchi.analyze("雨停在半空。瓦片亮了一下，巷子深处的猫叫拖得很长。"
                          "我把伞收起来，又撑开，像一句没说出口的话。后来天黑了，"
                          "灯一盏一盏亮起来，风从窗缝里挤进来。")
        self.assertEqual(r["form"], "prose")


class TestQu(unittest.TestCase):
    def test_qu_rhyme_one_tune(self):
        # 《天净沙·秋思》五句全押家麻；北曲一韵到底（曲模式回归）
        p = _tmp("枯藤老树昏鸦\n小桥流水人家\n古道西风瘦马\n夕阳西下\n断肠人在天涯\n")
        try:
            out = yuchi.render_qu(p, "曲")
            self.assertIn("第 1 句尾「鸦」：家麻", out)
            self.assertIn("第 5 句尾「涯」：家麻", out)
            self.assertIn("一韵到底", out)
        finally:
            os.unlink(p)

    def test_qu_tone_zhongyuan(self):
        # 声调按中原音韵：阴/阳/上/去；入声字按派入的声显示（北曲用法）；多音＝通
        self.assertEqual(yuchi.qu_tone_of("鸦")[0], "阴")
        self.assertEqual(yuchi.qu_tone_of("马")[0], "上")
        self.assertEqual(yuchi.qu_tone_of("雪")[0], "上")   # 入作上
        self.assertEqual(yuchi.qu_tone_of("月")[0], "去")   # 入作去
        self.assertEqual(yuchi.qu_tone_of("说")[0], "通")   # 多音


class TestFuAndHtml(unittest.TestCase):
    def test_fu_report(self):
        # 《前赤壁赋》风格节选：骈句报数与句末韵部（赋模式回归）
        t = "壬戌之秋\n七月既望\n苏子与客泛舟游于赤壁之下\n清风徐来\n水波不兴\n"
        p = _tmp(t)
        try:
            out = yuchi.render_fu(p, "赋")
            self.assertIn("骈句报数", out)
            self.assertIn("四字句", out)
            self.assertIn("第 1 句尾「秋」：十一尤", out)
            self.assertIn("不装懂", out)
        finally:
            os.unlink(p)

    def test_html_report_prose(self):
        t = ("雨停在半空。瓦片亮了一下，巷子深处的猫叫拖得很长。我把伞收起来，又撑开，"
             "像一句没说出口的话。后来天黑了，灯一盏一盏亮起来，风从窗缝里挤进来。"
             "我坐了许久，听着檐下滴水，一滴，又一滴。")
        r = yuchi.analyze(t)
        h = yuchi.render_html(r, "测试")
        self.assertIn("<!DOCTYPE html>", h)
        self.assertIn("</html>", h)
        self.assertIn("玉尺 · 文气诊断", h)
        self.assertIn(str(r["score"]), h)

    def test_html_report_structured(self):
        t = ("一、会议时间\n2026 年 10 月 1 日\n二、参会人员\n张三、李四\n"
             "三、会议内容\n讨论了排期与分工。\n四、待办\n1. 跟进排期\n2. 整理纪要")
        r = yuchi.analyze(t)
        h = yuchi.render_html(r, "纪要")
        self.assertIn("文体识别", h)


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
