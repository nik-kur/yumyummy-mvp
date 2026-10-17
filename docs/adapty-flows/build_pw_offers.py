#!/usr/bin/env python3
"""After-cancel offers C1 / C2 (placement pw_after_cancel), Welmi design on the flow-A/B blocks:

    python3 build_pw_offers.py      # writes pw_offer_free.json and pw_offer_price.json

Both sell the SAME product (weekly £4.99, 3-day trial; Nikita, Oct 5) and differ only in framing:
C1 "Try it FREE" (trial-led) vs C2 the price itself, big (price-led). No "-50%": there is no
reference price it would be true against (£4.99/week is more per month than either main plan).

One screen: full-bleed Costa photo (media/bg_costa_dark: bottom darkened + scan bubble baked in),
bottom-pinned gradient panel with the chip "Last offer, it's FREE" (14pt), the big offer line, the
price line, one Continue, "No commitment · Cancel anytime", links. No back button, no "instead of"
line (Nikita, Oct 2). C1 = weekly £2.99 + 3 days ("40% OFF"), C2 = weekly £4.99 + 3 days ("Try it FREE").
"""
import copy
import json
import os

import build_flows as bf
import build_pw_a_v2 as a
import build_pw_b as b
import build_pw_tests as t

fk, T, Var = bf.fk, bf.T, bf.Var
HERE = bf.HERE
P_W299 = '394d6da2-9b85-4674-9fd2-f172c0bad724'     # ai.yumyummy.app.weekly2.99.3d
P_W499 = 'b14a44af-2a10-4f2a-9889-7e587cb6d149'     # ai.yumyummy.app.weekly_upd (£4.99)
EXTRA_COLORS = b.EXTRA_COLORS + [('lime', 'Offer lime', '#D8FF5E')]


def offer_screen(sid, pid, big, sub_parts, prefix):
    bf.ids(prefix)
    bg = bf.media('bg_costa_dark')
    attach = fk.product([], product_id=pid, group_id='offer', default=True,
                        caption='Product attach point (hidden)')
    attach['props']['visibility'] = fk.hidden()
    chip = fk.stack([bf.pill([T("Last offer", 'in_badge', 'white', width='hug')],
                             'card_dark', border_id='white_dim', pad_v=7, pad_h=16, caption='Chip')],
                    align_h='center', caption='Chip row')
    big_t = T(big, 'fr_stat', 'lime', align='center', margin=fk.pad(12, 0, 0, 4), caption='Offer')
    sub = T(sub_parts, 'in_body', 'white', align='center', caption='Price line')
    buy = {'id': 'act_buy', 'type': 'purchase',
           'payload': {'product': {'type': 'const', 'value': {'id': pid}}}}
    bottom = fk.stack([a.cta('Start My 3-Day Free Trial', [buy], caption='CTA purchase'),
                       T('No commitment · Cancel anytime', 'in_caption', 'white_dim', align='center'),
                       t.legal_links('white_dim')], gap=12, margin=fk.pad(26, 0, 0, 0),
                      caption='Bottom block')
    panel = fk.stack([attach, chip, big_t, sub, bottom], padding=fk.pad(130, a.GUTTER, a.GUTTER, 52),
                     fill_=fk.fill(layers=fk.gradient(180, ('#0B0A09', 0, 0), ('#0B0A09', 0.75, 18),
                                                      ('#0B0A09', 0.95, 40), ('#0B0A09', 1, 100))),
                     caption='Offer panel')
    spacer = fk.stack([], fixed_h=1, caption='Photo (spacer)')
    return fk.screen(sid, [spacer, panel], caption=sid,
                     fill_=fk.image_fill(bg['url'], media_id=bg['media_id'], preview=bg['preview']),
                     padding=fk.pad(0, 0, 0, 0), gap=0, distribution='space-between',
                     scrollable=False, safe_area=False, status_bar_theme='dark',
                     selectable_groups=[{'id': 'offer', 'type': 'product'}])


def finish(screens):
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
    cfg['_meta']['fonts'] = copy.deepcopy(src['_meta']['fonts'])
    return cfg


def build_free():
    pv = Var(f'{P_W499}.prod_price')
    return finish([offer_screen('PW_OFFER_FREE', P_W499, 'Try it FREE',
                                ['3 days free, then ', pv, ' per week'], 'el_of')])


def build_price():
    pv = Var(f'{P_W499}.prod_price')
    # "50% OFF" is Nikita's call (Oct 5) after the no-reference-price warning.
    return finish([offer_screen('PW_OFFER_PRICE', P_W499, '50% OFF',
                                ['3 days free, then ', pv, ' per week'], 'el_op')])


if __name__ == '__main__':
    for name, fn in (('pw_offer_free.json', build_free), ('pw_offer_price.json', build_price)):
        cfg = fn()
        with open(os.path.join(HERE, name), 'w') as f:
            json.dump(cfg, f, indent=1, ensure_ascii=False)
        print(f'{name}: {len(cfg["screens"])} screen')
