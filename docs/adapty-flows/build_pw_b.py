#!/usr/bin/env python3
"""Flow B = Welmi 3-step paywall, rebuilt on the flow-A blocks (build_pw_a_v2 / build_pw_a_native):

    python3 build_pw_b.py      # writes pw_welmi.json (flow a31d5e53-47e5-4f10-82ce-4334941894ca)

  B1  "We want you to try YumYummy for free" + progress timeline + "No payment for now" + "Try for free"
  B2  the shared reminder screen (bell clip), renamed
  B3  Welmi paywall: full-bleed photo (media/bg_joe = Joe & The Juice shake, scan bubble), dark gradient,
      personalised headline, two dark plan cards (per-month figure + billing caption, SAVE 58%),
      "Continue" CTA, rating laurel (transparent branches), short disclosure, links. Nothing below the fold,
      scroll off, content pinned to the bottom so the photo absorbs the extra height on a Plus/Max.
v2 (Oct 5): custom tags as variable nodes, Welmi-short timeline copy, step 1 done, no laurels/reviews
below the fold, no literal price in the CTA (the builder cannot read an App Store intro price).
"""
import copy
import json
import os

import build_flows as bf
import build_pw_a_v2 as a
import build_pw_a_native as n
import build_pw_tests as t

fk, T, Var = bf.fk, bf.T, bf.Var
HERE = bf.HERE
EXTRA_COLORS = a.EXTRA_COLORS + [
    ('black', 'Black', '#0B0A09'),
    ('card_dark', 'Dark card', '#1C1917'),
    ('white_dim', 'White dim', '#D9D4CC'),
    ('card_dark_sel', 'Dark card selected', '#302B27'),
]


def b1_try():
    bf.ids('el_b1')
    h1 = a.headline('We want you to\ntry YumYummy for free', 58)
    tl = n.timeline_v2()
    tl['props']['margin'] = fk.pad(0, 0, 0, 0)
    bottom = fk.stack([a.ok_line('No payment for now'),
                       a.cta('Try for free', [fk.navigate('PW_B2_reminder', 'act_next')])],
                      gap=14, caption='Bottom block')
    return a.screen('PW_B1_try', [h1, tl, bottom], scroll=False, spread=True)


def b2_reminder():
    scr = a.a2_reminder()
    s = json.dumps(scr).replace('PW_A2_reminder', 'PW_B2_reminder').replace('PW_A3_plans', 'PW_B3_plans')
    return json.loads(s)


def plan_card_dark(key, pid, *, default, badge=None):
    pv = lambda f: Var(f'{pid}.{f}')  # noqa: E731
    if key == 'yearly':
        lines = [T('Yearly', 'in_small', 'white_dim', align='center'),
                 T([pv('prod_price_per_month'), ' /mo'], 'in_title', 'white', align='center'),
                 T(['only ', pv('prod_price'), ' per year'], 'in_caption', 'white_dim', align='center')]
    else:
        lines = [T('Monthly', 'in_small', 'white_dim', align='center'),
                 T([pv('prod_price'), ' /mo'], 'in_title', 'white', align='center'),
                 T('billed monthly', 'in_caption', 'white_dim', align='center')]
    kids = [fk.stack(lines, gap=4, align_h='center', caption='Plan text')]
    if badge:
        kids.append(bf.pill([T(badge, 'in_caption_strong', 'white', width='hug')], 'done_green',
                            pad_v=3, pad_h=9, caption='Badge', position=fk.absolute(top=-14, right=10)))
    card = fk.product(kids, product_id=pid, group_id='plans', default=default,
                      padding=fk.pad(14, 12, 12, 14), fill_=fk.fill('card_dark'),
                      corner=fk.radius(16), border='white_dim', border_width=1, align_h='center',
                      caption=f'Plan {key}')
    fk.on_selected(card, fill=fk.fill('card_dark_sel'), border={'color': fk.color('white'), 'width': 2})
    return card


def rating_laurel_dark():
    def branch(name):
        m = bf.media(name)
        return fk.image(m['url'], media_id=m['media_id'], preview=m['preview'], fit='fit',
                        fixed_w=34, fixed_h=54, caption=name)
    col = fk.stack([T([Var('var_RATING'), ' ★'], 'in_rating', 'white', align='center', width='hug'),
                    T('avg App Store rating', 'in_small', 'white_dim', align='center', width='hug')],
                   width='hug', gap=0, align_h='center', caption='Rating text')
    return fk.stack([branch('laurel_left_t'), col, branch('laurel_right_t')], direction='horizontal',
                    gap=12, align_h='center', align_v='center', caption='Rating laurel')


def b3_plans():
    bf.ids('el_b3')
    bg = bf.media('bg_joe_dark')   # bottom 60% darkened in the asset: a 2-layer fill is ignored on device
    h1 = n.hero_headline('white')
    h1['props']['margin'] = fk.pad(0, 0, 0, 0)
    cards = fk.stack([plan_card_dark('monthly', a.P_MONTHLY, default=False),
                      plan_card_dark('yearly', a.P_YEARLY, default=True, badge='🎁 SAVE 58%')],
                     direction='horizontal', gap=10, margin=fk.pad(22, 0, 0, 0), caption='Plan cards')
    bottom = fk.stack([T('✓ No commitment. Cancel anytime', 'in_body_strong', 'white', align='center',
                         caption='No commitment line'),
                       a.cta('Start My 3-Day Free Trial', [fk.purchase('plans', 'act_buy')], caption='CTA purchase'),
                       rating_laurel_dark(), t.legal_links('white_dim')], gap=14,
                      margin=fk.pad(22, 0, 0, 0), caption='Bottom block')
    panel = fk.stack([h1, cards, bottom], padding=fk.pad(110, a.GUTTER, a.GUTTER, 52),   # 52 = 24 + home-indicator inset (safe area off)
                     fill_=fk.fill(layers=fk.gradient(180, ('#0B0A09', 0, 0), ('#0B0A09', 0.75, 18),
                                                      ('#0B0A09', 0.95, 40), ('#0B0A09', 1, 100))),
                     caption='Gradient panel')
    spacer = fk.stack([], fixed_h=1, caption='Photo (spacer)')
    return fk.screen('PW_B3_plans', [spacer, panel], caption='PW_B3_plans',
                     fill_=fk.image_fill(bg['url'], media_id=bg['media_id'], preview=bg['preview']),
                     padding=fk.pad(0, 0, 0, 0), gap=0, distribution='space-between',
                     scrollable=False, safe_area=False, status_bar_theme='dark',
                     selectable_groups=[{'id': 'plans', 'type': 'product'}])


def build():
    screens = [b1_try(), b2_reminder(), b3_plans()]
    meta = {}
    for s in screens:
        if s.get('products'):
            meta.update(fk.predeclare(s['id'], [(p['id'], p.get('offerId')) for p in s['products']]))
    cfg = fk.config(screens=screens, colors=bf.COLORS, typography=bf.TYPO,
                    variables=bf.CUSTOM_VARS, meta_screens=meta)
    src = json.load(open(os.path.join(HERE, 'pw_single_monthly.working.json')))['config']
    cfg['theme'] = copy.deepcopy(src['theme'])
    for cid, name, hx in EXTRA_COLORS:
        cfg['theme']['colors'].append({'id': cid, 'name': name, 'light': {'hex': hx}, 'dark': {'hex': hx}})
    base = next(e for e in cfg['theme']['typography'] if e['id'] == 'in_title')
    rating = copy.deepcopy(base); rating['id'] = 'in_rating'; rating['name'] = 'Inter 700 · Rating 24/28'
    rating['settings'].update(size=24, weight='bold', lineHeight=28)
    cfg['theme']['typography'].append(rating)
    cfg['_meta']['fonts'] = copy.deepcopy(src['_meta']['fonts'])
    a.attach_videos(cfg)   # the bell clip on B2 (same element id as A2)
    return cfg


if __name__ == '__main__':
    cfg = build()
    out = os.path.join(HERE, 'pw_welmi.json')
    with open(out, 'w') as f:
        json.dump(cfg, f, indent=1, ensure_ascii=False)
    print(f'pw_welmi: {len(cfg["screens"])} screens -> {out}')
