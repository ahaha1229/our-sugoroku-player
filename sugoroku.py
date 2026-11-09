#!/usr/bin/env python3
"""すごろくメーカー（tkinter版）  実行: python sugoroku.py
2〜5人 / テンプレート4種 / ボード自作 / 毎ターンのアイテムルーレット（桃鉄風）
自作ボードは、このファイルと同じ場所の sugoroku_boards.json に保存されます。"""
import json, os, random, sys, tkinter as tk
from tkinter import messagebox

FONT = {"win32": "Yu Gothic UI", "darwin": "Hiragino Sans"}.get(sys.platform, "Noto Sans CJK JP")
F = lambda s=11, b=False: (FONT, s, "bold" if b else "normal")
BGC, FG = "#eaf1ff", "#1d2540"
COLORS = ["#e03131", "#1c7ed6", "#2f9e44", "#f08c00", "#9c36b5"]
CELLBG = {"n": "#ffffff", "f": "#c8f0e0", "b": "#ffd5d5", "s": "#e3d9ff", "a": "#ffeab0", "i": "#ffd6e8", "st": "#d0defa", "go": "#d0defa"}
TNAME = {"n": "ふつう", "f": "進む", "b": "戻る", "s": "1回休み", "a": "もう1回", "i": "アイテム"}
CS, COLS, MAXH = 68, 6, 3
SLOTS = [("ex", "急行", "サイコロ2個"), ("sp", "特急", "サイコロ3個"), ("bar", "バリアー", "悪い効果を1回防ぐ"),
         ("stop", "足止め", "相手を1回休みに"), ("swap", "入れ替え", "相手と場所を交換"),
         ("warp", "ワープ", "8〜12マス進む"), ("wind", "逆風", "他の全員を3マス戻す"), ("miss", "はずれ", "")]
ITEM = {s[0]: s for s in SLOTS}
SAVE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sugoroku_boards.json")


def gen(length, seed, dens=.4):
    r, cells = random.Random(seed), []
    for i in range(length):
        if i < 2 or i >= length - 2 or r.random() > dens:
            cells.append({"t": "n"}); continue
        q, n = r.random(), 1 + int(r.random() * 3) + (r.random() < .3)
        if q < .3: cells.append({"t": "f", "n": n + 1})
        elif q < .5: cells.append({"t": "b", "n": min(n, i - 1)})
        elif q < .64: cells.append({"t": "s"})
        elif q < .78: cells.append({"t": "a"})
        else: cells.append({"t": "i"})
    return cells


TPL = [{"name": "ほどほどコース", "desc": "約30分（4人の目安）", "cells": gen(120, 7)},
       {"name": "のんびりコース", "desc": "約40分（4人の目安）", "cells": gen(160, 21)},
       {"name": "じっくりコース", "desc": "約50分（4人の目安）", "cells": gen(200, 33)},
       {"name": "大冒険コース", "desc": "約1時間（4人の目安）", "cells": gen(250, 58)}]


def lab(c, i, last):
    return "START" if i == 0 else "GOAL" if i == last else {"n": "", "f": f"+{c.get('n')}", "b": f"-{c.get('n')}", "s": "休", "a": "再", "i": "★"}[c["t"]]


def cell_xy(i):
    r, c = divmod(i, COLS)
    return (COLS - 1 - c if r % 2 else c) * CS, r * CS


def draw_board(cv, cells, players=(), cur=-1, sel=None):
    cv.delete("all"); last = len(cells) - 1
    for i, c in enumerate(cells):
        x, y = cell_xy(i); k = "st" if i == 0 else "go" if i == last else c["t"]
        cv.create_rectangle(x + 2, y + 2, x + CS - 2, y + CS - 2, fill=CELLBG[k], outline="#000" if sel == i else "#9aa7c7", width=3 if sel == i else 1)
        cv.create_text(x + 6, y + 5, text=str(i), anchor="nw", font=F(7), fill="#667")
        cv.create_text(x + CS / 2, y + CS / 2 - 4, text=lab(c, i, last), font=F(12, True), fill=FG)
    seen = {}
    for k, p in enumerate(players):
        x, y = cell_xy(p.pos); j = seen[p.pos] = seen.get(p.pos, -1) + 1
        cx, cy, rr = x + 10 + j * 11, y + CS - 10, 7 if k == cur else 5
        cv.create_oval(cx - rr, cy - rr, cx + rr, cy + rr, fill=COLORS[k], outline="#000" if k == cur else "#fff", width=2)
    cv.config(scrollregion=(0, 0, COLS * CS, ((last) // COLS + 1) * CS))


def center(cv, i):
    tot = (len(cv.find_all()) and int(cv.cget("scrollregion").split()[3])) or 1
    cv.yview_moveto(max(0, (cell_xy(i)[1] + CS / 2 - int(cv.cget("height")) / 2) / tot))


def wheel(cv):
    cv.bind("<Enter>", lambda e: (cv.bind_all("<MouseWheel>", lambda ev: cv.yview_scroll(-1 if ev.delta > 0 else 1, "units")),
                                  cv.bind_all("<Button-4>", lambda ev: cv.yview_scroll(-1, "units")),
                                  cv.bind_all("<Button-5>", lambda ev: cv.yview_scroll(1, "units"))))
    cv.bind("<Leave>", lambda e: [cv.unbind_all(s) for s in ("<MouseWheel>", "<Button-4>", "<Button-5>")])


class P:
    def __init__(s, name):
        s.name, s.pos, s.skip, s.dice, s.hand, s.bar = name, 0, 0, 0, [], False


class App(tk.Tk):
    def __init__(self):
        super().__init__(); self.title("すごろくメーカー"); self.geometry("460x880"); self.configure(bg=BGC)
        try: self.mine = json.load(open(SAVE, encoding="utf-8"))
        except Exception: self.mine = []
        self.S = {"n": 2, "names": [f"プレイヤー{i + 1}" for i in range(5)]}
        self.tok = 0; self.box = tk.Frame(self, bg=BGC); self.box.pack(fill="both", expand=True)
        self.home()

    # ---------- 共通部品 ----------
    def store(self):
        try: json.dump(self.mine, open(SAVE, "w", encoding="utf-8"), ensure_ascii=False)
        except OSError: messagebox.showwarning("保存できません", "ボードを保存できませんでした。")

    def clear(self):
        self.tok += 1
        for w in self.box.winfo_children(): w.destroy()

    def lbl(self, parent, text, size=11, bold=False, **kw):
        return tk.Label(parent, text=text, font=F(size, bold), bg=kw.pop("bg", BGC), fg=kw.pop("fg", FG), **kw)

    def btn(self, parent, text, cmd, bg="#3b5bdb", fg="white", size=12, **kw):
        return tk.Button(parent, text=text, command=cmd, font=F(size, True), bg=bg, fg=fg, activebackground=bg, activeforeground=fg, relief="flat", padx=10, pady=6, **kw)

    def top(self, title, back):
        f = tk.Frame(self.box, bg=BGC); f.pack(fill="x", padx=10, pady=8)
        tk.Button(f, text="← もどる", command=back, font=F(10, True), relief="flat", bg=BGC, fg="#3b5bdb").pack(side="left")
        self.lbl(f, title, 14, True).pack(side="left", padx=8); return f

    def run(self, gen): self._run(gen, self.tok)

    def _run(self, gen, tok):
        if tok != self.tok: return
        try: ms = next(gen)
        except StopIteration: return
        self.after(ms, self._run, gen, tok)

    # ---------- 画面 ----------
    def home(self):
        self.clear(); self.lbl(self.box, "すごろくメーカー", 28, True).pack(pady=(50, 6))
        self.lbl(self.box, "2〜5人でみんなであそべる。コースは自分でも作れるよ。", 10).pack(pady=(0, 20))
        for t, cmd, bg in [("テンプレートであそぶ\n用意されたコースが4つ（30分〜1時間）", lambda: self.lst("t"), "#3b5bdb"),
                           (f"じぶんのボードであそぶ\n作ったコースを選ぶ（{len(self.mine)}個）", lambda: self.lst("m"), "#e8590c"),
                           ("ボードをつくる\n長さもマスの中身も自由に決められる", lambda: self.edit(), "#12a37f")]:
            self.btn(self.box, t, cmd, bg).pack(fill="x", padx=26, pady=9)

    def lst(self, kind):
        self.clear(); self.S["kind"] = kind; arr = TPL if kind == "t" else self.mine
        self.top("テンプレートをえらぶ" if kind == "t" else "じぶんのボード", self.home)
        if not arr:
            self.lbl(self.box, "まだボードがありません。").pack(pady=20)
            self.btn(self.box, "ボードをつくる", lambda: self.edit(), "#12a37f").pack()
        for i, b in enumerate(arr):
            r = tk.Frame(self.box, bg="white", highlightbackground="#c9d6f5", highlightthickness=2); r.pack(fill="x", padx=14, pady=5)
            tk.Label(r, text=f"{b['name']}\n{len(b['cells'])}マス  {b.get('desc', '')}", font=F(11, True), bg="white", fg=FG, justify="left", anchor="w").pack(side="left", padx=8, pady=6)
            self.btn(r, "あそぶ", lambda i=i: self.setup(kind, i), size=10).pack(side="right", padx=4)
            if kind == "m":
                self.btn(r, "さくじょ", lambda i=i: self.delete(i), "#868e96", size=10).pack(side="right", padx=2)
                self.btn(r, "へんしゅう", lambda i=i: self.edit(i), "#868e96", size=10).pack(side="right", padx=2)

    def delete(self, i):
        if messagebox.askyesno("さくじょ", f"「{self.mine[i]['name']}」を消しますか？"):
            del self.mine[i]; self.store(); self.lst("m")

    def setup(self, kind, i):
        self.S.update(kind=kind, idx=i, board=(TPL if kind == "t" else self.mine)[i]); self.setup_view()

    def setup_view(self):
        S = self.S; self.clear(); self.top(S["board"]["name"], lambda: self.lst(S["kind"]))
        self.lbl(self.box, f"{len(S['board']['cells'])}マスのコース  /  なん人であそぶ？", 10).pack(pady=(4, 6))
        row = tk.Frame(self.box, bg=BGC); row.pack()
        for n in (2, 3, 4, 5):
            on = n == S["n"]
            self.btn(row, f"{n}人", lambda n=n: (S.update(n=n), self.setup_view()), "#3b5bdb" if on else "white", "white" if on else FG).pack(side="left", padx=4)
        self.lbl(self.box, "なまえ", 10).pack(pady=(18, 4))
        for k in range(S["n"]):
            r = tk.Frame(self.box, bg=BGC); r.pack(pady=3)
            tk.Label(r, text="●", fg=COLORS[k], bg=BGC, font=F(16)).pack(side="left")
            v = tk.StringVar(value=S["names"][k]); v.trace_add("write", lambda *a, k=k, v=v: S["names"].__setitem__(k, v.get()))
            tk.Entry(r, textvariable=v, font=F(12), width=16).pack(side="left", padx=6)
        self.btn(self.box, "スタート！", self.start_game).pack(fill="x", padx=26, pady=24)

    # ---------- ゲーム ----------
    def cur(self): return self.pl[self.t]

    def start_game(self):
        S = self.S; self.cells = S["board"]["cells"]; self.last = len(self.cells) - 1
        self.t, self.busy, self.over, self.used = 0, True, False, False
        self.pl = [P(S["names"][k].strip() or f"プレイヤー{k + 1}") for k in range(S["n"])]
        self.clear(); self.top(S["board"]["name"], lambda: messagebox.askyesno("やめる", "ゲームをやめますか？") and self.setup_view())
        f = tk.Frame(self.box, bg=BGC); f.pack()
        self.cv = tk.Canvas(f, width=COLS * CS, height=300, bg=BGC, highlightthickness=0); self.cv.pack(side="left")
        sb = tk.Scrollbar(f, command=self.cv.yview); sb.pack(side="left", fill="y"); self.cv.config(yscrollcommand=sb.set); wheel(self.cv)
        self.lbl(self.box, "+n進む  -n戻る  休:1回休み  再:もう1回  ★:アイテムマス", 8, fg="#667").pack()
        pn = tk.Frame(self.box, bg="white", highlightbackground="#c9d6f5", highlightthickness=2); pn.pack(fill="x", padx=14, pady=6)
        self.die = tk.Label(pn, text="-", font=F(24, True), width=7, bg="white", fg=FG); self.die.pack(side="left")
        self.msg = tk.Label(pn, text="", font=F(11, True), wraplength=300, justify="left", bg="white", fg=FG, height=2); self.msg.pack(side="left")
        self.act = tk.Frame(self.box, bg=BGC); self.act.pack(fill="x", padx=14)
        self.plv = tk.Frame(self.box, bg=BGC); self.plv.pack(fill="x", padx=14, pady=6)
        self.run(self.turn())

    def say(self, t): self.msg.config(text=t)

    def clear_act(self):
        for w in self.act.winfo_children(): w.destroy()

    def draw(self):
        draw_board(self.cv, self.cells, self.pl, self.t); center(self.cv, self.cur().pos); self.draw_players()

    def draw_players(self):
        for w in self.plv.winfo_children(): w.destroy()
        for k, p in enumerate(self.pl):
            hand = " ".join(ITEM[c][1] for c in p.hand) or "なし"
            tk.Label(self.plv, anchor="w", bg=BGC, fg=COLORS[k], font=F(10, k == self.t),
                     text=f"{'▶' if k == self.t else '　'}{p.name}  {p.pos}/{self.last}{' [休]' if p.skip else ''}{' [盾]' if p.bar else ''}  手札:{hand}").pack(fill="x")

    def turn(self):
        self.busy, self.used = True, False; p = self.cur(); self.draw()
        if p.skip:
            p.skip -= 1; self.say(f"{p.name}は今回お休み…"); self.clear_act(); yield 1100; self.nxt(); return
        yield from self.spin(p); self.action_ui()

    def nxt(self): self.t = (self.t + 1) % len(self.pl); self.run(self.turn())

    def spin(self, p):
        self.say(f"{p.name}のアイテムルーレット！"); self.clear_act(); g = tk.Frame(self.act, bg=BGC); g.pack(fill="x"); cells = []
        for i, (_, n, _) in enumerate(SLOTS):
            l = tk.Label(g, text=n, font=F(11, True), width=8, height=2, bg="#f3f3f3", fg=FG, relief="groove"); l.grid(row=i // 4, column=i % 4, padx=2, pady=2); cells.append(l)
        if len(p.hand) >= MAXH:
            self.say(f"{p.name}はカードがいっぱい！使うとまた回せるよ"); yield 1200; return
        t = random.randrange(8); N = 16 + t
        for k in range(1, N + 1):
            for i, l in enumerate(cells): l.config(bg="#ffc83d" if i == k % 8 else "#f3f3f3")
            yield int(40 + (k / N) ** 3 * 220)
        cid, n, _ = SLOTS[t]
        if cid == "miss": self.say("はずれ…")
        else: p.hand.append(cid); self.say(f"{n}カードをゲット！")
        self.draw_players(); yield 900

    def action_ui(self):
        p = self.cur(); self.busy = False; self.draw_players(); self.clear_act()
        h = tk.Frame(self.act, bg=BGC); h.pack(fill="x")
        for k, cid in enumerate(p.hand):
            tk.Button(h, text=f"{ITEM[cid][1]}\n{ITEM[cid][2]}", font=F(9, True), bg="#fff3bf", wraplength=120, state="disabled" if self.used else "normal",
                      command=lambda k=k: self.use_card(k)).pack(side="left", expand=True, fill="x", padx=3)
        if not p.hand: self.lbl(h, "カードなし", 10).pack()
        self.btn(self.act, f"{p.name}：サイコロをふる", self.roll, COLORS[self.t]).pack(fill="x", pady=6)
        self.say(f"{p.name}の番。カードは1ターンに1枚まで")

    def pick(self, title, cb):
        self.say(title); self.clear_act()
        for k, q in enumerate(self.pl):
            if q is not self.cur(): self.btn(self.act, f"{q.name}（{q.pos}マス）", lambda q=q: cb(q), COLORS[k]).pack(fill="x", pady=2)
        self.btn(self.act, "やめる", self.action_ui, "#868e96", size=10).pack(pady=4)

    @staticmethod
    def guard(q):
        if q.bar: q.bar = False; return True
        return False

    def use_card(self, k):
        if self.busy or self.used: return
        p = self.cur(); cid = p.hand[k]

        def fin(): p.hand.remove(cid); self.used = True
        if cid in ("ex", "sp"): fin(); p.dice = 2 if cid == "ex" else 3; self.roll()
        elif cid == "bar": fin(); p.bar = True; self.action_ui(); self.say("バリアーを張った！")
        elif cid == "warp": fin(); self.busy = True; self.run(self._warp(p))
        elif cid == "wind":
            fin(); bl = []
            for q in self.pl:
                if q is not p:
                    if self.guard(q): bl.append(q.name)
                    else: q.pos = max(0, q.pos - 3)
            self.draw(); self.action_ui(); self.say("逆風！" + ("・".join(bl) + "はバリアーで防いだ" if bl else "他の全員が3マス戻った"))
        elif cid == "stop":
            def do(q):
                g = self.guard(q); q.skip = 0 if g else 1; fin(); self.action_ui()
                self.say(f"{q.name}のバリアーで防がれた！" if g else f"{q.name}を足止め！")
            self.pick("だれを足止めする？", do)
        elif cid == "swap":
            def do(q):
                p.pos, q.pos = q.pos, p.pos; fin(); self.draw(); self.action_ui(); self.say(f"{p.name}と{q.name}が入れ替わった！")
            self.pick("だれと入れ替わる？", do)

    def _warp(self, p):
        n = random.randint(8, 12); self.clear_act(); self.say(f"ワープ！{n}マス進む"); yield 700
        yield from self.move(p, n); again = yield from self.land(p); yield from self.finish(p, again)

    def roll(self):
        if self.busy or self.over: return
        self.busy = True; self.run(self._roll())

    def _roll(self):
        p = self.cur(); n = p.dice or 1; p.dice = 0; self.clear_act()
        for _ in range(8):
            d = [random.randint(1, 6) for _ in range(n)]; self.die.config(text=" ".join(map(str, d))); yield 70
        s = sum(d); self.say(f"{p.name}は {'+'.join(map(str, d))}{'=' + str(s) if n > 1 else ''} 進む！"); yield 450
        yield from self.move(p, s); again = yield from self.land(p); yield from self.finish(p, again)

    def move(self, p, n):
        s = 1 if n > 0 else -1
        for _ in range(abs(n)):
            np_ = p.pos + s
            if np_ < 0 or np_ > self.last: break
            p.pos = np_; self.draw(); yield 220
            if np_ == self.last: break

    def land(self, p):
        if p.pos >= self.last: return False
        c = self.cells[p.pos]; t = c["t"]
        if t == "f": self.say(f"{c['n']}マス進む！"); yield 600; yield from self.move(p, c["n"])
        elif t == "b":
            if self.guard(p): self.say("バリアーが戻るのを防いだ！")
            else: self.say(f"{c['n']}マス戻る…"); yield 600; yield from self.move(p, -c["n"])
        elif t == "s":
            if self.guard(p): self.say("バリアーが休みを防いだ！")
            else: p.skip = 1; self.say("次は1回お休み…")
        elif t == "a": self.say("もう1回ふれる！"); return True
        elif t == "i": self.say("アイテムマス！"); yield 700; yield from self.spin(p)
        return False

    def finish(self, p, again):
        if p.pos >= self.last:
            self.over = True; self.draw()
            if messagebox.askyesno(f"{p.name}の勝ち！", "ゴールおめでとう！\nもう一度あそびますか？（いいえ：タイトルへ）"): self.start_game()
            else: self.home()
            return
        self.draw_players(); yield 800
        if again: self.used = False; self.action_ui()
        else: self.nxt()

    # ---------- ボードエディタ ----------
    def edit(self, i=None):
        b = self.mine[i] if i is not None else None
        cells = json.loads(json.dumps(b["cells"])) if b else [{"t": "n"} for _ in range(100)]
        self.E = {"idx": i, "cells": cells, "sel": None}; self.clear(); self.top("ボードをつくる", self.home)
        self.E["name"] = tk.StringVar(value=b["name"] if b else "マイボード")
        tk.Entry(self.box, textvariable=self.E["name"], font=F(12)).pack(fill="x", padx=14)
        self.elen = self.lbl(self.box, "", 10); self.elen.pack()
        sc = tk.Scale(self.box, from_=20, to=300, orient="horizontal", showvalue=False, bg=BGC, highlightthickness=0); sc.set(len(cells)); sc.pack(fill="x", padx=14)
        f = tk.Frame(self.box, bg=BGC); f.pack()
        self.ecv = tk.Canvas(f, width=COLS * CS, height=280, bg=BGC, highlightthickness=0); self.ecv.pack(side="left")
        sb = tk.Scrollbar(f, command=self.ecv.yview); sb.pack(side="left", fill="y"); self.ecv.config(yscrollcommand=sb.set); wheel(self.ecv)
        self.ecv.bind("<Button-1>", self.ecv_click)
        self.ep = tk.Frame(self.box, bg="white", highlightbackground="#c9d6f5", highlightthickness=2); self.ep.pack(fill="x", padx=14, pady=6)
        self.btn(self.box, "おまかせ配置", lambda: (self.E.update(cells=gen(len(self.E["cells"]), random.random()), sel=None), self.erefresh()), "#868e96", size=10).pack()
        self.btn(self.box, "保存してあそぶ", lambda: self.save_b(True), "#12a37f").pack(fill="x", padx=14, pady=4)
        self.btn(self.box, "保存して一覧へ", lambda: self.save_b(False)).pack(fill="x", padx=14)
        self.erefresh(); sc.config(command=self.setlen)

    def setlen(self, v):
        v = int(float(v)); c = self.E["cells"]
        if v == len(c): return
        while len(c) < v: c.append({"t": "n"})
        del c[v:]; c[-1] = {"t": "n"}
        if self.E["sel"] is not None and self.E["sel"] >= v - 1: self.E["sel"] = None
        self.erefresh()

    def ecv_click(self, e):
        c, r = int(self.ecv.canvasx(e.x) // CS), int(self.ecv.canvasy(e.y) // CS)
        if c >= COLS: return
        i = r * COLS + (COLS - 1 - c if r % 2 else c)
        if 0 <= i < len(self.E["cells"]): self.E["sel"] = i; self.erefresh()

    def erefresh(self):
        E = self.E; cells, s = E["cells"], E["sel"]; self.elen.config(text=f"長さ：{len(cells)}マス（スライダーで変更）")
        draw_board(self.ecv, cells, sel=s)
        for w in self.ep.winfo_children(): w.destroy()
        if s in (None, 0, len(cells) - 1):
            tk.Label(self.ep, text="マスをクリックして中身を決めよう（スタートとゴールは固定）", font=F(10), bg="white", fg="#667").pack(pady=8); return
        x = cells[s]; tk.Label(self.ep, text=f"{s}マス目", font=F(11, True), bg="white", fg=FG).pack()
        row = tk.Frame(self.ep, bg="white"); row.pack(pady=4)
        for t, n in TNAME.items():
            tk.Button(row, text=n, font=F(9, True), relief="sunken" if x["t"] == t else "raised", bg="#ffc83d" if x["t"] == t else "#f3f3f3", command=lambda t=t: self.set_t(t)).pack(side="left", padx=1)
        if x["t"] in ("f", "b"):
            r2 = tk.Frame(self.ep, bg="white"); r2.pack(pady=4)
            tk.Button(r2, text="−", width=3, command=lambda: self.step(-1)).pack(side="left")
            tk.Label(r2, text=f"{x['n']}マス{'進む' if x['t'] == 'f' else '戻る'}", font=F(11, True), bg="white", fg=FG).pack(side="left", padx=8)
            tk.Button(r2, text="＋", width=3, command=lambda: self.step(1)).pack(side="left")

    def set_t(self, t):
        x = self.E["cells"][self.E["sel"]]; x["t"] = t
        if t in ("f", "b"): x["n"] = x.get("n", 2)
        else: x.pop("n", None)
        self.erefresh()

    def step(self, d):
        x = self.E["cells"][self.E["sel"]]; x["n"] = max(1, min(6, x["n"] + d)); self.erefresh()

    def save_b(self, play):
        o = {"name": self.E["name"].get().strip() or "マイボード", "cells": self.E["cells"]}; i = self.E["idx"]
        if i is None: self.mine.append(o); i = len(self.mine) - 1
        else: self.mine[i] = o
        self.store(); self.setup("m", i) if play else self.lst("m")


if __name__ == "__main__":
    App().mainloop()
