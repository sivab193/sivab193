#!/usr/bin/env python3
"""
Self-generated GitHub profile card.

Fetches repos, languages, lines-of-code (authored) and contribution stats via the
GitHub GraphQL API, then renders two self-contained animated SVGs (dark + light,
VS Code style) and refreshes the "Latest Projects" table inside README.md.

No third-party services, no pip dependencies (stdlib only).

Env:
  GH_TOKEN   token with read access to the repos you want counted (private -> needs repo scope)
  GH_LOGIN   github username (default: sivab193)
Run from the repository root:  python .github/scripts/generate.py
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request
from collections import Counter

TOKEN = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
LOGIN = os.environ.get("GH_LOGIN", "sivab193")

# Curated stack shown on the card's `stack:` line. Kept separate from the
# auto-computed language breakdown (in the terminal panel) so it complements
# rather than repeats it. Edit freely.
STACK = ["TypeScript", "React", "Python", "AWS"]
GRAPHQL = "https://api.github.com/graphql"
REST = "https://api.github.com"
ROOT = os.getcwd()

if not TOKEN:
    sys.exit("error: set GH_TOKEN (a PAT with repo read scope to include private repos)")


# --------------------------------------------------------------------------- API
def gql(query, variables):
    body = json.dumps({"query": query, "variables": variables}).encode()
    req = urllib.request.Request(
        GRAPHQL,
        data=body,
        headers={
            "Authorization": f"bearer {TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": f"{LOGIN}-profile-generator",
        },
    )
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req) as r:
                d = json.loads(r.read())
            if "errors" in d:
                sys.stderr.write("graphql warnings: " + json.dumps(d["errors"])[:400] + "\n")
            return d.get("data", {}) or {}
        except urllib.error.HTTPError as e:
            if e.code in (403, 502) and attempt < 3:
                time.sleep(2 * (attempt + 1))
                continue
            raise


def all_time_commits():
    """Best-effort all-time authored commit count via the commit search API."""
    req = urllib.request.Request(
        f"{REST}/search/commits?q=author:{LOGIN}&per_page=1",
        headers={
            "Authorization": f"bearer {TOKEN}",
            "Accept": "application/vnd.github+json",
            "User-Agent": f"{LOGIN}-profile-generator",
        },
    )
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read()).get("total_count", 0)
    except Exception:
        return 0


USER_Q = """
query($login:String!){
  viewer{ id }
  user(login:$login){
    name login createdAt
    followers{totalCount}
    contributionsCollection{
      totalCommitContributions restrictedContributionsCount
      contributionCalendar{ totalContributions weeks{ contributionDays{ contributionCount } } }
    }
  }
}"""

REPOS_Q = """
query($login:String!,$cursor:String){
  user(login:$login){
    repositories(first:50,after:$cursor,ownerAffiliations:OWNER,isFork:false,orderBy:{field:PUSHED_AT,direction:DESC}){
      pageInfo{hasNextPage endCursor}
      nodes{
        name isPrivate description url homepageUrl stargazerCount pushedAt
        primaryLanguage{name color}
        repositoryTopics(first:4){nodes{topic{name}}}
        languages(first:10,orderBy:{field:SIZE,direction:DESC}){edges{size node{name color}}}
        defaultBranchRef{name}
      }
    }
  }
}"""

LOC_Q = """
query($owner:String!,$name:String!,$id:ID!,$cursor:String){
  repository(owner:$owner,name:$name){
    defaultBranchRef{ target{ ... on Commit {
      history(first:100,after:$cursor,author:{id:$id}){
        totalCount pageInfo{hasNextPage endCursor}
        nodes{ additions deletions }
      }
    }}}
  }
}"""


def fetch():
    sys.stderr.write("fetching user + contributions\n")
    u = gql(USER_Q, {"login": LOGIN})
    viewer_id = u["viewer"]["id"]
    user = u["user"]

    sys.stderr.write("fetching repositories\n")
    repos, cursor = [], None
    while True:
        d = gql(REPOS_Q, {"login": LOGIN, "cursor": cursor})["user"]["repositories"]
        repos += d["nodes"]
        if not d["pageInfo"]["hasNextPage"]:
            break
        cursor = d["pageInfo"]["endCursor"]

    sys.stderr.write(f"counting lines of code across {len(repos)} repos\n")
    add = dl = 0
    for r in repos:
        r["loc_add"] = 0
        if not r.get("defaultBranchRef"):
            continue
        cur = None
        for _ in range(12):  # cap 1200 commits/repo
            rd = gql(LOC_Q, {"owner": LOGIN, "name": r["name"], "id": viewer_id, "cursor": cur})
            h = (((rd.get("repository") or {}).get("defaultBranchRef") or {}).get("target") or {}).get("history")
            if not h:
                break
            for n in h["nodes"]:
                add += n["additions"]
                dl += n["deletions"]
                r["loc_add"] += n["additions"]
            if not h["pageInfo"]["hasNextPage"]:
                break
            cur = h["pageInfo"]["endCursor"]

    return {
        "user": user,
        "repos": repos,
        "totals": {
            "add": add,
            "del": dl,
            "net": add - dl,
            "commits_all_time": all_time_commits(),
            "repo_count": len(repos),
        },
    }


# ------------------------------------------------------------------------ render
def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def fmt(n):
    return f"{n:,}"


THEMES = {
    "dark": dict(
        win="#1e1e1e", border="#0d1117", title="#323233", act="#333333", tabbar="#252526",
        tab_active="#1e1e1e", tab_inact="#2d2d2d", panel="#181818", status="#007acc",
        status_tx="#ffffff", gut="#858585", act_ic="#858585", tabtx="#cccccc",
        tabtx_dim="#8a8a8a", paneltx="#cccccc", panhdr="#9d9d9d", barbg="#2a2d2e",
        kw="#569cd6", var="#4fc1ff", prop="#9cdcfe", str="#ce9178", num="#b5cea8",
        pun="#d4d4d4", com="#6a9955", t="#d4d4d4", caret="#aeafad",
    ),
    "light": dict(
        win="#ffffff", border="#d0d7de", title="#e4e4e4", act="#f3f3f3", tabbar="#ececec",
        tab_active="#ffffff", tab_inact="#e8e8e8", panel="#f8f8f8", status="#007acc",
        status_tx="#ffffff", gut="#237893", act_ic="#616161", tabtx="#333333",
        tabtx_dim="#7a7a7a", paneltx="#333333", panhdr="#6a6a6a", barbg="#e6e6e6",
        kw="#0000ff", var="#0070c1", prop="#001080", str="#a31515", num="#098658",
        pun="#333333", com="#008000", t="#333333", caret="#333333",
    ),
}

# geometry
W = 860
TITLE_H = 34
TAB_TOP = TITLE_H
TAB_H = 32
EDITOR_TOP = TAB_TOP + TAB_H
LH = 22
CODE_TOP = EDITOR_TOP + 26
ACT_W = 48
GUT_R = ACT_W + 40
CODEX = ACT_W + 52
N = 10
PANEL_TOP = CODE_TOP + N * LH + 6
PANEL_H = 138
STATUS_H = 26
H = PANEL_TOP + PANEL_H + STATUS_H
CLIPW = W - CODEX - 16
RADIUS = 12


def render(theme_name, data):
    c = THEMES[theme_name]
    T = data["totals"]
    user = data["user"]
    cc = user["contributionsCollection"]

    repo_count = T["repo_count"]
    commits = T["commits_all_time"] or "—"
    loc_add = T["add"]
    loc_net = T["net"]
    contribs_year = cc["contributionCalendar"]["totalContributions"]

    lang_size, lang_col = Counter(), {}
    for r in data["repos"]:
        for e in r["languages"]["edges"]:
            lang_size[e["node"]["name"]] += e["size"]
            lang_col[e["node"]["name"]] = e["node"]["color"]
    lang_total = sum(lang_size.values()) or 1
    top_langs = [(n, 100 * s / lang_total, lang_col.get(n, "#888")) for n, s in lang_size.most_common(5)]
    top_lang_name = top_langs[0][0] if top_langs else "Code"

    latest = [r for r in data["repos"] if r["name"] != user["login"]][:3]
    weeks = cc["contributionCalendar"]["weeks"]
    spark = [sum(dd["contributionCount"] for dd in w["contributionDays"]) for w in weeks][-30:]
    updated = time.strftime("%b %d", time.gmtime())

    # stack line: each curated tech string token individually colored
    stack_tokens = [("t", "  "), ("prop", "stack"), ("pun", ": [")]
    stack_names = STACK or [top_lang_name]
    for i, n in enumerate(stack_names):
        stack_tokens.append(("str", f'"{n}"'))
        if i < len(stack_names) - 1:
            stack_tokens.append(("pun", ", "))
    stack_tokens.append(("pun", "],"))

    commits_txt = fmt(commits).replace(",", "_") if isinstance(commits, int) else str(commits)
    lines = [
        [("kw", "const "), ("var", "sivab"), ("pun", " = "), ("pun", "{")],
        [("t", "  "), ("prop", "role"), ("pun", ": "), ("str", '"Full-Stack · Cloud · Security"'), ("pun", ",")],
        [("t", "  "), ("prop", "education"), ("pun", ": "), ("str", '"CS @ Purdue"'), ("pun", ",")],
        [("t", "  "), ("prop", "repos"), ("pun", ": "), ("num", str(repo_count)), ("pun", ","), ("com", "          // owned, non-fork")],
        [("t", "  "), ("prop", "commits"), ("pun", ": "), ("num", commits_txt), ("pun", ",")],
        [("t", "  "), ("prop", "linesOfCode"), ("pun", ": "), ("num", fmt(loc_add).replace(",", "_")), ("pun", ","), ("com", f"   // net {fmt(loc_net).replace(',', '_')}")],
        stack_tokens,
        [("t", "  "), ("prop", "latest"), ("pun", ": "), ("str", f'"{latest[0]["name"]}"' if latest else '""'), ("pun", ","), ("com", f"   // +{repo_count - 1} more shipped")],
        [("t", "  "), ("prop", "building"), ("pun", ": "), ("kw", "true"), ("pun", ","), ("com", "        // always")],
        [("pun", "}")],
    ]

    p = []
    p.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
        f'font-family="ui-monospace,SFMono-Regular,\'SF Mono\',Menlo,Consolas,\'Liberation Mono\',monospace">'
    )
    p.append(
        "<style>"
        "text{white-space:pre;}"
        f".fin{{opacity:0;animation:fin .5s ease forwards;}}"
        "@keyframes fin{to{opacity:1;}}"
        "@keyframes blink{0%,49%{opacity:1;}50%,100%{opacity:0;}}"
        ".caret{animation:blink 1.05s step-end infinite;}"
        "@media(prefers-reduced-motion:reduce){.fin{opacity:1;animation:none;}.caret{animation:none;}}"
        "</style>"
    )

    p.append(f'<rect x="0.5" y="0.5" width="{W-1}" height="{H-1}" rx="{RADIUS}" fill="{c["win"]}" stroke="{c["border"]}"/>')
    p.append(f'<clipPath id="{theme_name}win"><rect x="0" y="0" width="{W}" height="{H}" rx="{RADIUS}"/></clipPath>')
    p.append(f'<g clip-path="url(#{theme_name}win)">')

    # title bar
    p.append(f'<rect x="0" y="0" width="{W}" height="{TITLE_H}" fill="{c["title"]}"/>')
    for i, col in enumerate(["#ff5f56", "#ffbd2e", "#27c93f"]):
        p.append(f'<circle cx="{20+i*20}" cy="{TITLE_H/2}" r="6" fill="{col}"/>')
    p.append(
        f'<text x="{W/2}" y="{TITLE_H/2+4}" text-anchor="middle" font-size="13" fill="{c["tabtx_dim"]}">'
        f'<tspan fill="{c["kw"]}">●</tspan> sivab.tsx — {esc(LOGIN)}</text>'
    )

    # activity bar + icons
    p.append(f'<rect x="0" y="{TITLE_H}" width="{ACT_W}" height="{H-TITLE_H-STATUS_H}" fill="{c["act"]}"/>')
    p.append(f'<path d="M{ACT_W/2-7} {TITLE_H+22} h9 l5 5 v13 h-14 z" fill="none" stroke="{c["kw"]}" stroke-width="1.6"/>')
    p.append(f'<circle cx="{ACT_W/2-2}" cy="{TITLE_H+62}" r="6" fill="none" stroke="{c["act_ic"]}" stroke-width="1.6"/>'
             f'<line x1="{ACT_W/2+3}" y1="{TITLE_H+67}" x2="{ACT_W/2+8}" y2="{TITLE_H+72}" stroke="{c["act_ic"]}" stroke-width="1.6"/>')
    p.append(f'<g stroke="{c["act_ic"]}" stroke-width="1.6" fill="none">'
             f'<circle cx="{ACT_W/2-5}" cy="{TITLE_H+100}" r="3"/><circle cx="{ACT_W/2-5}" cy="{TITLE_H+118}" r="3"/>'
             f'<circle cx="{ACT_W/2+7}" cy="{TITLE_H+104}" r="3"/>'
             f'<path d="M{ACT_W/2-5} {TITLE_H+103} v12 M{ACT_W/2-5} {TITLE_H+110} q0 -6 8 -6"/></g>')

    # tab bar
    p.append(f'<rect x="{ACT_W}" y="{TAB_TOP}" width="{W-ACT_W}" height="{TAB_H}" fill="{c["tabbar"]}"/>')
    tabs = [("sivab.tsx", c["kw"], True)]
    for r in latest[:2]:
        col = (r.get("primaryLanguage") or {}).get("color") or c["tabtx_dim"]
        tabs.append((r["name"], col, False))
    tx = ACT_W
    for name, dot, active in tabs:
        tw = 24 + len(name) * 8 + 20
        p.append(f'<rect x="{tx}" y="{TAB_TOP}" width="{tw}" height="{TAB_H}" fill="{c["tab_active"] if active else c["tab_inact"]}"/>')
        if active:
            p.append(f'<rect x="{tx}" y="{TAB_TOP}" width="{tw}" height="2" fill="{c["status"]}"/>')
        p.append(f'<circle cx="{tx+14}" cy="{TAB_TOP+TAB_H/2}" r="4" fill="{dot}"/>')
        p.append(f'<text x="{tx+24}" y="{TAB_TOP+TAB_H/2+4}" font-size="12.5" fill="{c["tabtx"] if active else c["tabtx_dim"]}">{esc(name)}</text>')
        p.append(f'<text x="{tx+tw-14}" y="{TAB_TOP+TAB_H/2+4}" font-size="12" fill="{c["tabtx_dim"]}">×</text>')
        tx += tw

    # editor: gutter + typed code
    FS = 14.5
    for i, segs in enumerate(lines):
        ly = CODE_TOP + i * LH
        begin = 0.35 + i * 0.32
        p.append(f'<text class="fin" style="animation-delay:{begin:.2f}s" x="{GUT_R}" y="{ly}" '
                 f'text-anchor="end" font-size="12.5" fill="{c["gut"]}">{i+1}</text>')
        cid = f"{theme_name}c{i}"
        p.append(f'<clipPath id="{cid}"><rect x="{CODEX}" y="{ly-LH+4}" width="0" height="{LH}">'
                 f'<animate attributeName="width" begin="{begin:.2f}s" dur="0.5s" from="0" to="{CLIPW}" fill="freeze"/></rect></clipPath>')
        tspans = "".join(f'<tspan fill="{c[cls]}">{esc(txt)}</tspan>' for cls, txt in segs if txt != "")
        p.append(f'<text clip-path="url(#{cid})" x="{CODEX}" y="{ly}" font-size="{FS}">{tspans}</text>')
    caret_begin = 0.35 + N * 0.32
    cy = CODE_TOP + (N - 1) * LH
    p.append(f'<rect class="caret" style="animation-delay:{caret_begin:.2f}s" x="{CODEX+11}" y="{cy-12}" width="8" height="16" fill="{c["caret"]}" opacity="0"/>')

    # bottom panel
    p.append(f'<rect x="{ACT_W}" y="{PANEL_TOP}" width="{W-ACT_W}" height="{PANEL_H}" fill="{c["panel"]}"/>')
    p.append(f'<line x1="{ACT_W}" y1="{PANEL_TOP}" x2="{W}" y2="{PANEL_TOP}" stroke="{c["border"]}" stroke-width="1"/>')
    hx = CODEX
    for t in ["PROBLEMS", "OUTPUT", "TERMINAL"]:
        active = t == "TERMINAL"
        p.append(f'<text x="{hx}" y="{PANEL_TOP+20}" font-size="11" letter-spacing="0.5" '
                 f'fill="{c["paneltx"] if active else c["panhdr"]}">{t}</text>')
        if active:
            p.append(f'<rect x="{hx}" y="{PANEL_TOP+26}" width="{len(t)*7}" height="1.5" fill="{c["status"]}"/>')
        hx += len(t) * 8 + 22
    p.append(f'<text x="{CODEX}" y="{PANEL_TOP+46}" font-size="12.5" class="fin" style="animation-delay:3.4s">'
             f'<tspan fill="{c["kw"]}">➜</tspan> <tspan fill="{c["prop"]}">~</tspan> '
             f'<tspan fill="{c["t"]}">loc --by-language</tspan></text>')
    bar_x, bar_w = CODEX + 96, 260
    base = max(top_langs[0][1], 1) if top_langs else 1
    for i, (name, pct, col) in enumerate(top_langs):
        by = PANEL_TOP + 62 + i * 15
        fw = max(3, bar_w * pct / base)
        p.append(f'<text x="{CODEX}" y="{by+4}" font-size="11.5" fill="{c["paneltx"]}">{esc(name)}</text>')
        p.append(f'<rect x="{bar_x}" y="{by-8}" width="{bar_w}" height="8" rx="4" fill="{c["barbg"]}"/>')
        p.append(f'<rect x="{bar_x}" y="{by-8}" width="0" height="8" rx="4" fill="{col}">'
                 f'<animate attributeName="width" begin="{3.7+i*0.12:.2f}s" dur="0.7s" from="0" to="{fw:.0f}" '
                 f'fill="freeze" calcMode="spline" keySplines="0.2 0.8 0.2 1" keyTimes="0;1" values="0;{fw:.0f}"/></rect>')
        p.append(f'<text x="{bar_x+bar_w+8}" y="{by+4}" font-size="11" fill="{c["panhdr"]}">{pct:.1f}%</text>')

    sp_x, sp_w = W - 250, 230
    sp_bottom = PANEL_TOP + PANEL_H - 20
    sp_h = 60
    mx = max(spark) if spark else 1
    p.append(f'<text x="{sp_x}" y="{PANEL_TOP+46}" font-size="11.5" fill="{c["panhdr"]}">'
             f'<tspan fill="{c["status"]}" font-size="13">{contribs_year}</tspan> contributions · 1y</text>')
    if spark:
        bwn = sp_w / len(spark)
        for i, v in enumerate(spark):
            bh = max(2, sp_h * v / mx)
            bx = sp_x + i * bwn
            p.append(f'<rect x="{bx:.1f}" y="{sp_bottom-bh:.1f}" width="{bwn-2:.1f}" height="{bh:.1f}" rx="1.5" '
                     f'fill="{c["status"]}" opacity="0" class="fin" style="animation-delay:{3.7+i*0.03:.2f}s"/>')

    p.append("</g>")

    # status bar
    sy = H - STATUS_H
    p.append(f'<g clip-path="url(#{theme_name}win)">')
    p.append(f'<rect x="0" y="{sy}" width="{W}" height="{STATUS_H+RADIUS}" fill="{c["status"]}"/>')
    scy = sy + STATUS_H / 2 + 4
    p.append(f'<text x="14" y="{scy}" font-size="12" fill="{c["status_tx"]}">'
             f'⎇ main <tspan dx="10">↻ 0↓ 0↑</tspan> <tspan dx="10">⊗ 0 ⚠ 0</tspan></text>')
    right = f'⚡ {fmt(loc_add)} LOC   {top_lang_name}   {contribs_year} contribs   ⟳ updated {updated}'
    p.append(f'<text x="{W-14}" y="{scy}" text-anchor="end" font-size="12" fill="{c["status_tx"]}">{esc(right)}</text>')
    p.append("</g>")

    p.append("</svg>")
    return "\n".join(p)


# ---------------------------------------------------- top repos by lines of code
TOP_N = 5


def render_repos(theme_name, data):
    """Animated horizontal bar chart: top public repos by authored lines of code."""
    c = THEMES[theme_name]
    T = data["totals"]
    pub = [r for r in data["repos"] if not r["isPrivate"] and r["name"] != data["user"]["login"]]
    pub.sort(key=lambda r: r.get("loc_add", 0), reverse=True)
    pub = pub[:TOP_N]
    max_loc = max((r.get("loc_add", 0) for r in pub), default=1) or 1

    TH = 34
    PROMPT_Y = TH + 30
    ROW = 36
    ROWS_TOP = TH + 56
    FOOT_Y = ROWS_TOP + len(pub) * ROW + 4
    HH = FOOT_Y + 24
    bar_x = 214
    bar_max = W - bar_x - 118
    bar_h = 15

    p = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{HH}" viewBox="0 0 {W} {HH}" '
        f'font-family="ui-monospace,SFMono-Regular,\'SF Mono\',Menlo,Consolas,\'Liberation Mono\',monospace">',
        "<style>text{white-space:pre;}"
        ".fin{opacity:0;animation:rfin .5s ease forwards;}@keyframes rfin{to{opacity:1;}}"
        "@media(prefers-reduced-motion:reduce){.fin{opacity:1;animation:none;}}</style>",
        f'<rect x="0.5" y="0.5" width="{W-1}" height="{HH-1}" rx="{RADIUS}" fill="{c["win"]}" stroke="{c["border"]}"/>',
        f'<clipPath id="{theme_name}rwin"><rect x="0" y="0" width="{W}" height="{HH}" rx="{RADIUS}"/></clipPath>',
        f'<g clip-path="url(#{theme_name}rwin)">',
        f'<rect x="0" y="0" width="{W}" height="{TH}" fill="{c["title"]}"/>',
    ]
    for i, col in enumerate(["#ff5f56", "#ffbd2e", "#27c93f"]):
        p.append(f'<circle cx="{20+i*20}" cy="{TH/2}" r="6" fill="{col}"/>')
    p.append(f'<text x="{W/2}" y="{TH/2+4}" text-anchor="middle" font-size="13" fill="{c["tabtx_dim"]}">'
             f'loc — lines of code by repository</text>')

    # prompt
    p.append(f'<text x="24" y="{PROMPT_Y}" font-size="13" class="fin" style="animation-delay:.15s">'
             f'<tspan fill="{c["kw"]}">➜</tspan>  <tspan fill="{c["prop"]}">~</tspan>  '
             f'<tspan fill="{c["t"]}">loc --sort lines --top {TOP_N}</tspan></text>')

    for i, r in enumerate(pub):
        cy = ROWS_TOP + i * ROW
        col = (r.get("primaryLanguage") or {}).get("color") or c["status"]
        name = r["name"]
        loc = r.get("loc_add", 0)
        fw = max(4, bar_max * loc / max_loc)
        begin = 0.4 + i * 0.14
        p.append(f'<text x="24" y="{cy+5}" font-size="13" fill="{c["gut"]}">{i+1}</text>')
        p.append(f'<text x="44" y="{cy+5}" font-size="13.5" fill="{c["t"]}">{esc(name)}</text>')
        p.append(f'<rect x="{bar_x}" y="{cy-bar_h/2}" width="{bar_max}" height="{bar_h}" rx="{bar_h/2}" fill="{c["barbg"]}"/>')
        p.append(f'<rect x="{bar_x}" y="{cy-bar_h/2}" width="0" height="{bar_h}" rx="{bar_h/2}" fill="{col}">'
                 f'<animate attributeName="width" begin="{begin:.2f}s" dur="0.8s" from="0" to="{fw:.0f}" '
                 f'fill="freeze" calcMode="spline" keySplines="0.2 0.85 0.25 1" keyTimes="0;1" values="0;{fw:.0f}"/></rect>')
        p.append(f'<text x="{W-24}" y="{cy+5}" text-anchor="end" font-size="13" fill="{c["prop"]}" '
                 f'class="fin" style="animation-delay:{begin+0.5:.2f}s">{fmt(loc)}</text>')

    p.append(f'<text x="24" y="{FOOT_Y+8}" font-size="12" fill="{c["com"]}">'
             f'# {T["repo_count"]} repositories · {fmt(T["add"])} lines written · net {fmt(T["net"])}</text>')
    p.append("</g></svg>")
    return "\n".join(p)


# --------------------------------------------------------------- README injection
def update_readme(data):
    path = os.path.join(ROOT, "README.md")
    if not os.path.exists(path):
        return
    start, end = "<!-- LATEST:START -->", "<!-- LATEST:END -->"
    text = open(path, encoding="utf-8").read()
    if start not in text or end not in text:
        return

    pub = [r for r in data["repos"] if not r["isPrivate"] and r["name"] != data["user"]["login"]]
    pub = pub[:6]
    rows = ["| Project | What it is | Stack | Lines |", "|---|---|---|---|"]
    for r in pub:
        name = r["name"]
        link = r["homepageUrl"] or r["url"]
        title = f"**[{name}]({link})**"
        # descriptor fallback: description -> live site -> topics -> dash
        desc = (r["description"] or "").strip()
        if not desc and r["homepageUrl"]:
            domain = r["homepageUrl"].split("//")[-1].strip("/").split("/")[0]
            desc = f"🔗 Live at {domain}"
        if not desc:
            topics = [t["topic"]["name"] for t in (r.get("repositoryTopics") or {}).get("nodes", [])]
            desc = " · ".join(topics)
        if len(desc) > 78:
            desc = desc[:75].rstrip() + "…"
        desc = desc.replace("|", "\\|") or "—"
        lang = (r.get("primaryLanguage") or {}).get("name") or "—"
        loc = f"{r.get('loc_add', 0):,}"
        rows.append(f"| {title} | {desc} | `{lang}` | {loc} |")
    block = start + "\n" + "\n".join(rows) + "\n" + end
    pre = text.split(start)[0]
    post = text.split(end)[1]
    open(path, "w", encoding="utf-8").write(pre + block + post)
    sys.stderr.write(f"updated README latest-projects ({len(pub)} repos)\n")


def main():
    data = fetch()
    T = data["totals"]
    os.makedirs(os.path.join(ROOT, "assets"), exist_ok=True)
    for theme in ("dark", "light"):
        with open(os.path.join(ROOT, "assets", f"{theme}.svg"), "w", encoding="utf-8") as f:
            f.write(render(theme, data))
        with open(os.path.join(ROOT, "assets", f"repos-{theme}.svg"), "w", encoding="utf-8") as f:
            f.write(render_repos(theme, data))
    update_readme(data)
    sys.stderr.write(
        f"done: +{T['add']:,} / -{T['del']:,} net {T['net']:,} | "
        f"{T['commits_all_time']} commits | {T['repo_count']} repos\n"
    )


if __name__ == "__main__":
    main()
