#!/usr/bin/env python3
# 机构自己的卷入库前检查（docs/31）：一套卷一个 JSON，按我们的试卷格式写；这个脚本只读不改，不联网，只用标准库。
#   python3 -I scripts/bank/check_paper.py <卷.json 或目录> [--img-dir <题图根目录>] [--prefix org1-]
# 有错误退出码 1（不能入库）；只有提醒的可以入库，页面上会照常显示。
# 规则和我们自己入库的检查（scripts/bank/check.ts）一致，另加机构卷的几条：编号前缀、卷的性质（kind）。
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
DICT = json.load(open(os.path.join(ROOT, 'assets', 'kp-dict.json'), encoding='utf-8'))['stages']
TYPES = ('选择', '填空', '解答')
DIFF = ('易', '中', '难')
KINDS = ('真题', '模拟', '练习')
EXAMS = {'中考': '初中', '高考': '高中'}
GRADES = {'初中': ('初一', '初二', '初三'), '高中': ('高一', '高二', '高三')}
SUBJECTS = ('chinese', 'math', 'english', 'physics', 'chemistry', 'biology', 'history', 'geography', 'politics')
ID_RE = re.compile(r'^[a-z0-9]+(-[a-z0-9]+)*$')


def check(p, path, img_dir=None, prefix=None):
    E, W = [], []
    need = ('id', 'exam', 'subject', 'year', 'regions', 'title', 'full', 'kind', 'items')
    miss = [k for k in need if k not in p]
    if miss:
        return ['缺字段：' + '、'.join(miss)], W
    pid = str(p['id'])
    if not ID_RE.match(pid):
        E.append('编号「%s」只能用小写字母、数字和 -' % pid)
    if prefix and not pid.startswith(prefix):
        E.append('编号要以「%s」开头，和我们的卷区分开' % prefix)
    if os.path.splitext(os.path.basename(path))[0] != pid:
        W.append('文件名和编号不一样（文件名应为 %s.json）' % pid)
    if p['exam'] not in EXAMS:
        return E + ['考试「%s」只能是 中考 或 高考' % p['exam']], W
    stage = EXAMS[p['exam']]
    if p['subject'] not in SUBJECTS:
        return E + ['科目「%s」不对，可选：%s' % (p['subject'], '、'.join(SUBJECTS))], W
    if p['kind'] not in KINDS:
        E.append('卷的性质 kind「%s」只能是 %s' % (p['kind'], '、'.join(KINDS)))
    if not (isinstance(p['year'], int) and 2000 <= p['year'] <= 2100):
        E.append('年份不对')
    if not (isinstance(p['regions'], list) and p['regions'] and all(isinstance(r, str) and r for r in p['regions'])):
        E.append('regions 要写地区名的列表，例如 ["成都"]')
    sd = DICT.get(stage, {}).get(p['subject'])
    if not sd:
        return E + ['考点字典里没有 %s %s' % (stage, p['subject'])], W
    mods = set(sd['modules'])
    kps = {k['name'] for k in sd['kps']}
    items = p['items']
    if not isinstance(items, list) or not items:
        return E + ['items 是空的'], W
    full = p['full']
    if not (isinstance(full, (int, float)) and full > 0):
        E.append('满分 full 要大于 0')
    total = 0
    nos = []
    for x in items:
        no = str(x.get('no', ''))
        at = '第 %s 题' % (no or '?')
        if not re.match(r'^\d+$', no):
            E.append('%s 题号要是数字' % at)
        else:
            nos.append(int(no))
        if x.get('type') not in TYPES:
            E.append('%s 题型「%s」只能是 %s' % (at, x.get('type'), '、'.join(TYPES)))
        pts = x.get('points')
        if not (isinstance(pts, (int, float)) and pts > 0):
            E.append('%s 分值要大于 0' % at)
        else:
            total += pts
        if x.get('module') not in mods:
            E.append('%s 模块「%s」不在标准模块表（%s）' % (at, x.get('module'), '、'.join(sd['modules'])))
        ks = x.get('kps') or []
        if not ks:
            E.append('%s 没有考点' % at)
        for k in ks:
            if k not in kps:
                E.append('%s 考点「%s」不在字典（assets/kp-dict.json）' % (at, k))
        if x.get('difficulty') not in DIFF:
            W.append('%s 难度「%s」只能是 易、中、难，没填的按「中」算' % (at, x.get('difficulty')))
        g = x.get('grade')
        if g is not None and g not in GRADES[stage]:
            W.append('%s 年级「%s」不对' % (at, g))
        if not str(x.get('stem') or '').strip():
            W.append('%s 没有题干，页面上只能显示考点' % at)
        for q in x.get('parts') or []:
            for k in q.get('kps') or []:
                if k not in kps:
                    E.append('%s%s 考点「%s」不在字典' % (at, q.get('sub', ''), k))
        if x.get('parts'):
            ps = sum(q.get('points') or 0 for q in x['parts'])
            if pts and ps and ps != pts:
                W.append('%s 小问分值合计 %s ≠ %s' % (at, ps, pts))
        for f in x.get('imgs') or []:
            if '/' in f or '\\' in f or f.startswith('.'):
                E.append('%s 图片名「%s」只写文件名' % (at, f))
            elif img_dir and not os.path.isfile(os.path.join(img_dir, pid, f)):
                E.append('%s 图片 %s/%s 找不到' % (at, pid, f))
    if nos:
        miss = [n for n in range(min(nos), max(nos) + 1) if n not in nos]
        if miss:
            E.append('缺题号 ' + '、'.join(map(str, miss)))
        dup = sorted({n for n in nos if nos.count(n) > 1})
        if dup:
            E.append('题号重复 ' + '、'.join(map(str, dup)))
    if isinstance(full, (int, float)) and full > 0 and total != full:
        (W if total >= full * 0.85 else E).append('各题分值合计 %s ≠ 满分 %s' % (total, full))
    if p['kind'] != '真题':
        W.append('这是%s卷：不算进「历年考情」统计（统计只用真题）' % p['kind'])
    return E, W


def main(argv):
    args = [a for a in argv[1:] if not a.startswith('--')]
    opt = lambda k: argv[argv.index(k) + 1] if k in argv else None
    if not args:
        print('用法：check_paper.py <卷.json 或目录> [--img-dir <题图根目录>] [--prefix org1-]')
        return 2
    target = args[0]
    files = [os.path.join(target, f) for f in sorted(os.listdir(target)) if f.endswith('.json')] if os.path.isdir(target) else [target]
    errors = warns = 0
    seen = {}
    for f in files:
        try:
            p = json.load(open(f, encoding='utf-8'))
        except (OSError, ValueError) as e:
            print('✗ %s  读不了：%s' % (f, e))
            errors += 1
            continue
        E, W = check(p, f, opt('--img-dir'), opt('--prefix'))
        pid = p.get('id')
        if pid in seen:
            E.append('编号和 %s 重复' % seen[pid])
        seen[pid] = f
        errors += len(E)
        warns += len(W)
        n = len(p.get('items') or [])
        print('%s %s  %d 题%s%s' % ('✗' if E else '✓', pid or f, n, ' · %d 个错误' % len(E) if E else '', ' · %d 个提醒' % len(W) if W else ''))
        for e in E:
            print('    错误：' + e)
        for w in W:
            print('    提醒：' + w)
    print('\n%d 套 · %d 个错误 · %d 个提醒' % (len(files), errors, warns))
    return 1 if errors else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
