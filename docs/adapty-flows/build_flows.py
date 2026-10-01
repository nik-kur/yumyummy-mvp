#!/usr/bin/env python3
"""Build the two YumYummy Adapty flow configs from intro-spec.md.

    python3 build_flows.py            # writes onb_main.json and pw_main.json next to this file

Deterministic: element ids come from one counter PER SCREEN (prefix el_sNN / el_pw), so editing one
screen never renumbers another. Product UUIDs / offer ids are read from products.json.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REF = os.path.join(HERE, '..', 'adapty-skills', 'skills', 'flow-generator', 'references')
sys.path.insert(0, os.path.abspath(REF))
sys.dont_write_bytecode = True
import flowkit as fk  # noqa: E402

Span, Var = fk.Span, fk.Var

# ------------------------------------------------------------------------------------------------
# Theme (spec §0.7). The app has no dark mode, so dark == light: nothing flips on a dark-mode phone.
# ------------------------------------------------------------------------------------------------
COLORS = [
    ('bg', 'Background (paper)', '#F7F1E6'),
    ('surface', 'Surface (cards)', '#FFFDF9'),
    ('surface_alt', 'Surface alt', '#FBF6EE'),
    ('ink', 'Ink', '#19150F'),
    ('ink_muted', 'Ink muted', '#6B6258'),
    ('ink_faint', 'Ink faint', '#938A7C'),
    ('hairline', 'Hairline', '#E7DFD1'),
    ('hairline_strong', 'Hairline strong', '#D8CCB9'),
    ('terracotta', 'Terracotta', '#B85A3A'),
    ('terracotta_text', 'Terracotta text', '#9A4628'),
    ('terracotta_soft', 'Terracotta soft', '#EFDFD1'),
    ('success', 'Success', '#2E6B4E'),
    ('error', 'Error', '#9A2A1F'),
    ('info_blue', 'Info blue', '#1F5C99'),
    ('info_blue_soft', 'Info blue soft', '#E7EFF8'),
    ('olive_soft', 'Olive soft', '#E3E6CE'),
    ('warning_soft', 'Warning soft', '#FBEFD6'),
    ('protein', 'Protein', '#5A6A3A'),
    ('fat', 'Fat', '#8A5A14'),
    ('carbs', 'Carbs', '#2C6CA8'),
    ('done_green', 'Paywall done green', '#16A34A'),
    ('surplus_strip', 'CICO surplus strip', '#C97A6A'),
    ('stage_bg', 'Welcome demo stage', '#F2EADB'),
    ('white', 'White', '#FFFFFF'),
]
COLORS = [(i, n, h, h) for i, n, h in COLORS]

# Typography: ids name the INTENDED face. No `family` -> builder default system font until the
# Google fonts are uploaded in the builder and mapped (trap 8; CHECKLIST.md).
TYPO = [
    ('fr_hero', 'Fraunces 600 · Hero 56/58', 56, 'semibold', 58),
    ('fr_stat', 'Fraunces 700 · Stat 60/66', 60, 'bold', 66),
    ('fr_h1', 'Fraunces 600 · H1 28/32', 28, 'semibold', 32),
    ('fr_h2', 'Fraunces 600 · H2 22/28', 22, 'semibold', 28),
    ('fr_num34', 'Fraunces 700 · kcal 34/40', 34, 'bold', 40),
    ('fr_label28', 'Fraunces 700 · Mascot label 28/32', 28, 'bold', 32),
    ('in_title', 'Inter 600 · Title 18/24', 18, 'semibold', 24),
    ('in_title_26', 'Inter 600 · Title 18/26', 18, 'semibold', 26),
    ('in_body', 'Inter 400 · Body 16/26', 16, 'regular', 26),
    ('in_body_strong', 'Inter 600 · Body strong 16/26', 16, 'semibold', 26),
    ('in_small', 'Inter 400 · Small 14/21', 14, 'regular', 21),
    ('in_caption', 'Inter 500 · Caption 12/16', 12, 'medium', 16),
    ('in_caption_strong', 'Inter 600 · Chip 12/16', 12, 'semibold', 16),
    ('in_button', 'Inter 600 · Button 16/20', 16, 'semibold', 20),
    ('in_badge', 'Inter 600 · Number badge 14/18', 14, 'semibold', 18),
    ('jb_overline', 'JetBrains Mono 500 · Overline 11/14 +1.6', 11, 'medium', 14, 1.6),
    ('jb_badge', 'JetBrains Mono 500 · Source badge 11/14 +1', 11, 'medium', 14, 1),
    ('emoji_42', 'Emoji 42', 42, 'regular', 48),
    ('emoji_40', 'Emoji 40', 40, 'regular', 48),
    ('emoji_26', 'Emoji 26', 26, 'regular', 32),
    ('emoji_22', 'Emoji 22', 22, 'regular', 28),
    ('emoji_20', 'Emoji 20', 20, 'regular', 26),
]

GUTTER = 20


def media(name):
    """An asset uploaded with `flows media upload --json` (record kept in media/<name>.json)."""
    with open(os.path.join(HERE, 'media', name + '.json')) as f:
        m = json.load(f)
    return dict(url=m['url'], media_id=str(m['id']), preview=m.get('preview_base64') or fk.NO_PREVIEW)


def ids(prefix):
    """One counter per screen: stable ids that do not shift when another screen changes."""
    fk._ids = fk.Ids(prefix=prefix)


# ------------------------------------------------------------------------------------------------
# Small builders
# ------------------------------------------------------------------------------------------------

def T(parts, preset, color='ink', align='left', width='fill', **kw):
    if isinstance(parts, (str, Span, Var)):
        parts = [parts]
    vis = kw.pop('visibility', None)
    node = fk.text(fk.rich(*parts), preset=preset, color_id=color, align=align, width=width, **kw)
    if vis is not None:
        node['props']['visibility'] = vis
    return node


def pill(children, fill_id, border_id=None, pad_v=4, pad_h=12, gap=4, caption='Pill', **kw):
    return fk.stack(children, width='hug', direction='horizontal', gap=gap, align_h='center',
                    align_v='center', fill_=fk.fill(fill_id), corner=fk.radius(999),
                    padding=fk.pad(pad_v, pad_h, pad_h, pad_v), border=border_id, border_width=1,
                    caption=caption, **kw)


def card(children, *, gap=12, pad=16, border='hairline', bw=1, fill_id='surface', rad=16,
         caption='Card', direction='vertical', **kw):
    return fk.stack(children, gap=gap, padding=fk.pad(pad, pad, pad, pad), fill_=fk.fill(fill_id),
                    corner=fk.radius(rad), border=border, border_width=bw, caption=caption,
                    direction=direction, **kw)


def button(label, actions, caption='CTA'):
    """Brand button (§0.6): full width, 54 high, radius 12, terracotta, white Inter 600 16."""
    return fk.stack([T(label, 'in_button', 'white', align='center')], fixed_h=54,
                    fill_=fk.fill('terracotta'), corner=fk.radius(12), align_h='center',
                    align_v='center', padding=fk.pad(0, 24, 24, 0), actions=actions,
                    caption=caption)


def eyebrow(text, color='terracotta_text', align='left'):
    return T(text.upper(), 'jb_overline', color, align=align)


def header_block(over, h1, body=None):
    """§0.4: eyebrow, h1 (marginTop 4), optional muted body. marginTop 12 / marginBottom 20."""
    kids = [eyebrow(over), T(h1, 'fr_h1', 'ink', margin=fk.pad(4, 0, 0, 0))]
    if body:
        kids.append(T(body, 'in_body', 'ink_muted'))
    return fk.stack(kids, gap=4, margin=fk.pad(12, 0, 0, 20), caption='Header block')


def back_button():
    return fk.stack([fk.icon('CaretLeft', size_pt=18, color_id='ink')], fixed_w=32, fixed_h=32,
                    align_h='center', align_v='center', fill_=fk.fill('surface'),
                    corner=fk.radius(16), border='hairline', border_width=1,
                    actions=[fk.navigate_back('act_back')], caption='Back')


def intro_header():
    """IntroHeader row. The progress-bar component is appended to this row's hierarchy as a
    `global` node after the screen is built (see attach_progress)."""
    return fk.stack([back_button()], direction='horizontal', gap=12, align_v='center',
                    margin=fk.pad(8, 0, 0, 8), caption='IntroHeader')


def radio_ring(color_on='terracotta'):
    """Unselected: 22 ring hairlineStrong. Selected: terracotta ring + terracotta check (=CircleCheck)."""
    chk = fk.icon('Check', size_pt=14, color_id=color_on, weight='bold')
    chk['props']['opacity'] = 0
    fk.on_selected(chk, opacity=100)
    ring = fk.stack([chk], fixed_w=22, fixed_h=22, align_h='center', align_v='center',
                    corner=fk.radius(11), border='hairline_strong', border_width=1.5,
                    caption='Radio')
    fk.on_selected(ring, border={'color': fk.color(color_on), 'style': 'solid', 'width': 1.5})
    return ring


def checkbox():
    chk = fk.icon('Check', size_pt=14, color_id='white', weight='bold')
    chk['props']['opacity'] = 0
    fk.on_selected(chk, opacity=100)
    box = fk.stack([chk], fixed_w=22, fixed_h=22, align_h='center', align_v='center',
                   corner=fk.radius(8), border='hairline_strong', border_width=1.5,
                   fill_=fk.fill('surface'), caption='Checkbox')
    fk.on_selected(box, fill=fk.fill('terracotta'),
                   border={'color': fk.color('terracotta'), 'style': 'solid', 'width': 1.5})
    return box


def option_card(children, *, group, cid, actions=None, gap=12, pad_v=12, pad_h=16, **kw):
    node = fk.selectable(children, group_id=group, custom_id=cid, direction='horizontal',
                         gap=gap, align_v='center', padding=fk.pad(pad_v, pad_h, pad_h, pad_v),
                         fill_=fk.fill('surface'), corner=fk.radius(16), border='hairline',
                         border_width=1.5, actions=actions, caption=f'Option {cid}', **kw)
    fk.on_selected(node, fill=fk.fill('terracotta_soft'),
                   border={'color': fk.color('terracotta'), 'style': 'solid', 'width': 1.5})
    return node


def spacer():
    return fk.stack([], caption='Spacer')


def attach_progress(scr, header_id, segment):
    """Reference the progress-bar component inside the IntroHeader row and switch the screen on."""
    def walk(n):
        if n.get('id') == header_id:
            n.setdefault('children', []).append({'id': PB_ID, 'type': 'global'})
            return True
        return any(walk(c) for c in n.get('children', []))
    assert walk(scr['elements']['hierarchy']), header_id
    scr['props']['progressBar'] = {'enabled': True, 'segment': segment}
    return scr


def mk_screen(sid, nodes, *, scroll, groups=(), spread=False, pad_top=0, pad_bottom=16):
    return fk.screen(sid, nodes, caption=sid, fill_=fk.fill('bg'),
                     padding=fk.pad(pad_top, GUTTER, GUTTER, pad_bottom), gap=0,
                     distribution='space-between' if spread else None, scrollable=scroll,
                     safe_area=True, status_bar_theme='light', selectable_groups=list(groups))


# ------------------------------------------------------------------------------------------------
# Progress bar component (patterns.md "A progress bar"): 12 manual segments, gap 0, so the fill is
# exactly step/12 like IntroHeader's round(step/12*100)%.
# ------------------------------------------------------------------------------------------------
PB_ID = 'pb_intro'
LAST_STEP = 12


def progress_component():
    ids('el_pb')
    segs = []
    for i in range(1, LAST_STEP + 1):
        loader = fk._node('progress-bar-loader', {
            'fill': fk.fill('terracotta_soft'), 'color': fk.color('terracotta'),
            'width': fk.size('fill'), 'height': fk.size('fixed', 4), 'duration': 300,
            'easing': 'ease-in-out', 'position': fk.relative()})
        seg = fk._node('progress-bar-segment', {
            'width': fk.size('fill'), 'height': fk.size('hug'),
            'layout': fk.layout('horizontal', 0, 'start', 'center'), 'customId': f's{i:02d}'},
            children=[loader],
            props_by_state={s: {'width': fk.size('fill'), 'height': fk.size('hug')}
                            for s in ('current', 'upcoming', 'completed')})
        segs.append(seg)
    lay = fk.layout('horizontal', 0, 'start', 'center')
    lay['clipContent'] = True
    bar = fk._node('progress-bar', {
        'type': 'multiple-segments', 'template': 'segmented', 'oneSegmentPerScreen': False,
        'width': fk.size('fill'), 'height': fk.size('fixed', 4), 'layout': lay,
        'padding': fk.pad(0, 0, 0, 0), 'borderRadius': fk.radius(999),
        'fill': fk.fill('terracotta_soft')}, children=segs, caption='Intro progress (step/12)')
    node_map, hierarchy = fk.flatten([bar])
    for el in node_map.values():      # components elements carry no `states` in real exports
        el.pop('states', None)
    return {PB_ID: {'map': node_map, 'hierarchy': hierarchy}}


# ------------------------------------------------------------------------------------------------
# Flow 1 — onb_main
# ------------------------------------------------------------------------------------------------

def s1_welcome():
    ids('el_s01')
    mascot = fk.image(**media('mood_stellar_t'), fit='fit', fixed_w=64, fixed_h=64,
                      margin=fk.pad(0, 0, 0, 4), caption='Mascot mood_stellar_t.png 64x64')
    head = fk.stack([
        mascot,
        T('The food tracker you’ll actually keep up with', 'fr_h1', 'ink', align='center',
          margin=fk.pad(4, 0, 0, 0)),
        T('Any meal, any way — verified calories in ~10 seconds.', 'in_title_26', 'ink_muted',
          align='center', margin=fk.pad(0, 12, 12, 0)),
    ], gap=8, align_h='center', caption='Welcome header')

    def mode_pills(active):
        out = []
        for name, ic in (('Photo', 'Camera'), ('Voice', 'Microphone'), ('Text', 'Keyboard')):
            on = name == active
            out.append(pill([fk.icon(ic, size_pt=12, color_id='white' if on else 'ink_muted'),
                             T(name, 'in_caption_strong', 'white' if on else 'ink_muted',
                               width='hug')],
                            'terracotta' if on else 'bg', 'terracotta' if on else 'hairline',
                            pad_v=5, caption=f'Mode {name}'))
        return fk.stack(out, direction='horizontal', gap=8, align_h='center', caption='Mode pills')

    def stage(kids, caption):
        return fk.stack(kids, fixed_h=128, gap=8, align_h='center', align_v='center',
                        fill_=fk.fill('stage_bg'), corner=fk.radius(12),
                        padding=fk.pad(0, 16, 16, 0), caption=caption)

    def result(kcal, name, source, macros):
        strip = fk.stack([], fixed_w=3, height='auto', fill_=fk.fill('terracotta'),
                         position=fk.absolute(top=0, bottom=0, left=0), caption='Accent 3px')
        left = fk.stack([
            fk.stack([T(kcal, 'fr_h2', 'ink', width='hug'),
                      T(' kcal', 'in_caption', 'ink_muted', width='hug')],
                     direction='horizontal', align_v='end', width='hug'),
            T(name, 'in_caption', 'ink_muted'),
        ], gap=2, caption='Result left')
        src = pill([T('◎ ' + source.upper(), 'jb_badge', 'info_blue', width='hug')],
                   'info_blue_soft', pad_v=3, pad_h=8, caption='Source badge')
        right = fk.stack([src, T(macros, 'in_caption', 'ink_muted', align='right', width='hug')],
                         width='hug', gap=4, align_h='end', caption='Result right')
        node = fk.stack([strip, left, right], direction='horizontal', gap=8, align_v='center',
                        fill_=fk.fill('surface'), corner=fk.radius(12), border='hairline',
                        border_width=0.5, padding=fk.pad(12, 16, 16, 12), caption='Result card')
        node['props']['layout']['clipContent'] = True
        return fk.stack([node], caption='Result slot')

    def slide(active, stg, res):
        return fk.stack([mode_pills(active), stg, res], gap=12, padding=fk.pad(12, 12, 12, 12),
                        fill_=fk.fill('surface'), corner=fk.radius(20), border='hairline',
                        border_width=0.5, caption=f'Demo {active}')

    bars = [fk.stack([], fixed_w=5, fixed_h=h, fill_=fk.fill('terracotta'), corner=fk.radius(3),
                     caption='Wave bar') for h in (14, 26, 32, 18, 28, 12, 22)]
    slides = [
        slide('Photo', stage([T('🥑🍳🍞', 'emoji_42', 'ink', align='center')], 'Stage photo'),
              result('412', 'Avocado toast & eggs', 'USDA', 'P 22g · F 24g · C 28g')),
        slide('Voice', stage([
            T(Span('“Starbucks cappuccino and a butter croissant”', italic=True), 'in_body',
              'ink', align='center'),
            fk.stack(bars, direction='horizontal', gap=4, align_h='center', align_v='center',
                     fixed_h=32, width='hug', caption='Waveform')], 'Stage voice'),
              result('350', 'Cappuccino & butter croissant', 'Starbucks',
                     'P 11g · F 18g · C 38g')),
        slide('Text', stage([T(['tunacado from joe & the juice',
                                Span('|', color='terracotta')], 'in_title', 'ink',
                               align='center')], 'Stage text'),
              result('570', 'Tunacado sandwich', 'Joe & The Juice', 'P 25g · F 40g · C 29g')),
    ]
    demo = fk.carousel(slides, slide_w=310, slide_h=300, gap=12, dots=False,
                       margin=fk.pad(12, 0, 0, 12), caption='WelcomeDemo (auto-advances)')
    demo['props']['scrollAnimation'] = {'delay': 3300, 'duration': 400, 'easing': 'ease-in-out'}

    body = fk.stack([head, demo], gap=20, align_h='center', padding=fk.pad(24, 20, 20, 0),
                    caption='Body')

    chips = [pill([T(t, 'in_caption', 'ink_muted', width='hug')], 'surface', 'hairline',
                  pad_v=5, caption='Trust chip') for t in ('★ 4.9', '12,000+ trackers',
                                                          '✓ Verified data')]
    chip_rows = fk.stack([
        fk.stack(chips[:2], direction='horizontal', gap=8, align_h='center', width='fill'),
        fk.stack(chips[2:], direction='horizontal', gap=8, align_h='center', width='fill'),
    ], gap=8, align_h='center', caption='Trust chips')
    signin = T('Already have an account? Sign in', 'in_small', 'terracotta_text', align='center',
               actions=[fk.custom_action('sign_in', 'act_signin')], caption='Sign in link')
    foot = fk.footer([
        button('Get Started', [fk.custom_action('request_att', 'act_att'),
                               fk.navigate('S2_goal', 'act_next')]),
        chip_rows, signin,
    ], fill_=fk.fill('bg'), padding=fk.pad(12, 20, 20, 20), gap=12, align_v='start')
    return mk_screen('S1_welcome', [body, foot], scroll=True)


def s2_goal():
    ids('el_s02')
    hdr = intro_header()
    opts = []
    for cid, ic, label in (('lose', 'TrendDown', 'Lose weight'),
                           ('maintain', 'ForkKnife', 'Maintain & eat healthier'),
                           ('gain', 'Barbell', 'Gain muscle'),
                           ('just_track', 'Eye', 'Just track my food')):
        ic_on = fk.icon(ic, size_pt=22, color_id='terracotta')
        fk.on_selected(ic_on, opacity=0)
        ic_sel = fk.icon(ic, size_pt=22, color_id='white', position=fk.absolute(top=11, left=11))
        ic_sel['props']['opacity'] = 0
        fk.on_selected(ic_sel, opacity=100)
        tile = fk.stack([ic_on, ic_sel], fixed_w=44, fixed_h=44, align_h='center',
                        align_v='center', fill_=fk.fill('terracotta_soft'), corner=fk.radius(12),
                        caption='Icon tile')
        fk.on_selected(tile, fill=fk.fill('terracotta'))
        opts.append(option_card([tile, T(label, 'in_title', 'ink'), radio_ring()],
                                group='goal', cid=cid,
                                actions=[fk.navigate('S3_why', 'act_next')]))
    top = fk.stack([hdr, header_block('About you', 'What’s your goal right now?')],
                   caption='Top')
    lst = fk.stack(opts, gap=16, caption='Goal options')
    scr = mk_screen('S2_goal', [top, lst, spacer()], scroll=False, spread=True,
                    groups=[{'id': 'goal', 'type': 'single_choice'}])
    return attach_progress(scr, hdr['id'], 's01')


WHY = {  # goal: (stat, statcap, headline, body, foot, url)
    'lose': ('2×', 'more weight lost, on average', 'Tracking is your biggest lever',
             "People who log their meals consistently lose about twice as much weight as those "
             "who don't — and keep it off longer.",
             'Kaiser Permanente study of 1,685 adults · Am J Prev Med, 2008',
             'https://pubmed.ncbi.nlm.nih.gov/18617080/'),
    'maintain': ('#1', 'predictor of keeping it off', 'The habit that makes it stick',
                 'Simply writing down what you eat is one of the strongest predictors of '
                 'maintaining a healthy weight for good.',
                 'National Weight Control Registry · Am J Clin Nutr, 2005',
                 'https://pubmed.ncbi.nlm.nih.gov/16002825/'),
    'gain': ('2×', 'faster lean gains', 'Muscle is a numbers game',
             'Hit your protein and calorie targets consistently and you build lean mass far '
             'faster than training alone.',
             'Meta-analysis of 49 trials · Br J Sports Med, 2018',
             'https://pubmed.ncbi.nlm.nih.gov/28698222/'),
    'just_track': ('~30%', 'how much people misjudge intake', 'Awareness changes everything',
                   'Most people misjudge what they eat by about a third. Just seeing the real '
                   'numbers is often enough to shift habits.',
                   'Lichtman et al. · New England Journal of Medicine, 1992',
                   'https://pubmed.ncbi.nlm.nih.gov/1454084/'),
}


def s3_why():
    ids('el_s03')
    hdr = intro_header()
    goal = fk.ref('goal.selectedOptionId')
    others = ('maintain', 'gain', 'just_track')

    def per_goal(idx, preset, color, align='center', **kw):
        content = fk.switch_rich([(fk.eq(goal, g), [WHY[g][idx]]) for g in others],
                                 default=[WHY['lose'][idx]])
        return fk.text(content, preset=preset, color_id=color, align=align, **kw)

    cite_action = fk.conditional_action(
        [(fk.eq(goal, g), [fk.open_url(WHY[g][5], external=True, action_id='')])
         for g in others],
        default=[fk.open_url(WHY['lose'][5], external=True, action_id='')], action_id='act_cite')
    cite = fk.stack([per_goal(4, 'in_caption', 'ink_faint', width='hug'),
                     fk.icon('ArrowSquareOut', size_pt=12, color_id='info_blue')],
                    direction='horizontal', gap=4, align_h='center', align_v='center',
                    margin=fk.pad(16, 0, 0, 0), actions=[cite_action], caption='Citation link')
    middle = fk.stack([
        per_goal(0, 'fr_stat', 'terracotta'),
        per_goal(1, 'in_small', 'ink_muted', margin=fk.pad(4, 0, 0, 0)),
        per_goal(2, 'fr_h1', 'ink', margin=fk.pad(16, 0, 0, 0)),
        per_goal(3, 'in_body', 'ink_muted', margin=fk.pad(8, 0, 0, 0)),
        cite,
    ], align_h='center', padding=fk.pad(0, 8, 8, 0), caption='Why content (per goal)')
    top = fk.stack([hdr, eyebrow('Why this works')], gap=12, caption='Top')
    cta = button('Continue', [fk.navigate('S4_gender', 'act_next')])
    scr = mk_screen('S3_why', [top, middle, cta], scroll=False, spread=True)
    return attach_progress(scr, hdr['id'], 's02')


def s4_gender():
    ids('el_s04')
    hdr = intro_header()
    cards = []
    for cid, emo, label in (('male', '👨', 'Male'), ('female', '👩', 'Female')):
        c = fk.selectable([T(emo, 'emoji_40', 'ink', align='center'),
                           T(label, 'in_title', 'ink', align='center')],
                          group_id='gender', custom_id=cid, fixed_h=160, gap=8, align_h='center',
                          align_v='center', fill_=fk.fill('surface'), corner=fk.radius(16),
                          border='hairline', border_width=1.5,
                          actions=[fk.navigate('S5_age', 'act_next')], caption=f'Option {cid}')
        fk.on_selected(c, fill=fk.fill('terracotta_soft'),
                       border={'color': fk.color('terracotta'), 'style': 'solid', 'width': 1.5})
        cards.append(c)
    top = fk.stack([hdr, header_block('Your metabolism',
                                      'How should we calculate your metabolism?',
                                      'We use this for your calorie formula only.')],
                   caption='Top')
    row = fk.stack(cards, direction='horizontal', gap=16, align_v='center', caption='Gender row')
    scr = mk_screen('S4_gender', [top, row, spacer()], scroll=False, spread=True,
                    groups=[{'id': 'gender', 'type': 'single_choice'}])
    return attach_progress(scr, hdr['id'], 's03')


def num_input(cid, placeholder, *, preset='fr_h2', width='fill', height=56):
    return fk.number_input(cid, placeholder=placeholder, preset=preset, width=width,
                           height_pt=height, fill_=fk.fill('surface'), border='hairline',
                           corner=fk.radius(12), padding=fk.pad(0, 16, 16, 0),
                           caption=f'Input {cid}')


def s5_age():
    ids('el_s05')
    hdr = intro_header()
    inp = fk.number_input('age', placeholder='30', preset='fr_hero', width='fill', height_pt=80,
                          fill_=fk.fill('surface'), border='hairline', corner=fk.radius(16),
                          padding=fk.pad(0, 24, 24, 0), caption='Input age')
    picker = fk.stack([fk.stack([inp], fixed_w=160, caption='Age box')], align_h='center',
                      caption='Age picker')
    top = fk.stack([hdr, header_block('Your metabolism', 'How old are you?')], caption='Top')
    cta = button('Continue', [fk.navigate('S6_body', 'act_next')])
    scr = mk_screen('S5_age', [top, picker, cta], scroll=False, spread=True)
    return attach_progress(scr, hdr['id'], 's04')


def s6_body():
    ids('el_s06')
    hdr = intro_header()
    segs = []
    for cid, label, default in (('metric', 'Metric', True), ('imperial', 'Imperial', False)):
        lab = T(label, 'in_body_strong', 'ink_muted', align='center')
        fk.on_selected(lab, color=fk.color('bg'))
        s = fk.selectable([lab], group_id='units', custom_id=cid, default=default,
                          padding=fk.pad(12, 8, 8, 12), corner=fk.radius(8), align_h='center',
                          align_v='center', caption=f'Segment {cid}')
        fk.on_selected(s, fill=fk.fill('ink'))
        segs.append(s)
    seg = fk.stack(segs, direction='horizontal', gap=4, padding=fk.pad(4, 4, 4, 4),
                   fill_=fk.fill('surface_alt'), corner=fk.radius(12), border='hairline',
                   border_width=1, margin=fk.pad(0, 0, 0, 20), caption='Units toggle')

    units = fk.ref('units.selectedOptionId')
    is_imp = fk.when(fk.eq(units, 'imperial'))
    is_met = fk.when(fk.neq(units, 'imperial'))

    def with_unit(inp, unit):
        return fk.stack([inp, T(unit, 'in_body', 'ink_muted', width='hug')],
                        direction='horizontal', gap=6, align_v='center')

    def column(label, metric, imperial):
        m = fk.stack(metric, direction='horizontal', gap=8, align_v='center', visibility=is_met,
                     caption='Metric')
        i = fk.stack(imperial, direction='horizontal', gap=8, align_v='center',
                     visibility=is_imp, caption='Imperial')
        return fk.stack([T(label.upper(), 'jb_overline', 'ink_muted', align='center'), m, i],
                        gap=8, align_h='center', caption=f'Column {label}')

    height = column('Height', [with_unit(num_input('height_cm', '175'), 'cm')],
                    [with_unit(num_input('height_ft', '5'), 'ft'),
                     with_unit(num_input('height_in', '9'), 'in')])
    weight = column('Weight', [with_unit(num_input('weight_kg', '75'), 'kg')],
                    [with_unit(num_input('weight_lb', '165'), 'lb')])
    cols = fk.stack([height, weight], direction='horizontal', gap=24, align_v='center',
                    caption='Columns')
    top = fk.stack([hdr, header_block('Your metabolism', 'Your height and weight',
                                      'Used to calculate your calorie target. We never share '
                                      'this data.'), seg], caption='Top')
    cta = button('Continue', [fk.navigate('S7_activity', 'act_next')])
    scr = mk_screen('S6_body', [top, cols, cta], scroll=False, spread=True,
                    groups=[{'id': 'units', 'type': 'single_choice'}])
    return attach_progress(scr, hdr['id'], 's05')


def s7_activity():
    ids('el_s07')
    hdr = intro_header()
    opts = []
    for cid, emo, label, sub in (('sedentary', '🪑', 'Mostly sitting', 'Desk job, little movement'),
                                 ('light', '🚶', 'Lightly active', 'Walks, 1–2 workouts a week'),
                                 ('moderate', '🏃', 'Active', '3–5 workouts a week'),
                                 ('active', '🏋️', 'Very active', 'Training 6–7 days a week')):
        txt = fk.stack([T(label, 'in_title', 'ink'), T(sub, 'in_small', 'ink_muted')], gap=2)
        opts.append(option_card([T(emo, 'emoji_26', 'ink', width='hug'), txt, radio_ring()],
                                group='activity', cid=cid,
                                actions=[fk.navigate('S8_pain_points', 'act_next')]))
    top = fk.stack([hdr, header_block('Your metabolism', 'How active is your typical week?')],
                   caption='Top')
    lst = fk.stack(opts, gap=16, caption='Activity options')
    scr = mk_screen('S7_activity', [top, lst, spacer()], scroll=False, spread=True,
                    groups=[{'id': 'activity', 'type': 'single_choice'}])
    return attach_progress(scr, hdr['id'], 's06')


def s8_pain_points():
    ids('el_s08')
    hdr = intro_header()
    rows = []
    for cid, emo, label in (('too_long', '⏱️', 'Logging took too long'),
                            ('gave_up', '📉', 'I gave up after a few days'),
                            ('accuracy', '🤔', 'Never sure the calories were right'),
                            ('eating_out', '🍽️', 'Eating out broke everything'),
                            ('first_time', '🌱', 'First time tracking')):
        rows.append(option_card([T(emo, 'emoji_20', 'ink', width='hug'),
                                 T(label, 'in_title', 'ink'), checkbox()],
                                group='pain_points', cid=cid))
    top = fk.stack([hdr, header_block('Be honest', 'What made tracking hard before?',
                                      'Pick all that apply.')], caption='Top')
    lst = fk.stack(rows, gap=12, caption='Pain point options')
    cta = button('Continue', [fk.navigate('S9_problem', 'act_next')])
    scr = mk_screen('S8_pain_points', [top, lst, cta], scroll=False, spread=True,
                    groups=[{'id': 'pain_points', 'type': 'multi_choice'}])
    return attach_progress(scr, hdr['id'], 's07')


def cite_row(text, url):
    return fk.stack([T(text, 'in_caption', 'ink_faint'),
                     fk.icon('ArrowSquareOut', size_pt=12, color_id='info_blue')],
                    direction='horizontal', gap=4, align_v='center', margin=fk.pad(16, 0, 0, 0),
                    actions=[fk.open_url(url, external=True, action_id='act_cite')],
                    caption='Research link')


def s9_problem():
    ids('el_s09')
    hdr = intro_header()

    def bar_col(label, height, fill_id, number, strip=False):
        kids = []
        if strip:
            kids.append(fk.stack([], fixed_w=86, fixed_h=16, fill_=fk.fill('surplus_strip'),
                                 position=fk.absolute(top=0, left=0), caption='Surplus strip'))
        kids.append(T(number, 'in_caption', 'white', align='center',
                      margin=fk.pad(0, 0, 0, 8)))
        bar = fk.stack(kids, fixed_h=height, align_h='center', align_v='end',
                       fill_=fk.fill(fill_id), corner=fk.radius(12), caption=f'Bar {label}')
        bar['props']['layout']['clipContent'] = True
        return fk.stack([bar, T(label, 'in_small', 'ink_muted', align='center')], fixed_w=86,
                        gap=4, align_h='center', caption=f'Column {label}')

    bars = fk.stack([bar_col('In', 128, 'terracotta', '2,450', strip=True),
                     bar_col('Out', 112, 'ink', '2,200')], direction='horizontal', gap=20,
                    align_h='center', align_v='end', fixed_h=154, caption='Bars')
    cico = card([bars, T('+250 kcal a day ≈ +1 kg a month', 'in_body_strong', 'error',
                         align='center'),
                 T('Illustrative numbers', 'in_caption', 'ink_faint', align='center')],
                margin=fk.pad(20, 0, 0, 0), caption='CicoBalance (surplus phase, static)')

    def trap(emo, title, text):
        return card([T(emo, 'emoji_22', 'ink', width='hug'),
                     fk.stack([T(title, 'in_title', 'ink'), T(text, 'in_small', 'ink_muted')],
                              gap=2)], direction='horizontal', margin=fk.pad(12, 0, 0, 0),
                    caption='Trap card')

    content = fk.stack([
        eyebrow('The truth'),
        T('It all comes down to one thing', 'fr_h1', 'ink', margin=fk.pad(8, 0, 0, 0)),
        T(['Weight change is driven by one equation: ',
           Span('calories in vs. calories out.', bold=True, color='ink')], 'in_body',
          'ink_muted', margin=fk.pad(8, 0, 0, 0)),
        cico,
        T('Sounds simple. But two things quietly break it:', 'in_body', 'ink_muted',
          margin=fk.pad(20, 0, 0, 0)),
        trap('📏', 'The margin is tiny', 'The gap between losing and gaining is often just '
             '200–300 kcal a day. One dressing. One latte.'),
        trap('🎯', 'Guesses are usually wrong', 'Most people misjudge what they eat by 20–40%. '
             '"Feels healthy" doesn\'t mean the numbers add up.'),
        cite_row('Research: self-reported food intake is off by ~30% on average '
                 '(Lichtman et al., NEJM 1992).', 'https://pubmed.ncbi.nlm.nih.gov/1454084/'),
    ], padding=fk.pad(8, 0, 0, 16), caption='Problem content')
    foot = fk.footer([button("So what's the answer?", [fk.navigate('S10_fix', 'act_next')])],
                     fill_=fk.fill('bg'), padding=fk.pad(8, 20, 20, 16), gap=0)
    scr = mk_screen('S9_problem', [hdr, content, foot], scroll=True)
    return attach_progress(scr, hdr['id'], 's08')


def s10_fix():
    ids('el_s10')
    hdr = intro_header()

    def num_badge(n):
        return fk.stack([T(str(n), 'in_badge', 'white', align='center')], fixed_w=28,
                        fixed_h=28, align_h='center', align_v='center',
                        fill_=fk.fill('terracotta'), corner=fk.radius(8), caption='Number badge')

    def head(n, title):
        return fk.stack([num_badge(n), T(title, 'in_title', 'ink')], direction='horizontal',
                        gap=12, align_v='center')

    def macro(text, color, bg):
        return pill([T(text, 'in_caption', color, width='hug')], bg, pad_v=3, caption='Macro')

    proof = card([
        fk.stack([T('Oikos Greek yogurt, 150g', 'in_body_strong', 'ink'),
                  pill([T('◎ DANONE', 'jb_badge', 'info_blue', width='hug')], 'info_blue_soft',
                       pad_v=3, pad_h=8, caption='Source badge')],
                 direction='horizontal', gap=8, align_v='center'),
        fk.stack([T('90', 'fr_num34', 'ink', width='hug'),
                  T('kcal', 'in_small', 'ink_muted', width='hug')], direction='horizontal',
                 gap=4, align_v='end'),
        fk.stack([macro('P 15g', 'protein', 'olive_soft'), macro('F 0g', 'fat', 'warning_soft'),
                  macro('C 6g', 'carbs', 'info_blue_soft')], direction='horizontal', gap=8),
    ], gap=8, pad=12, fill_id='surface_alt', rad=12, caption='Proof meal card')
    fix1 = card([head(1, 'Precise — so it actually counts'),
                 T('Every meal checked against official databases and verified brand data — '
                   'USDA, restaurant menus, packaged foods. Not AI guesses.', 'in_small',
                   'ink_muted'), proof], caption='Fix card 1')
    chips = [pill([T(t, 'in_small', 'ink', width='hug')], 'surface_alt', 'hairline',
                  caption='Mode chip') for t in ('📷 Photo', '🎤 Voice', '⌨️ Text')]
    fix2 = card([head(2, 'Frictionless — so you keep it up'),
                 T('Log any meal in ~10 seconds — photo, text, or voice. No barcodes, no '
                   'scrolling.', 'in_small', 'ink_muted'),
                 fk.stack(chips, direction='horizontal', gap=8)], caption='Fix card 2')
    mascot = fk.stack([
        fk.image(**media('mood_great_t'), fit='fit', fixed_w=104, fixed_h=104,
                 caption='Mascot mood_great_t.png 104x104'),
        T("That's YumYummy", 'fr_label28', 'ink', width='hug'),
    ], direction='horizontal', gap=12, align_h='center', align_v='center',
        padding=fk.pad(8, 0, 0, 8), caption='Mascot row')
    content = fk.stack([
        fk.stack([eyebrow('The answer'),
                  T('So we built both into one app', 'fr_h1', 'ink', margin=fk.pad(8, 0, 0, 0))]),
        fk.stack([fix1, fix2], gap=16, padding=fk.pad(12, 0, 0, 12)),
        mascot,
    ], gap=8, padding=fk.pad(8, 0, 0, 16), caption='Fix content')
    foot = fk.footer([button('Build my plan', [fk.custom_action('quiz_done', 'act_done')])],
                     fill_=fk.fill('bg'), padding=fk.pad(12, 20, 20, 16), gap=0)
    scr = mk_screen('S10_fix', [hdr, content, foot], scroll=True)
    return attach_progress(scr, hdr['id'], 's09')


def build_onb():
    screens = [s1_welcome(), s2_goal(), s3_why(), s4_gender(), s5_age(), s6_body(),
               s7_activity(), s8_pain_points(), s9_problem(), s10_fix()]
    return fk.config(screens=screens, colors=COLORS, typography=TYPO,
                     components=progress_component())


# ------------------------------------------------------------------------------------------------
# Flow 2 — pw_main (Variant A, A_trial_all_v1 copy)
# ------------------------------------------------------------------------------------------------
PW = 'PW_A_trial_all'
TERMS_URL = 'https://yumyummy.ai/terms'      # placeholder per brief (app uses /terms.html)
PRIVACY_URL = 'https://yumyummy.ai/privacy'  # placeholder per brief (app uses /privacy.html)

# Declared so they show up in the builder's variable panel; NOT referenced (the reference form
# for a custom variable is unverified, flow-schema.md trap 4). Values = the app's own defaults.
CUSTOM_VARS = [
    {'id': 'var_HERO_LINE', 'name': 'HERO_LINE', 'valueType': 'string', 'value': ''},
    {'id': 'var_TARGET_WEIGHT', 'name': 'TARGET_WEIGHT', 'valueType': 'string', 'value': ''},
    {'id': 'var_TARGET_DATE', 'name': 'TARGET_DATE', 'valueType': 'string', 'value': ''},
    {'id': 'var_DAILY_KCAL', 'name': 'DAILY_KCAL', 'valueType': 'string', 'value': ''},
    {'id': 'var_GOAL', 'name': 'GOAL', 'valueType': 'string', 'value': ''},
    {'id': 'var_RATING', 'name': 'RATING', 'valueType': 'string', 'value': '4.9'},
    {'id': 'var_USERS', 'name': 'USERS', 'valueType': 'string', 'value': '12,000'},
]


def load_products():
    with open(os.path.join(HERE, 'products.json')) as f:
        p = json.load(f)
    return {k: (v['product_id'], v.get('offer_id') or None) for k, v in p.items()
            if not k.startswith('_')}


def build_pw():
    ids('el_pw')
    prods = load_products()
    trial_sel = fk.ref('plans.selectedProduct.is_free_trial')
    sel_trial = fk.when(fk.eq(trial_sel, fk.lit(True)))
    sel_paid = fk.when(fk.neq(trial_sel, fk.lit(True)))

    topbar = fk.stack([T('Restore', 'in_caption', 'ink_faint', width='hug',
                         actions=[fk.restore('act_restore')], caption='Restore (top)')],
                      direction='horizontal', align_h='end', padding=fk.pad(4, 0, 0, 4),
                      caption='Top bar')
    h1 = T('Nutrition tracking that finally works', 'fr_h1', 'ink', align='center',
           margin=fk.pad(4, 0, 0, 8))

    hero_line = T('<HERO_LINE/>', 'fr_h2', 'ink', align='center',
                  caption='Hero line (app customTag HERO_LINE, resolved per goal)')
    hero = fk.stack([eyebrow('Your plan — locked in', align='center'), hero_line],
                    gap=2, align_h='center', padding=fk.pad(12, 16, 16, 12),
                    fill_=fk.fill('surface'), corner=fk.radius(16), border='hairline',
                    border_width=0.5, margin=fk.pad(0, 0, 0, 8), caption='Hero card')

    laurels = [pill([T(t, 'in_caption', 'ink_muted', width='hug')], 'surface_alt',
                    caption='Laurel') for t in ('★ <RATING/> rating', '<USERS/>+ trackers',
                                                '✓ Verified data')]
    laurel_rows = fk.stack([
        fk.stack(laurels[:2], direction='horizontal', gap=8, align_h='center'),
        fk.stack(laurels[2:], direction='horizontal', gap=8, align_h='center'),
    ], gap=8, margin=fk.pad(0, 0, 0, 8), caption='Laurels')

    quote = card([T(Span('“Finally started losing — the numbers were just right.”', italic=True),
                    'in_body', 'ink', align='center'),
                  T('Maria · −4 kg in 6 weeks', 'in_caption', 'ink_muted', align='center')],
                 gap=4, pad=12, bw=0.5, margin=fk.pad(0, 0, 0, 8), align_h='center',
                 caption='Testimonial (not rendered by native Variant A)')

    def timeline(steps, caption, visibility):
        rows = []
        for i, (ic, done, title, desc) in enumerate(steps):
            last = i == len(steps) - 1
            chip = fk.stack([fk.icon(ic, size_pt=14, color_id='white' if done else 'terracotta',
                                     weight='bold' if done else 'regular')],
                            fixed_w=26, fixed_h=26, align_h='center', align_v='center',
                            fill_=fk.fill('done_green' if done else 'terracotta_soft'),
                            corner=fk.radius(13), position=fk.absolute(top=0, left=0),
                            caption='Step icon')
            kids = [chip]
            if not last:
                kids.append(fk.stack([], fixed_w=2, height='auto', fill_=fk.fill('hairline'),
                                     position=fk.absolute(top=30, left=12, bottom=2),
                                     caption='Connector'))
            kids.append(fk.stack([T(title, 'in_body_strong', 'ink'),
                                  T(desc, 'in_caption', 'ink_muted')], gap=1,
                                 padding=fk.pad(0, 38, 0, 8 if not last else 0)))
            rows.append(fk.stack(kids, direction='horizontal', caption='Step'))
        return fk.stack(rows, margin=fk.pad(0, 0, 0, 8), visibility=visibility, caption=caption)

    trial_tl = timeline([('Check', True, 'Done', 'Your personal plan — built'),
                         ('LockOpen', False, 'Today', 'Full access unlocked — you pay nothing'),
                         ('Bell', False, 'Day 2', "We'll remind you 24h before any charge"),
                         ('Star', False, 'Day 3', 'Trial ends — cancel anytime before')],
                        'Timeline (trial)', sel_trial)
    paid_tl = timeline([('Check', True, 'Done', 'Your personal plan — built'),
                        ('LockOpen', False, 'Today', 'Full access unlocked'),
                        ('Bell', False, 'Day 2', "You'll set up your full tracking system and "
                                                 'see how simple it is'),
                        ('Star', False, 'Day 3', "You'll start noticing changes in your routine "
                                                 'and eating trends')],
                       'Timeline (no trial — PAID_TIMELINE_STEPS)', sel_paid)

    def plan(key, cadence_trial, cadence_paid, badge=None, default=False):
        pid, offer = prods[key]
        pv = lambda f: Var(f'{pid}.{f}')  # noqa: E731
        p_trial = fk.when(fk.eq(fk.ref(f'{pid}.is_free_trial'), fk.lit(True)))
        p_paid = fk.when(fk.neq(fk.ref(f'{pid}.is_free_trial'), fk.lit(True)))
        dot = fk.stack([], fixed_w=11, fixed_h=11, corner=fk.radius(6), caption='Dot')
        fk.on_selected(dot, fill=fk.fill('terracotta'))
        ring = fk.stack([dot], fixed_w=22, fixed_h=22, align_h='center', align_v='center',
                        corner=fk.radius(11), border='hairline', border_width=1.5,
                        caption='Radio')
        fk.on_selected(ring, border={'color': fk.color('terracotta'), 'style': 'solid',
                                     'width': 1.5})
        sub_t = T([pv('offer_full_duration'), ' free trial, then ' + cadence_trial[0]]
                  + ([pv('prod_price')] if cadence_trial[1] else []), 'in_caption', 'ink_muted',
                  visibility=p_trial, caption='Sub (trial)')
        sub_p = T([cadence_paid[0]] + ([pv('prod_price')] if cadence_paid[1] else []),
                  'in_caption', 'ink_muted', visibility=p_paid, caption='Sub (no trial)')
        rec = T('✦ Recommended for building the habit', 'in_caption', 'protein',
                margin=fk.pad(4, 0, 0, 0), caption='Rec tag (selected only)')
        rec['props']['opacity'] = 0
        fk.on_selected(rec, opacity=100)
        info = fk.stack([T([pv('prod_price_per_week'), '/wk'], 'in_title', 'ink'), sub_t, sub_p,
                         rec], gap=0, caption='Plan info')
        row = fk.stack([ring, info], direction='horizontal', gap=12, align_v='center')
        kids = []
        if badge:
            kids.append(pill([T(badge, 'jb_overline', 'white', width='hug')], 'terracotta',
                             pad_v=2, pad_h=8, caption='Badge', margin=fk.pad(0, 0, 0, 4)))
            kids[-1]['props']['borderRadius'] = fk.radius(8)
        kids.append(row)
        card_ = fk.product(kids, product_id=pid, offer_id=offer, group_id='plans',
                           default=default, padding=fk.pad(12, 16, 16, 12),
                           fill_=fk.fill('surface'), corner=fk.radius(16), border='hairline',
                           border_width=1.5, caption=f'Plan {key}')
        fk.on_selected(card_, border={'color': fk.color('terracotta'), 'style': 'solid',
                                      'width': 1.5})
        return card_

    plans = fk.stack([
        plan('yearly', ('billed annually at ', True), ('billed annually at ', True),
             badge='BEST VALUE', default=True),
        plan('monthly', ('billed monthly at ', True), ('billed monthly at ', True)),
        plan('weekly', ('billed weekly', False), ('billed weekly', False)),
    ], gap=8, margin=fk.pad(0, 0, 0, 12), caption='Plan cards')

    above_t = T('✓ No payment due now · Cancel anytime', 'in_caption', 'done_green',
                align='center', visibility=sel_trial, caption='Above CTA (trial)')
    above_p = T('✓ Cancel anytime', 'in_caption', 'done_green', align='center',
                visibility=sel_paid, caption='Above CTA (no trial)')
    above = fk.stack([above_t, above_p], margin=fk.pad(0, 0, 0, 8), caption='Above CTA')

    cta = fk.stack([T('Start 3 days free now', 'in_button', 'white', align='center',
                      visibility=sel_trial, caption='CTA label (trial)'),
                    T('Continue', 'in_button', 'white', align='center', visibility=sel_paid,
                      caption='CTA label (no trial)')],
                   fixed_h=54, fill_=fk.fill('terracotta'), corner=fk.radius(12),
                   align_h='center', align_v='center', padding=fk.pad(0, 24, 24, 0),
                   actions=[fk.purchase('plans', 'act_buy')], caption='CTA purchase')

    legal_t = ('After the free trial, your subscription auto-renews at the price shown unless '
               'cancelled at least 24 hours before the end of the current period. Manage or '
               'cancel anytime in your Apple Account settings.')
    legal_p = ('Subscription auto-renews at the price shown unless cancelled at least 24 hours '
               'before the end of the current period. Manage or cancel anytime in your Apple '
               'Account settings.')
    disclosure = fk.stack([
        T(legal_t, 'in_caption', 'ink_faint', align='center', visibility=sel_trial,
          caption='Disclosure (trial)'),
        T(legal_p, 'in_caption', 'ink_faint', align='center', visibility=sel_paid,
          caption='Disclosure (no trial)'),
    ], margin=fk.pad(20, 0, 0, 0), caption='Disclosure')
    sep = lambda: T(' · ', 'in_caption', 'ink_faint', width='hug')  # noqa: E731
    links = fk.stack([
        T('Restore', 'in_caption', 'ink_faint', width='hug', actions=[fk.restore('act_restore')],
          caption='Restore (footer)'), sep(),
        T('Terms', 'in_caption', 'ink_faint', width='hug',
          actions=[fk.open_url(TERMS_URL, external=True, action_id='act_terms')],
          caption='Terms'), sep(),
        T('Privacy', 'in_caption', 'ink_faint', width='hug',
          actions=[fk.open_url(PRIVACY_URL, external=True, action_id='act_privacy')],
          caption='Privacy'),
    ], direction='horizontal', align_h='center', align_v='center', margin=fk.pad(16, 0, 0, 0),
        caption='Legal links')

    scr = fk.screen(PW, [topbar, h1, hero, laurel_rows, quote, trial_tl, paid_tl, plans, above,
                         cta, disclosure, links],
                    caption=PW, fill_=fk.fill('bg'), padding=fk.pad(0, GUTTER, GUTTER, 20),
                    scrollable=True, safe_area=True, status_bar_theme='light',
                    selectable_groups=[{'id': 'plans', 'type': 'product'}])
    meta = fk.predeclare(PW, [(p['id'], p.get('offerId')) for p in scr['products']])
    return fk.config(screens=[scr], colors=COLORS, typography=TYPO, variables=CUSTOM_VARS,
                     meta_screens=meta)


def main():
    out = {'onb_main.json': build_onb(), 'pw_main.json': build_pw()}
    for name, cfg in out.items():
        path = os.path.join(HERE, name)
        with open(path, 'w') as f:
            json.dump(cfg, f, ensure_ascii=False, indent=1)
        n = sum(len(s['elements']['map']) for s in cfg['screens'])
        print(f'{name}: {len(cfg["screens"])} screens, {n} elements -> {path}')


if __name__ == '__main__':
    main()
