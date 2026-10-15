#!/usr/bin/env python3
"""Flow A = Cal AI 3-step paywall, rebuilt from MEASURED reference screens (not from memory).

    python3 build_pw_a_v2.py      # writes pw_calai.json

Reference: Cal AI replay screens 41/42/43 (ScreensDesign, 1080x2335 px = 375x811 pt, 2.88 px/pt),
measured with scratchpad/ref/ (bands of dark pixels → pt):
  screen 1: headline 2 lines top 105, 27pt line pitch · phone mockup 216x362 at y 229 · "No Payment Due
            Now" at 612 (13pt caps) · CTA 56 high, x 14–360, radius ~14 · links row at 742–754.
  screen 2: back chevron · headline 3 lines top 203 · bell block ~y 300–420 · same bottom block.
  screen 3: back · headline 2 lines top 101 · timeline rows at 194 / 269 / 352 (icon 30, title 16 semibold,
            description ~13 muted) · two cards 160x85 at y 475, gap 10 · "No Payment Due Now" 579 · CTA 609.
Brand swaps: Fraunces for the headline, terracotta CTA (Cal AI: system bold / black), our laurels on
screen 3, SAVE 58% green badge instead of "3 DAYS FREE", no "Already purchased?" (Restore covers it).
Nothing below the fold.
"""
import copy
import json
import os

import build_flows as bf
import build_single as bs

fk, T, Var = bf.fk, bf.T, bf.Var
HERE = bf.HERE

P_YEARLY = '7cbbdae3-6caa-4862-b05a-33960863c2f1'   # ai.yumyummy.app.yearly49.99.3d (£49.99, 3-day trial)
P_MONTHLY = 'cf5874b1-a1c2-46cc-900a-2ee04db8ddde'  # ai.yumyummy.app.monthly (£9.99, 3-day trial)

POSTER = None        # media name of a still shown under the A1 video (set by build_pw_a_native)
GUTTER = 16          # Cal AI 14; ours 16 so the CTA keeps the same visual weight on 390pt phones
CTA_H = 56           # measured
EXTRA_COLORS = [
    ('red_badge', 'Red badge', '#D32F2F'),
    ('bell_gray', 'Bell gray', '#C9D3D8'),
]


# ------------------------------------------------------------------------------------------------
# Atoms (every number is a measurement, see the module docstring)
# ------------------------------------------------------------------------------------------------

def headline(text, lines_margin_top):
    return T(text, 'fr_h1', 'ink', align='center', margin=fk.pad(lines_margin_top, 0, 0, 0),
             caption='Headline')


def ok_line(text):
    return T('✓ ' + text, 'in_body_strong', 'ink', align='center', caption='No payment line')


def cta(label, actions, caption='CTA'):
    return fk.stack([T(label, 'in_button', 'white', align='center')], fixed_h=CTA_H,
                    fill_=fk.fill('terracotta'), corner=fk.radius(14), align_h='center',
                    align_v='center', padding=fk.pad(0, 24, 24, 0), actions=actions,
                    caption=caption)


def links_row():
    sep = lambda: T(' · ', 'in_caption', 'ink_faint', width='hug')  # noqa: E731
    return fk.stack([
        T('Terms', 'in_caption', 'ink_faint', width='hug',
          actions=[fk.open_url(bs.TERMS_URL, external=True, action_id='act_terms')], caption='Terms'),
        sep(),
        T('Privacy', 'in_caption', 'ink_faint', width='hug',
          actions=[fk.open_url(bs.PRIVACY_URL, external=True, action_id='act_privacy')],
          caption='Privacy'),
        sep(),
        T('Restore', 'in_caption', 'ink_faint', width='hug', actions=[fk.restore('act_restore')],
          caption='Restore'),
    ], direction='horizontal', align_h='center', align_v='center', margin=fk.pad(4, 0, 0, 0),
        caption='Legal links')


def bottom_block(ok_text, cta_label, actions):
    """Measured: ok line, 18pt gap, 56pt CTA, 18pt gap, links. Pinned by the screen's space-between."""
    return fk.stack([ok_line(ok_text), cta(cta_label, actions)], gap=18,   # no links: Oct 5 decision
                    caption='Bottom block')


def back_row():
    return fk.stack([bf.back_button()], direction='horizontal', align_v='center',
                    margin=fk.pad(6, 0, 0, 0), caption='Back row')


def screen(sid, nodes, *, scroll, spread, groups=()):
    return fk.screen(sid, nodes, caption=sid, fill_=fk.fill('bg'),
                     padding=fk.pad(0, GUTTER, GUTTER, 24), gap=0,
                     distribution='space-between' if spread else None, scrollable=scroll,
                     safe_area=True, status_bar_theme='light', selectable_groups=list(groups))


# ------------------------------------------------------------------------------------------------
# Screen 1 — "We want you to try YumYummy for free." + video in a phone frame
# ------------------------------------------------------------------------------------------------

def a1_try():
    bf.ids('el_a1')
    h1 = headline('We want you to\ntry YumYummy for free.', 58)
    # iPhone mockup 216x444 (frame PNG 720x1480, bezel 22px = 6.6pt): video sits inside the bezel,
    # the frame PNG (transparent screen) is drawn on top.
    frame_png = bf.media('phone_frame')
    video = fk.video(fixed_h=431, width='fill', corner=fk.radius(29),
                     position=fk.absolute(top=7, left=7, right=7),
                     caption='Demo video (paywall_demo_scan_loop_v3.mp4)')
    overlay = fk.image(frame_png['url'], media_id=frame_png['media_id'], preview=frame_png['preview'],
                       fit='cover', fixed_w=216, fixed_h=444, position=fk.absolute(top=0, left=0),
                       caption='iPhone frame overlay')
    kids = [video, overlay]
    if POSTER:   # first frame under the video: the HLS stream takes ~0.7 s to start on device
        m = bf.media(POSTER)
        poster = fk.image(m['url'], media_id=m['media_id'], preview=m['preview'], fit='cover',
                          width='fill', fixed_h=431, position=fk.absolute(top=7, left=7, right=7),
                          caption='Poster (first frame)')
        poster['props']['borderRadius'] = fk.radius(29)
        kids.insert(0, poster)
    phone = fk.stack(kids, fixed_w=216, fixed_h=444, caption='Phone mockup')
    mock = fk.stack([phone], align_h='center', caption='Mockup')
    return screen('PW_A1_try', [h1, mock, bottom_block('No Payment Due Now', 'Try Now',
                                                       [fk.navigate('PW_A2_reminder', 'act_next')])],
                  scroll=False, spread=True)


# ------------------------------------------------------------------------------------------------
# Screen 2 — reminder (Welmi / Cal AI, identical)
# ------------------------------------------------------------------------------------------------

def a2_reminder():
    bf.ids('el_a2')
    h1 = headline("We'll send you a\nreminder before your\nfree trial ends", 96)
    # Animated bell: a looping 3.2 s clip (media/reminder_bell_loop.mp4, cream background, no audio),
    # uploaded in the builder; 210x210 pt box, so the bell itself is ~115 pt like Welmi's.
    bell_box = fk.video(fixed_h=210, width='fill', fit='fit',
                        caption='Bell animation (reminder_bell_loop_720.mp4)')
    bell_box = fk.stack([bell_box], fixed_w=210, caption='Bell + badge')
    mid = fk.stack([bell_box], align_h='center', caption='Bell block')
    top = fk.stack([back_row(), h1], caption='Top')
    return screen('PW_A2_reminder', [top, mid,
                                     bottom_block('No payment for now', 'Continue for FREE',
                                                  [fk.navigate('PW_A3_plans', 'act_next')])],
                  scroll=False, spread=True)


# ------------------------------------------------------------------------------------------------
# Screen 3 — plans (Cal AI) with a personalised headline and our laurels
# ------------------------------------------------------------------------------------------------

def timeline():
    rows = [
        ('LockOpen', False, 'Today', "Unlock all the app's features: photo, voice and text logging "
                                     'with verified sources.'),
        ('Bell', False, 'In 2 Days - Reminder', "We'll send you a reminder that your trial is ending "
                                                "soon if you've allowed us to notify you."),
        ('Crown', True, 'In 3 Days - Billing Starts', 'Your plan starts unless you cancel anytime '
                                                      'before. Nothing is charged during the trial.'),
    ]
    out = []
    for i, (icon, gray, title, desc) in enumerate(rows):
        last = i == len(rows) - 1
        chip = fk.stack([fk.icon(icon, size_pt=15, color_id='ink_faint' if gray else 'terracotta',
                                 weight='fill')],
                        fixed_w=30, fixed_h=30, align_h='center', align_v='center',
                        fill_=fk.fill('hairline' if gray else 'terracotta_soft'),
                        corner=fk.radius(15), position=fk.absolute(top=0, left=0),
                        caption='Step icon')
        kids = [chip]
        if not last:
            kids.append(fk.stack([], fixed_w=3, height='auto', fill_=fk.fill('terracotta_soft'),
                                 position=fk.absolute(top=34, left=14, bottom=-2), caption='Rail'))
        kids.append(fk.stack([T(title, 'in_body_strong', 'ink'), T(desc, 'in_small', 'ink_muted')],
                             gap=2, padding=fk.pad(3, 44, 0, 0 if last else 22),
                             caption='Step text'))
        out.append(fk.stack(kids, direction='horizontal', caption='Step'))
    return fk.stack(out, margin=fk.pad(18, 0, 0, 0), caption='Timeline')


def plan_card(key, pid, *, default, badge=None):
    chk = fk.icon('Check', size_pt=12, color_id='white', weight='bold')
    chk['props']['opacity'] = 0
    fk.on_selected(chk, opacity=100)
    ring = fk.stack([chk], fixed_w=22, fixed_h=22, align_h='center', align_v='center',
                    corner=fk.radius(11), border='hairline_strong', border_width=1.5, caption='Check')
    fk.on_selected(ring, fill=fk.fill('ink'),
                   border={'color': fk.color('ink'), 'width': 1.5})
    pv = lambda f: Var(f'{pid}.{f}')  # noqa: E731
    if key == 'yearly':
        lines = [T('Yearly', 'in_small', 'ink_muted'),
                 T([pv('prod_price')], 'in_title', 'ink'),
                 T([pv('prod_price_per_month'), ' / month'], 'in_caption', 'ink_muted')]
    else:
        lines = [T('Monthly', 'in_small', 'ink_muted'),
                 T([pv('prod_price')], 'in_title', 'ink'),
                 T('per month', 'in_caption', 'ink_muted')]
    row = fk.stack([fk.stack(lines, gap=2, caption='Plan text'), ring], direction='horizontal',
                   gap=8, align_v='center', caption='Plan row')
    kids = [row]
    if badge:
        kids.append(bf.pill([T(badge, 'in_caption_strong', 'white', width='hug')], 'done_green',
                            pad_v=3, pad_h=9, caption='Badge', position=fk.absolute(top=-12, right=10)))
    card = fk.product(kids, product_id=pid, group_id='plans', default=default,
                      padding=fk.pad(14, 12, 12, 14), fill_=fk.fill('surface'),
                      corner=fk.radius(16), border='hairline_strong', border_width=1.5,
                      caption=f'Plan {key}')
    fk.on_selected(card, border={'color': fk.color('ink'), 'width': 2})
    return card


def a3_plans():
    bf.ids('el_a3')
    h1 = T([Var('var_HERO_LINE'), '. Start for FREE today.'], 'fr_h1', 'ink', align='center',
           margin=fk.pad(6, 0, 0, 0), caption='Headline (HERO_LINE from the app)')
    laurels = fk.stack([bf.pill([T(t, 'in_caption', 'ink_muted', width='hug')], 'surface',
                                border_id='hairline', caption='Laurel')
                        for t in (['★ ', Var('var_RATING')], [Var('var_USERS'), '+ trackers'],
                                  '✓ Verified data')],
                       direction='horizontal', gap=6, align_h='center', margin=fk.pad(12, 0, 0, 0),
                       caption='Laurels')
    cards = fk.stack([plan_card('monthly', P_MONTHLY, default=False),
                      plan_card('yearly', P_YEARLY, default=True, badge='SAVE 58%')],
                     direction='horizontal', gap=10, margin=fk.pad(26, 0, 0, 0), caption='Plan cards')
    legal = T('3 days free, then the plan price. Billed yearly or monthly. Plan auto-renews unless '
              'you cancel. Cancel in the App Store.', 'in_caption_15', 'ink_faint', align='center',
              caption='Disclosure')
    bottom = fk.stack([ok_line('No Payment Due Now'),
                       cta('Start My 3-Day Free Trial', [fk.purchase('plans', 'act_buy')],
                           caption='CTA purchase'),
                       legal, links_row()], gap=14, margin=fk.pad(22, 0, 0, 0), caption='Bottom block')
    top = fk.stack([back_row(), h1, laurels, timeline(), cards], caption='Content')
    return screen('PW_A3_plans', [top, bottom], scroll=True, spread=False,
                  groups=[{'id': 'plans', 'type': 'product'}])


# ------------------------------------------------------------------------------------------------

def build():
    screens = [a1_try(), a2_reminder(), a3_plans()]
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
    attach_videos(cfg)
    return cfg


# Clips uploaded through the builder UI on 2026-10-03 (the API rejects anything under 640x640;
# the bell is therefore the 720x720 upscale). Keyed by element id so a rebuild keeps them.
VIDEO_URLS = {
    'el_a1_002V': '470b50c3-4966-4b8f-b209-344450d948c6',   # paywall_demo_scan_loop_v3.mp4
    'el_a2_002V': 'ee1ce31d-cb59-4c68-bc30-41b622c35ae4',   # reminder_bell_loop_720.mp4 (page-colour bg)
}


def attach_videos(cfg):
    def walk(o):
        if isinstance(o, dict):
            if o.get('type') == 'video' and o.get('id') in VIDEO_URLS:
                base = 'https://public-media.adapty.io/video/' + VIDEO_URLS[o['id']]
                o['props']['video'] = {'values': {'en': {'videoUrl': base + '/hls/master.m3u8',
                                                          'previewUrl': base + '/preview.png'}},
                                       '_localizable': True}
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(cfg['screens'])


if __name__ == '__main__':
    cfg = build()
    path = os.path.join(HERE, 'pw_calai.json')
    with open(path, 'w') as f:
        json.dump(cfg, f, ensure_ascii=False, indent=1)
    n = sum(len(s['elements']['map']) for s in cfg['screens'])
    print(f'pw_calai (v2, measured): {len(cfg["screens"])} screens, {n} elements -> {path}')
