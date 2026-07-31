"""
HTML template renderer and card sanitization module.
"""
from pathlib import Path
from models import (
    esc, source_key, EMOJI, CAT_ICON, CAT_FILTERS, SRC_LABELS, IMP_ORDER, safe_int
)

UI_DIR = Path(__file__).parent
CSS = (UI_DIR / "static" / "style.css").read_text(encoding="utf-8")
FILTER_JS = "<script>\n" + (UI_DIR / "static" / "app.js").read_text(encoding="utf-8") + "\n</script>"


def safe_url(url: str) -> str:
    url_str = (url or "").strip()
    if url_str.lower().startswith(("http://", "https://")):
        return url_str
    return ""


def render_card(c):
    dup_cls = " dup" if c.duplicate_of else ""
    is_dup = 1 if c.duplicate_of else 0
    is_qw = 1 if (c.importance == "high" and c.difficulty == "easy" and not c.duplicate_of) else 0
    if c.duplicate_of:
        dupnote = ('<div class="dupnote"><span class="msi" style="font-size:16px">subdirectory_arrow_right</span>'
                   'duplicate of %s</div>') % esc(c.duplicate_of)
    elif c.dup_count:
        dupnote = ('<div class="dupnote"><span class="msi" style="font-size:16px">content_copy</span>'
                   '%d similar reports merged</div>') % c.dup_count
    else:
        dupnote = ""
    clean_url = safe_url(c.url)
    link = ('<a href="%s" target="_blank" rel="noopener">source <span class="msi" style="font-size:14px">open_in_new</span></a>'
            % esc(clean_url)) if clean_url else "<span>%s</span>" % esc(c.source)
    cat_icon = CAT_ICON.get(c.category, "label")
    return (
        '<div class="card%s" data-cat="%s" data-imp="%s" data-src="%s" data-dup="%d" data-qw="%d">'
        '<div class="chips">'
        '<span class="chip cat-%s"><span class="msi">%s</span>%s</span>'
        '<span class="chip imp-%s">%s</span>'
        '<span class="chip plain"><span class="msi">build</span>%s · %s</span>'
        '<span class="chip sent">%s</span>'
        '</div>'
        '<div class="title">%s</div>'
        '<div class="summary">%s</div>'
        '%s'
        '<div class="meta"><span>%s · @%s</span>%s</div>'
        '</div>'
    ) % (dup_cls, esc(c.category), esc(c.importance), source_key(c.source), is_dup, is_qw,
         esc(c.category), cat_icon, esc(c.category),
         esc(c.importance), esc(c.importance),
         esc(c.difficulty), esc(c.eta), EMOJI.get(c.sentiment, "\U0001f610"),
         esc(c.title), esc(c.summary), dupnote, esc(c.source), esc(c.author), link)


def render_filters(cards):
    present_src, present_cat = [], []
    for c in cards:
        k = source_key(c.source)
        if k not in present_src:
            present_src.append(k)
        if c.category not in present_cat and c.category in CAT_FILTERS:
            present_cat.append(c.category)

    cat_chips = "".join(
        '<button class="fchip" data-g="cat" data-v="%s">'
        '<span class="msi ck">check</span><span class="msi">%s</span>%s</button>'
        % (cat, CAT_ICON.get(cat, "label"), cat) for cat in present_cat)
    imp_chips = "".join(
        '<button class="fchip" data-g="imp" data-v="%s">'
        '<span class="msi ck">check</span>%s</button>' % (imp, imp)
        for imp in ("high", "medium", "low"))
    src_chips = "".join(
        '<button class="fchip" data-g="src" data-v="%s">'
        '<span class="msi ck">check</span>%s</button>' % (k, SRC_LABELS[k])
        for k in present_src)

    return """<section class="filters">
  <div class="frow"><span class="flabel"><span class="msi">category</span>Type</span>%(cat)s</div>
  <div class="frow"><span class="flabel"><span class="msi">flag</span>Importance</span>%(imp)s</div>
  <div class="frow"><span class="flabel"><span class="msi">database</span>Source</span>%(src)s</div>
  <div class="frow">
    <span class="flabel"><span class="msi">tune</span>View</span>
    <button class="fchip" data-toggle="nodup"><span class="msi ck">check</span>
      <span class="msi">visibility_off</span>Hide duplicates</button>
    <button class="fchip" data-toggle="qw"><span class="msi ck">check</span>
      <span class="msi">bolt</span>Quick wins only</button>
    <input class="fsearch" id="fsearch" type="search" placeholder="Search feedback...">
    <span class="fcount" id="fcount"></span>
  </div>
</section>""" % {"cat": cat_chips, "imp": imp_chips, "src": src_chips}


def render_dashboard(cards, summary, generated_at):
    if not isinstance(summary, dict):
        summary = {}
    mains = [c for c in cards if not c.duplicate_of]
    dups = [c for c in cards if c.duplicate_of]
    mains.sort(key=lambda c: (IMP_ORDER.get(c.importance, 1), -c.dup_count))
    quick_wins = [c for c in mains if c.importance == "high" and c.difficulty == "easy"]
    mood_raw = summary.get("mood")
    if not isinstance(mood_raw, dict):
        mood_raw = {}
    mood = {"frustrated": safe_int(mood_raw.get("frustrated"), 33),
            "neutral": safe_int(mood_raw.get("neutral"), 34),
            "excited": safe_int(mood_raw.get("excited"), 33)}
    total = sum(mood.values())
    if total == 0:
        mood = {"frustrated": 33, "neutral": 34, "excited": 33}
    elif total != 100:
        largest = max(mood, key=mood.get)
        mood = {k: int(round(v * 100 / total)) for k, v in mood.items()}
        mood[largest] += 100 - sum(mood.values())
    bullets = "".join("<li>%s</li>" % esc(b) for b in summary.get("bullets", []))

    qw_html = ""
    if quick_wins:
        rows = "".join(
            '<div class="qw"><div><div class="t">%s</div><div class="s">%s</div></div>'
            '<span class="tag"><span class="msi" style="font-size:15px">bolt</span>quick win</span></div>'
            % (esc(c.title), esc(c.summary))
            for c in quick_wins[:5])
        qw_html = ('<h3 class="sec"><span class="msi" style="color:var(--g-green)">bolt</span>'
                   'Quick wins — high impact, low effort</h3>%s') % rows

    stats = """
    <div class="stats">
      <div class="stat"><span class="msi">inbox</span><div class="n">%(total)d</div><div class="l">Total feedback items</div></div>
      <div class="stat"><span class="msi">priority_high</span><div class="n">%(high)d</div><div class="l">High importance</div></div>
      <div class="stat"><span class="msi">content_copy</span><div class="n">%(dups)d</div><div class="l">Duplicates merged</div></div>
      <div class="stat"><span class="msi">bolt</span><div class="n">%(qw)d</div><div class="l">Quick wins found</div></div>
    </div>""" % {
        "total": len(cards), "high": sum(1 for c in cards if c.importance == "high"),
        "dups": len(dups), "qw": len(quick_wins)}

    cards_html = "".join(render_card(c) for c in mains + dups)

    return """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Radar — every voice, one dashboard</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Roboto:wght@400;500;700&display=swap" rel="stylesheet">
<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@24,400,0,0" rel="stylesheet">
<style>%(css)s</style></head>
<body><div class="wrap">
<header class="top">
  <div class="logo">
    <div class="mark"><span class="msi">radar</span></div>
    <div><h1><b>Radar</b></h1>
    <div class="sub">Every voice, one dashboard · Powered by Google Antigravity SDK</div></div>
  </div>
  <div class="badge">%(when)s</div>
</header>
<section class="brief">
  <h2><span class="msi">coffee</span> Morning Brief</h2>
  <div class="headline">%(headline)s</div>
  <ul>%(bullets)s</ul>
  <div class="moodbar">
    <div style="width:%(fr)d%%;background:var(--g-red)"></div>
    <div style="width:%(ne)d%%;background:var(--g-yellow)"></div>
    <div style="width:%(ex)d%%;background:var(--g-green)"></div>
  </div>
  <div class="moodlabels">
    <span><span class="dot" style="background:var(--g-red)"></span>Frustrated %(fr)d%%</span>
    <span><span class="dot" style="background:var(--g-yellow)"></span>Neutral %(ne)d%%</span>
    <span><span class="dot" style="background:var(--g-green)"></span>Excited %(ex)d%%</span>
  </div>
</section>
%(stats)s
%(qw)s
%(filters)s
<h3 class="sec"><span class="msi">move_to_inbox</span> All feedback — triaged</h3>
<div class="grid">%(cards)s</div>
<div class="empty hidden" id="empty"><span class="msi">search_off</span>
No feedback matches these filters — try clearing some.</div>
<footer>Built with <a href="https://github.com/google-antigravity/antigravity-sdk-python">Google Antigravity SDK</a></footer>
</div>
%(js)s
</body></html>""" % {
        "css": CSS, "when": esc(generated_at),
        "headline": esc(summary.get("headline", "")),
        "bullets": bullets,
        "fr": mood["frustrated"], "ne": mood["neutral"], "ex": mood["excited"],
        "stats": stats, "qw": qw_html, "cards": cards_html,
        "filters": render_filters(cards), "js": FILTER_JS}
