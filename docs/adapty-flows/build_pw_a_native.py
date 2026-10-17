#!/usr/bin/env python3
"""Flow A, "native blocks" variant: screens 1-2 are shared with pw_calai (build_pw_a_v2), screen 3 is
assembled from the builder's own Add-element library (component-catalog.json: prod-horizontal-list,
badge, btn-sub) plus a progress-coded timeline, with our theme mapped onto the catalog's styles.
v2 (Oct 5, after device QA): no laurels under the headline, Welmi-short timeline copy, step 1 marked
done, per-month figure on both cards, rating laurel under the CTA, space-between layout.

    python3 build_pw_a_native.py      # writes pw_a_native.json

The catalog blocks are the same stack/text/icon/product primitives as everything else — the point
of this variant is to keep the builder's proportions (card padding 16, radius 12, 1px border,
centred text, 16pt gaps) untouched and only swap copy, products, colours and fonts.
"""
import copy
import json
import os

import build_flows as bf
import build_pw_a_v2 as a
import build_single as bs

fk, T, Var = bf.fk, bf.T, bf.Var
HERE = bf.HERE
CATALOG = os.path.join(HERE, '..', 'adapty-skills', 'skills', 'flow-generator', 'references',
                       'component-catalog.json')

COLOR_MAP = {'gray-800': 'ink', 'gray-500': 'ink_faint', 'gray-100': 'hairline',
             'white': 'surface', 'accent': 'terracotta'}
PRESET_MAP = {'h3': 'in_title', 'body': 'in_small', 'button-label': 'in_body_strong',
              'caption': 'in_caption'}


def catalog(key):
    comps = json.load(open(CATALOG))['components']
    if isinstance(comps, list):
        comps = {c['id']: c for c in comps}
    return comps[key]


def restyle(node, *, colors=COLOR_MAP, presets=PRESET_MAP):
    """Map the catalog's default colour ids / font presets onto our theme, in place."""
    props = node.get('props') or {}
    if isinstance(props.get('color'), dict) and props['color'].get('colorId') in colors:
        props['color']['colorId'] = colors[props['color']['colorId']]
    if isinstance(props.get('font'), dict) and props['font'].get('preset') in presets:
        props['font']['preset'] = presets[props['font']['preset']]
    for f in props.get('fill') or []:
        c = f.get('color') or {}
        if c.get('colorId') in colors:
            c['colorId'] = colors[c['colorId']]
    b = props.get('border') or {}
    if isinstance(b.get('color'), dict) and b['color'].get('colorId') in colors:
        b['color']['colorId'] = colors[b['color']['colorId']]
    for st in (node.get('propsByState') or {}).values():
        bb = st.get('border') or {}
        if isinstance(bb.get('color'), dict) and bb['color'].get('colorId') in colors:
            bb['color']['colorId'] = colors[bb['color']['colorId']]
    for ch in node.get('_children') or []:
        restyle(ch, colors=colors, presets=presets)
    return node


def texts(node, out=None):
    out = [] if out is None else out
    if node.get('type') == 'text':
        out.append(node)
    for ch in node.get('_children') or []:
        texts(ch, out)
    return out


def icons(node, out=None):
    out = [] if out is None else out
    if node.get('type') == 'icon':
        out.append(node)
    for ch in node.get('_children') or []:
        icons(ch, out)
    return out


def timeline_v2():
    """Cal AI timeline, progress-coded: step 1 is done (filled terracotta chip, white icon, soft
    terracotta rail), steps 2-3 are upcoming (hairline chips, faint icons, hairline rail). Copy is
    Welmi-short; the billing date needs a TRIAL_END_DATE custom tag from the app (next build)."""
    rows = [
        ('LockOpen', True, 'Today', 'Unlock AI food calorie tracking'),
        ('Bell', False, 'In 2 Days - Reminder', "We'll send you a reminder that your trial is ending soon"),
        ('Crown', False, 'In 3 Days - Billing Starts', "You'll be charged unless you cancel before"),
    ]
    out = []
    for i, (icon, done, title, desc) in enumerate(rows):
        last = i == len(rows) - 1
        chip = fk.stack([fk.icon(icon, size_pt=15, color_id='white' if done else 'ink_faint', weight='fill')],
                        fixed_w=30, fixed_h=30, align_h='center', align_v='center',
                        fill_=fk.fill('terracotta' if done else 'hairline'), corner=fk.radius(15),
                        position=fk.absolute(top=0, left=0), caption='Step icon')
        kids = [chip]
        if not last:
            kids.append(fk.stack([], fixed_w=3, height='auto',
                                 fill_=fk.fill('terracotta_soft' if done else 'hairline'),
                                 position=fk.absolute(top=34, left=14, bottom=-2), caption='Rail'))
        kids.append(fk.stack([T(title, 'in_body_strong', 'ink'), T(desc, 'in_small', 'ink_muted')],
                             gap=2, padding=fk.pad(3, 44, 0, 0 if last else 20), caption='Step text'))
        out.append(fk.stack(kids, direction='horizontal', caption='Step'))
    return fk.stack(out, margin=fk.pad(22, 0, 0, 0), caption='Timeline')


def plans_v2():
    """Catalog prod-horizontal-list, restyled. Both cards lead with the per-month figure; the
    caption says how it is billed (Nikita, Oct 5)."""
    pv = lambda pid, f: Var(f'{pid}.{f}')  # noqa: E731
    items = [
        {'product_id': a.P_MONTHLY, 'title': fk.rich('Monthly'),
         'details': fk.rich(pv(a.P_MONTHLY, 'prod_price'), ' /mo')},
        {'product_id': a.P_YEARLY, 'title': fk.rich('Yearly'),
         'details': fk.rich(pv(a.P_YEARLY, 'prod_price_per_month'), ' /mo')},
    ]
    node = fk.from_catalog(catalog('prod-horizontal-list'), group_id='plans', items=items)[0]
    restyle(node)
    cards = node['_children']
    for card in cards:
        card['props']['layout']['distribution'] = {'type': 'gap', 'gap': 4}
        card['props']['padding'] = fk.pad(14, 12, 12, 14)
        card['props']['borderRadius'] = fk.radius(16)
        card['propsByState']['selected']['border'] = {'width': 2, 'color': fk.color('ink')}
        card['propsByState']['selected']['fill'] = fk.fill('card_sel')   # Welmi: the chosen card also lightens
        title, details = texts(card)[:2]
        title['props']['font'] = {'preset': 'in_small'}
        title['props']['color'] = {'type': 'color-style', 'colorId': 'ink_muted'}
        details['props']['font'] = {'preset': 'in_title'}
    cards[0]['props']['default'] = False
    cards[1]['props']['default'] = True
    cards[0]['_children'].append(T('billed monthly', 'in_caption', 'ink_muted', align='center'))
    cards[1]['_children'].append(T(['only ', pv(a.P_YEARLY, 'prod_price'), ' per year'], 'in_caption',
                                   'ink_muted', align='center'))
    badge = fk.from_catalog(catalog('badge'), fills={'label': fk.rich('🎁 SAVE 58%')})[0]
    restyle(badge, colors={'accent': 'done_green', 'white': 'white'})
    badge['props']['fill'] = fk.fill('done_green')
    badge['props']['position'] = fk.absolute(top=-14, right=10)
    for t in texts(badge):
        t['props']['font'] = {'preset': 'in_caption_strong'}
        t['props']['color'] = {'type': 'color-style', 'colorId': 'white'}
    cards[1]['_children'].append(badge)
    node['caption'] = 'Plan cards (catalog prod-horizontal-list)'
    node['props']['layout']['distribution'] = {'type': 'gap', 'gap': 10}
    return node


def native_cta():
    node = fk.from_catalog(catalog('btn-sub'), fills={'label': fk.rich('Start My 3-Day Free Trial')})[0]
    restyle(node)
    node['props']['height'] = fk.size('fixed', a.CTA_H)
    node['props']['borderRadius'] = fk.radius(14)
    for t in texts(node):
        t['props']['font'] = {'preset': 'in_button'}
        t['props']['color'] = {'type': 'color-style', 'colorId': 'white'}
    node['interactions'] = [{'id': 'int' + node['id'][2:], 'trigger': 'tap',
                             'actions': [fk.purchase('plans', 'act_buy')]}]
    node['caption'] = 'CTA purchase (catalog btn-sub)'
    return node


def rating_laurel():
    """Cal AI-style laurel under the CTA: '{RATING} ★' over 'avg App Store rating', a gold branch
    on each side (media/laurel_left|right, generated on the page colour so no box shows)."""
    def branch(name):
        m = bf.media(name)
        return fk.image(m['url'], media_id=m['media_id'], preview=m['preview'], fit='fit',
                        fixed_w=34, fixed_h=54, caption=name)
    col = fk.stack([T([Var('var_RATING'), ' ★'], 'in_rating', 'ink', align='center', width='hug'),
                    T('avg App Store rating', 'in_small', 'ink_muted', align='center', width='hug')],
                   width='hug', gap=0, align_h='center', caption='Rating text')
    return fk.stack([branch('laurel_left'), col, branch('laurel_right')], direction='horizontal',
                    gap=12, align_h='center', align_v='center', caption='Rating laurel')


def hero_headline(color):
    """Two mutually exclusive headlines. When the app passed a target weight (TARGET_WEIGHT non-empty):
    'Reach 80 kg by Jan 11 / Start for FREE today.' — the user's own numbers from onboarding. Otherwise
    the app's HERO_LINE fallback ('Your zone: 1,800 kcal' / 'Your plan is ready'). Builder preview shows
    the fallback because TARGET_WEIGHT has no default."""
    has_target = fk.when(fk.not_empty(fk.ref('var_TARGET_WEIGHT')))
    no_target = fk.when(fk.eq(fk.ref('var_TARGET_WEIGHT'), fk.lit('')))
    goal = T(['Reach ', Var('var_TARGET_WEIGHT'), ' by ', Var('var_TARGET_DATE'), '\nStart for FREE today.'],
             'fr_h1', color, align='center', visibility=has_target, caption='Headline (target)')
    fallback = T([Var('var_HERO_LINE'), '\nStart for FREE today.'], 'fr_h1', color, align='center',
                 visibility=no_target, caption='Headline (fallback)')
    return fk.stack([goal, fallback], margin=fk.pad(6, 0, 0, 0), caption='Headline')


def a3_native():
    bf.ids('el_a3')
    h1 = hero_headline('ink')
    bottom = fk.stack([a.ok_line('No Payment Due Now'), native_cta(), rating_laurel(), a.links_row()],
                      gap=14, caption='Bottom block')   # links yes, disclosure no (Oct 5)
    header = fk.stack([a.back_row(), h1], caption='Header')
    tl = timeline_v2(); tl['props']['margin'] = fk.pad(0, 0, 0, 0)
    # Four root children + space-between (scroll off): the free height splits into three equal
    # gaps (header/timeline, timeline/cards, cards/bottom) so no single void reads as a mistake on
    # a Plus/Max; a footer would need scrolling on (patterns.md rule 0).
    return a.screen('PW_A3_plans', [header, tl, plans_v2(), bottom], scroll=False, spread=True,
                    groups=[{'id': 'plans', 'type': 'product'}])


# Clips uploaded through the builder UI for THIS flow (pw_a_native) — override pw_calai's.
VIDEO_OVERRIDES = {
    'el_a1_002V': 'f34670a6-b467-4765-b67f-cc54c6ae6bc6',   # paywall_demo_scan_loop_v6.mp4 (5.9 s: one HLS segment, faster start, 2026-10-05)
}


def build():
    a.POSTER = 'demo_poster'
    screens = [a.a1_try(), a.a2_reminder(), a3_native()]
    meta = {}
    for s in screens:
        if s.get('products'):
            meta.update(fk.predeclare(s['id'], [(p['id'], p.get('offerId')) for p in s['products']]))
    cfg = fk.config(screens=screens, colors=bf.COLORS, typography=bf.TYPO,
                    variables=bf.CUSTOM_VARS, meta_screens=meta)
    src = json.load(open(os.path.join(HERE, 'pw_single_monthly.working.json')))['config']
    cfg['theme'] = copy.deepcopy(src['theme'])
    for cid, name, hx in a.EXTRA_COLORS + [('card_sel', 'Card selected', '#F4E8D6')]:
        cfg['theme']['colors'].append({'id': cid, 'name': name, 'light': {'hex': hx}, 'dark': {'hex': hx}})
    cfg['_meta']['fonts'] = copy.deepcopy(src['_meta']['fonts'])
    base = next(e for e in cfg['theme']['typography'] if e['id'] == 'in_title')
    rating = copy.deepcopy(base); rating['id'] = 'in_rating'; rating['name'] = 'Inter 700 · Rating 24/28'
    rating['settings'].update(size=24, weight='bold', lineHeight=28)
    cfg['theme']['typography'].append(rating)
    a.attach_videos(cfg)
    a.VIDEO_URLS.update(VIDEO_OVERRIDES); a.attach_videos(cfg)   # this flow's own clips win
    return cfg


if __name__ == '__main__':
    cfg = build()
    out = os.path.join(HERE, 'pw_a_native.json')
    with open(out, 'w') as f:
        json.dump(cfg, f, indent=1, ensure_ascii=False)
    n = sum(1 for _ in json.dumps(cfg).split('"type": "') ) - 1
    print(f'pw_a_native: {len(cfg["screens"])} screens -> {out}')
