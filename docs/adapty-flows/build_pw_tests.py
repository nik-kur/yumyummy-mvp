#!/usr/bin/env python3
"""Build the October 2026 paywall test flows (replicas of Cal AI and Welmi) + after-cancel offers.

    python3 build_pw_tests.py        # writes pw_calai.json, pw_welmi.json, pw_offer_299.json, pw_offer_499.json

Theme + fonts are lifted from pw_single_monthly.working.json (same app, fonts already mapped in the
builder); a few extra colours are appended for the dark (Welmi) screens. Custom tags HERO_LINE /
RATING / USERS come from the app exactly as in pw_main.

Video: the Cal AI screen 1 carries a real `video` element with no source — upload the clip in the
builder (there is no CLI path for clips).
"""
import copy
import json
import os

import build_flows as bf
import build_single as bs

fk, T, Var = bf.fk, bf.T, bf.Var
HERE = bf.HERE

# Adapty product UUIDs (products list, 2026-10-02)
P_YEARLY = '7cbbdae3-6caa-4862-b05a-33960863c2f1'   # ai.yumyummy.app.yearly49.99.3d (£49.99, 3-day trial)
P_MONTHLY = 'cf5874b1-a1c2-46cc-900a-2ee04db8ddde'  # ai.yumyummy.app.monthly (£9.99, 3-day trial)
P_W299 = '394d6da2-9b85-4674-9fd2-f172c0bad724'     # ai.yumyummy.app.weekly2.99.3d
P_W499 = 'b14a44af-2a10-4f2a-9889-7e587cb6d149'     # ai.yumyummy.app.weekly_upd (£4.99)

EXTRA_COLORS = [
    ('lime', 'Offer lime', '#D8FF5E'),
    ('black', 'Black', '#0B0A09'),
    ('card_dark', 'Dark card', '#1C1917'),
    ('white_dim', 'White dim', '#D9D4CC'),
    ('red_badge', 'Red badge', '#D32F2F'),
    ('bell_gray', 'Bell gray', '#CFD8DC'),
]


def legal_links(color='ink_faint'):
    sep = lambda: T(' · ', 'in_caption', color, width='hug')  # noqa: E731
    return fk.stack([
        T('Terms', 'in_caption', color, width='hug',
          actions=[fk.open_url(bs.TERMS_URL, external=True, action_id='act_terms')], caption='Terms'),
        sep(),
        T('Privacy', 'in_caption', color, width='hug',
          actions=[fk.open_url(bs.PRIVACY_URL, external=True, action_id='act_privacy')],
          caption='Privacy'),
        sep(),
        T('Restore', 'in_caption', color, width='hug', actions=[fk.restore('act_restore')],
          caption='Restore'),
    ], direction='horizontal', align_h='center', align_v='center', caption='Legal links')


def cta(label, actions, fill_id='terracotta', caption='CTA'):
    return fk.stack([T(label, 'in_button', 'white', align='center')], fixed_h=54,
                    fill_=fk.fill(fill_id), corner=fk.radius(14), align_h='center',
                    align_v='center', padding=fk.pad(0, 24, 24, 0), actions=actions,
                    caption=caption)


def ok_line(text, color='ink'):
    return T('✓ ' + text, 'in_body_strong', color, align='center', caption='No payment line')


def timeline(rows, color_bg='terracotta_soft', color_icon='terracotta', text_color='ink',
             sub_color='ink_muted', caption='Timeline'):
    """Cal AI / Welmi timeline: icon circles joined by a thin rail, bold title + muted line."""
    out = []
    for i, (icon, title, desc, gray) in enumerate(rows):
        last = i == len(rows) - 1
        chip = fk.stack([fk.icon(icon, size_pt=15, color_id='ink_faint' if gray else color_icon,
                                 weight='fill')],
                        fixed_w=30, fixed_h=30, align_h='center', align_v='center',
                        fill_=fk.fill('hairline' if gray else color_bg), corner=fk.radius(15),
                        position=fk.absolute(top=0, left=0), caption='Step icon')
        kids = [chip]
        if not last:
            kids.append(fk.stack([], fixed_w=3, height='auto', fill_=fk.fill(color_bg),
                                 position=fk.absolute(top=34, left=14, bottom=0),
                                 caption='Rail'))
        kids.append(fk.stack([T(title, 'in_body_strong', text_color),
                              T(desc, 'in_caption', sub_color)], gap=2,
                             padding=fk.pad(2, 42, 0, 0 if last else 18)))
        out.append(fk.stack(kids, direction='horizontal', caption='Step'))
    return fk.stack(out, caption=caption)


def back_row():
    return fk.stack([bf.back_button()], direction='horizontal', align_v='center',
                    margin=fk.pad(8, 0, 0, 4), caption='Back row')


def screen(sid, nodes, *, scroll, spread=False, groups=(), fill_=None, status='light',
           pad_top=0, pad_bottom=16):
    return fk.screen(sid, nodes, caption=sid, fill_=fill_ or fk.fill('bg'),
                     padding=fk.pad(pad_top, bf.GUTTER, bf.GUTTER, pad_bottom), gap=0,
                     distribution='space-between' if spread else None, scrollable=scroll,
                     safe_area=True, status_bar_theme=status, selectable_groups=list(groups))


# ------------------------------------------------------------------------------------------------
# Shared screens
# ------------------------------------------------------------------------------------------------

def reminder_screen(sid, next_sid, brand_cta=True):
    """Welmi screen 2, 1:1: three-line headline, grey bell with a red «1», no payment line, CTA.
    The CTA should ALSO carry the builder's «Request permission → push» action: add it in the
    builder on the CTA (no CLI shape for it yet)."""
    h1 = T("We'll send you a\nreminder before your\nfree trial ends", 'fr_h1', 'ink',
           align='center', margin=fk.pad(8, 0, 0, 0))
    bell = fk.icon('Bell', size_pt=120, color_id='bell_gray', weight='fill')
    badge = fk.stack([T('1', 'in_title', 'white', align='center', width='hug')],
                     fixed_w=40, fixed_h=40, align_h='center', align_v='center',
                     fill_=fk.fill('red_badge'), corner=fk.radius(20),
                     position=fk.absolute(top=0, right=10), caption='Badge 1')
    bell_box = fk.stack([bell, badge], fixed_w=170, fixed_h=150, align_h='center',
                        align_v='center', caption='Bell')
    bell_wrap = fk.stack([bell_box], align_h='center', caption='Bell wrap')
    bottom = fk.stack([ok_line('No payment for now'),
                       cta('Continue for FREE', [fk.navigate(next_sid, 'act_next')],
                           caption='CTA (add Request permission: push in builder)'),
                       legal_links()], gap=14, caption='Bottom')
    return screen(sid, [fk.stack([back_row(), h1], caption='Top'), bell_wrap, bottom],
                  scroll=False, spread=True)


def plan_card_calai(key, pid, *, default, badge=None):
    """Cal AI plan card: name, big price, check circle on the right; yearly carries a green badge."""
    ring_chk = fk.icon('Check', size_pt=12, color_id='white', weight='bold')
    ring_chk['props']['opacity'] = 0
    fk.on_selected(ring_chk, opacity=100)
    ring = fk.stack([ring_chk], fixed_w=22, fixed_h=22, align_h='center', align_v='center',
                    corner=fk.radius(11), border='hairline_strong', border_width=1.5,
                    position=fk.absolute(top=14, right=12), caption='Check')
    fk.on_selected(ring, fill=fk.fill('ink'),
                   border={'color': fk.color('ink'), 'style': 'solid', 'width': 1.5})
    pv = lambda f: Var(f'{pid}.{f}')  # noqa: E731
    if key == 'yearly':
        lines = [T('Yearly', 'in_caption', 'ink_muted'),
                 T([pv('prod_price')], 'in_title', 'ink'),
                 T([pv('prod_price_per_month'), '/mo'], 'in_caption', 'ink_muted')]
    else:
        lines = [T('Monthly', 'in_caption', 'ink_muted'),
                 T([pv('prod_price'), ' /mo'], 'in_title', 'ink')]
    kids = [fk.stack(lines, gap=2, padding=fk.pad(0, 30, 0, 0), caption='Plan text'), ring]
    if badge:
        kids.append(bf.pill([T(badge, 'in_caption_strong', 'white', width='hug')], 'done_green',
                            pad_v=2, pad_h=8, caption='Badge',
                            position=fk.absolute(top=-11, right=10)))
    card = fk.product(kids, product_id=pid, group_id='plans', default=default,
                      padding=fk.pad(14, 12, 12, 14), fill_=fk.fill('surface'),
                      corner=fk.radius(16), border='hairline_strong', border_width=1.5,
                      caption=f'Plan {key}')
    fk.on_selected(card, border={'color': fk.color('ink'), 'style': 'solid', 'width': 2})
    return card


def plan_card_welmi(key, pid, *, default, badge=None):
    """Welmi card on the dark photo paywall: white text on a dark translucent card."""
    pv = lambda f: Var(f'{pid}.{f}')  # noqa: E731
    if key == 'yearly':
        lines = [T('Yearly', 'in_caption', 'white_dim'),
                 T([pv('prod_price_per_month'), '/mo'], 'in_title', 'white'),
                 T(['Only ', pv('prod_price'), '/year'], 'in_caption', 'white_dim',
                   margin=fk.pad(6, 0, 0, 0))]
    else:
        lines = [T('Monthly', 'in_caption', 'white_dim'),
                 T([pv('prod_price'), '/mo'], 'in_title', 'white'),
                 T('Billed monthly', 'in_caption', 'white_dim', margin=fk.pad(6, 0, 0, 0))]
    kids = [fk.stack(lines, gap=2, caption='Plan text')]
    if badge:
        kids.append(bf.pill([T(badge, 'in_caption_strong', 'white', width='hug')], 'done_green',
                            pad_v=2, pad_h=8, caption='Badge',
                            position=fk.absolute(top=-11, right=10)))
    card = fk.product(kids, product_id=pid, group_id='plans', default=default,
                      padding=fk.pad(14, 12, 12, 14), fill_=fk.fill('card_dark'),
                      corner=fk.radius(16), border='white_dim', border_width=1,
                      caption=f'Plan {key}')
    fk.on_selected(card, border={'color': fk.color('white'), 'style': 'solid', 'width': 2})
    return card


def below_fold(dark=False):
    """Review + before/after placeholder, shown only on scroll."""
    ink, muted = ('white', 'white_dim') if dark else ('ink', 'ink_muted')
    quote = bf.card([T(bf.Span('“Finally started losing — the numbers were just right.”',
                                italic=True), 'in_body', ink, align='center'),
                     T('Maria · −4 kg in 6 weeks', 'in_caption', muted, align='center')],
                    gap=4, pad=14, bw=1, fill_id='card_dark' if dark else 'surface',
                    border='white_dim' if dark else 'hairline', align_h='center',
                    caption='Testimonial')
    ba = fk.image(fk.PLACEHOLDER, fixed_h=220, corner=fk.radius(16),
                  caption='Before / after photo (upload in builder)')
    return fk.stack([quote, ba], gap=12, margin=fk.pad(20, 0, 0, 0), caption='Below the fold')


# ------------------------------------------------------------------------------------------------
# Flow A — Cal AI replica
# ------------------------------------------------------------------------------------------------

def a1_try():
    bf.ids('el_a1')
    h1 = T('We want you to\ntry YumYummy for free.', 'fr_h1', 'ink', align='center',
           margin=fk.pad(40, 0, 0, 0))
    phone = fk.stack([fk.video(fixed_h=430, corner=fk.radius(28),
                               caption='Demo video (upload chips_scan loop in builder)')],
                     fixed_w=226, padding=fk.pad(8, 8, 8, 8), fill_=fk.fill('ink'),
                     corner=fk.radius(36), caption='Phone frame')
    mid = fk.stack([phone], align_h='center', caption='Mockup')
    bottom = fk.stack([ok_line('No Payment Due Now'),
                       cta('Try Now', [fk.navigate('PW_A2_reminder', 'act_next')]),
                       legal_links()], gap=14, caption='Bottom')
    return screen('PW_A1_try', [h1, mid, bottom], scroll=False, spread=True)


def a3_plans():
    bf.ids('el_a3')
    h1 = T(['<HERO_LINE/>', '. Start for FREE today.'], 'fr_h1', 'ink', align='center',
           margin=fk.pad(4, 0, 0, 12), caption='Headline (HERO_LINE from the app)')
    laurels = [bf.pill([T(t, 'in_caption', 'ink_muted', width='hug')], 'surface',
                       border_id='hairline', caption='Laurel')
               for t in ('★ <RATING/> rating', '<USERS/>+ trackers', '✓ Verified data')]
    laurel_rows = fk.stack([
        fk.stack(laurels[:2], direction='horizontal', gap=8, align_h='center'),
        fk.stack(laurels[2:], direction='horizontal', gap=8, align_h='center'),
    ], gap=8, margin=fk.pad(0, 0, 0, 16), caption='Laurels')
    tl = timeline([
        ('LockOpen', 'Today', "Unlock all the app's features: photo, voice and text logging "
                              'with verified sources.', False),
        ('Bell', 'In 2 Days - Reminder', "We'll send you a reminder that your trial is ending "
                                         "soon if you've allowed us to notify you.", False),
        ('Crown', 'In 3 Days - Billing Starts', "Your plan starts unless you cancel anytime "
                                                'before. Nothing is charged during the trial.',
         True),
    ])
    cards = fk.stack([plan_card_calai('monthly', P_MONTHLY, default=False),
                      plan_card_calai('yearly', P_YEARLY, default=True, badge='SAVE 58%')],
                     direction='horizontal', gap=10, margin=fk.pad(20, 0, 0, 14),
                     caption='Plan cards')
    legal = T('3 days free, then the plan price. Billed yearly or monthly. Plan auto-renews '
              'unless you cancel. Cancel in the App Store.', 'in_caption_15', 'ink_faint',
              align='center', margin=fk.pad(0, 0, 0, 8))
    foot = fk.footer([ok_line('No Payment Due Now'),
                      cta('Start My 3-Day Free Trial', [fk.purchase('plans', 'act_buy')],
                          caption='CTA purchase')],
                     fill_=fk.fill('bg'), padding=fk.pad(8, 20, 20, 8), gap=12, align_v='start')
    content = fk.stack([back_row(), h1, laurel_rows, tl, cards, legal, legal_links(),
                        below_fold()], caption='Content', padding=fk.pad(0, 0, 0, 140))
    return screen('PW_A3_plans', [content, foot], scroll=True,
                  groups=[{'id': 'plans', 'type': 'product'}])


def build_calai():
    bf.ids('el_a2')
    scr = [a1_try(), reminder_screen('PW_A2_reminder', 'PW_A3_plans'), a3_plans()]
    return finish(scr)


# ------------------------------------------------------------------------------------------------
# Flow B — Welmi replica
# ------------------------------------------------------------------------------------------------

def b1_try():
    bf.ids('el_b1')
    h1 = T('We want you to\ntry YumYummy for free', 'fr_h1', 'ink', align='center',
           margin=fk.pad(40, 0, 0, 0))
    tl = timeline([
        ('LockOpen', 'Today', 'Unlock photo, voice and text logging', False),
        ('Bell', 'In 2 Days - Reminder', "We'll send you a reminder that your trial is ending "
                                         'soon', False),
        ('Crown', 'In 3 Days - Billing Starts', "You'll be charged in 3 days unless you cancel "
                                                'before', True),
    ])
    bottom = fk.stack([ok_line('No payment for now'),
                       cta('Try for £0.00', [fk.navigate('PW_B2_reminder', 'act_next')])],
                      gap=14, caption='Bottom')
    return screen('PW_B1_try', [h1, tl, bottom], scroll=False, spread=True)


def b3_plans():
    bf.ids('el_b3')
    bg = bf.media('bg_joe')
    cover = fk.stack([], fixed_h=400, caption='Cover band (photo shows through)')
    h1 = T('<HERO_LINE/>', 'fr_h1', 'white', align='center',
           margin=fk.pad(0, 0, 0, 14), caption='Headline (HERO_LINE from the app)')
    cards = fk.stack([plan_card_welmi('monthly', P_MONTHLY, default=False),
                      plan_card_welmi('yearly', P_YEARLY, default=True, badge='SAVE 58%')],
                     direction='horizontal', gap=10, caption='Plan cards')
    laurels = fk.stack([bf.pill([T(t, 'in_caption', 'white', width='hug')], 'card_dark',
                                border_id='white_dim', caption='Laurel')
                        for t in ('★ <RATING/>', '<USERS/>+ trackers', '✓ Verified data')],
                       direction='horizontal', gap=8, align_h='center',
                       margin=fk.pad(130, 0, 0, 0), caption='Laurels (below fold)')
    panel = fk.stack([h1, cards, laurels, below_fold(dark=True)],
                     padding=fk.pad(60, 0, 0, 150),
                     fill_=fk.fill(layers=fk.gradient(180, ('#0B0A09', 0, 0),
                                                      ('#0B0A09', 0.3, 88),
                                                      ('#0B0A09', 1, 100))),
                     caption='Gradient panel')
    foot = fk.footer([cta('Continue', [fk.purchase('plans', 'act_buy')], caption='CTA purchase'),
                      legal_links('white_dim')],
                     fill_=fk.fill('black'), padding=fk.pad(8, 20, 16, 8), gap=12,
                     align_v='start')
    return screen('PW_B3_plans', [cover, panel, foot], scroll=True, status='dark',
                  groups=[{'id': 'plans', 'type': 'product'}],
                  fill_=fk.image_fill(bg['url'], media_id=bg['media_id'], preview=bg['preview']))


def build_welmi():
    bf.ids('el_b2')
    scr = [b1_try(), reminder_screen('PW_B2_reminder', 'PW_B3_plans'), b3_plans()]
    return finish(scr)


# ------------------------------------------------------------------------------------------------
# After-cancel offers — Welmi design
# ------------------------------------------------------------------------------------------------

def offer_screen(sid, pid, big, sub_parts, prefix):
    bf.ids(prefix)
    bg = bf.media('bg_costa')
    attach = fk.product([], product_id=pid, group_id='offer', default=True,
                        caption='Product attach point (hidden)')
    attach['props']['visibility'] = fk.hidden()
    chip = bf.pill([T("Special Offer, it's FREE", 'in_caption', 'white', width='hug')],
                   'card_dark', border_id='white_dim', pad_v=4, pad_h=12, caption='Chip')
    chip_row = fk.stack([chip], align_h='center', caption='Chip row')
    big_t = T(big, 'fr_stat', 'lime', align='center', margin=fk.pad(10, 0, 0, 6))
    sub = T(sub_parts, 'in_body', 'white', align='center', margin=fk.pad(0, 0, 0, 18))
    buy = {'id': 'act_buy', 'type': 'purchase',
           'payload': {'product': {'type': 'const', 'value': {'id': pid}}}}
    panel = fk.stack([attach, chip_row, big_t, sub, cta('Continue', [buy], caption='CTA purchase'),
                      T('No Commitment · Cancel anytime', 'in_caption', 'white_dim',
                        align='center', margin=fk.pad(10, 0, 0, 10)),
                      legal_links('white_dim')],
                     padding=fk.pad(120, 0, 0, 8),
                     fill_=fk.fill(layers=fk.gradient(180, ('#0B0A09', 0, 0),
                                                      ('#0B0A09', 0.45, 90),
                                                      ('#0B0A09', 1, 100))),
                     caption='Offer panel')
    return screen(sid, [fk.stack([], caption='Cover'), panel], scroll=False, spread=True,
                  status='dark', groups=[{'id': 'offer', 'type': 'product'}],
                  fill_=fk.image_fill(bg['url'], media_id=bg['media_id'], preview=bg['preview']))


def build_offer_299():
    pv = Var(f'{P_W299}.prod_price')
    return finish([offer_screen('PW_OFFER_299', P_W299, '40% OFF',
                                ['3 days free trial, then ', pv, '/week'], 'el_o2')])


def build_offer_499():
    pv = Var(f'{P_W499}.prod_price')
    return finish([offer_screen('PW_OFFER_499', P_W499, 'Try it FREE',
                                ['3 days free trial, then ', pv, '/week'], 'el_o4')])


# ------------------------------------------------------------------------------------------------

def finish(screens):
    meta = {}
    for s in screens:
        if s.get('products'):
            meta.update(fk.predeclare(s['id'], [(p['id'], p.get('offerId')) for p in s['products']]))
    cfg = fk.config(screens=screens, colors=bf.COLORS, typography=bf.TYPO,
                    variables=bf.CUSTOM_VARS, meta_screens=meta or None)
    src = json.load(open(os.path.join(HERE, 'pw_single_monthly.working.json')))['config']
    cfg['theme'] = copy.deepcopy(src['theme'])
    for cid, name, hx in EXTRA_COLORS:
        cfg['theme']['colors'].append({'id': cid, 'name': name, 'light': {'hex': hx},
                                       'dark': {'hex': hx}})
    cfg['_meta']['fonts'] = copy.deepcopy(src['_meta']['fonts'])
    return cfg


def main():
    out = {'pw_calai.json': build_calai, 'pw_welmi.json': build_welmi,
           'pw_offer_299.json': build_offer_299, 'pw_offer_499.json': build_offer_499}
    for name, fn in out.items():
        cfg = fn()
        path = os.path.join(HERE, name)
        with open(path, 'w') as f:
            json.dump(cfg, f, ensure_ascii=False, indent=1)
        n = sum(len(s['elements']['map']) for s in cfg['screens'])
        print(f'{name}: {len(cfg["screens"])} screens, {n} elements -> {path}')


if __name__ == '__main__':
    main()
