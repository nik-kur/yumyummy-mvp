#!/usr/bin/env python3
"""Build the two single-plan Variant S paywall flows (intro-spec.md §P.3).

    python3 build_single.py   # writes pw_single_monthly.json and pw_single_weekly.json

Copy: repo config/paywalls/m_single_trial.json + w_single_trial.json (the CLI's `paywalls get`
returns no remote config). Theme + _meta.fonts are lifted from pw_main.working3.json (same app,
fonts uploaded in the builder), so typography is already bound to Fraunces / Inter / JetBrains Mono.
No custom tags anywhere (device test: the SDK did not substitute them).
"""
import copy
import json
import os

import build_flows as bf

fk, T, Span = bf.fk, bf.T, bf.Span
HERE = bf.HERE

TERMS_URL = 'https://yumyummy.ai/terms.html'
PRIVACY_URL = 'https://yumyummy.ai/privacy.html'
TAIL = (' Renews automatically unless cancelled at least 24 hours before the end of the current '
        'period. Cancel anytime in your Apple Account settings.')

PLANS = {
    'monthly': dict(flow='pw_single_monthly', screen='PW_S_monthly', prefix='el_pm',
                    product='cf5874b1-a1c2-46cc-900a-2ee04db8ddde', per='per month'),
    'weekly': dict(flow='pw_single_weekly', screen='PW_S_weekly', prefix='el_pk',
                   product='b14a44af-2a10-4f2a-9889-7e587cb6d149', per='per week'),
}

TRIAL_STEPS = [('Check', True, 'Done', 'Your personal plan — built'),
               ('LockOpen', False, 'Today', 'Full access unlocked — you pay nothing'),
               ('Bell', False, 'Day 2', "We'll remind you 24h before any charge"),
               ('Star', False, 'Day 3', 'Trial ends — cancel anytime before')]
PAID_STEPS = [('Check', True, 'Done', 'Your personal plan — built'),
              ('LockOpen', False, 'Today', 'Full access unlocked'),
              ('Bell', False, 'Day 2', "You'll set up your full tracking system and see how "
                                       'simple it is'),
              ('Star', False, 'Day 3', "You'll start noticing changes in your routine and "
                                       'eating trends')]

DIAL, RAIL_W, ROW_GAP = 40, 3, 16


def timeline(steps, caption, visibility):
    """§P.3 dial timeline: 40pt circle, 20pt icon, 3pt terracottaSoft rail with 4pt margins."""
    rows = []
    for i, (ic, done, title, desc) in enumerate(steps):
        last = i == len(steps) - 1
        dial = fk.stack([fk.icon(ic, size_pt=20, color_id='white' if done else 'terracotta',
                                 weight='bold' if done else 'regular')],
                        fixed_w=DIAL, fixed_h=DIAL, align_h='center', align_v='center',
                        fill_=fk.fill('done_green' if done else 'terracotta_soft'),
                        corner=fk.radius(DIAL // 2), position=fk.absolute(top=0, left=0),
                        caption='Dial')
        kids = [dial]
        if not last:
            kids.append(fk.stack([], fixed_w=RAIL_W, height='auto',
                                 fill_=fk.fill('terracotta_soft'), corner=fk.radius(2),
                                 position=fk.absolute(top=DIAL + 4, left=(DIAL - RAIL_W) / 2,
                                                      bottom=4),
                                 caption='Rail'))
        # paddingBottom 24 (spec 20) so the rail keeps its 20pt minimum: 24+20+24 = 68 = 40+4+20+4
        kids.append(fk.stack([T(title, 'in_title', 'ink'), T(desc, 'in_small_20', 'ink_muted')],
                             gap=2, padding=fk.pad(8, DIAL + ROW_GAP, 0, 0 if last else 24)))
        rows.append(fk.stack(kids, direction='horizontal', caption=f'Step {title}'))
    return fk.stack(rows, padding=fk.pad(0, 4, 4, 0), visibility=visibility, caption=caption)


def build(key):
    p = PLANS[key]
    bf.ids(p['prefix'])
    pid = p['product']
    trial = fk.ref(f'{pid}.is_free_trial')
    is_trial = fk.when(fk.eq(trial, fk.lit(True)))
    no_trial = fk.when(fk.neq(trial, fk.lit(True)))

    topbar = fk.stack([T('Restore', 'in_caption', 'ink_faint', width='hug',
                         actions=[fk.restore('act_restore')], caption='Restore (top)')],
                      direction='horizontal', align_h='end', padding=fk.pad(4, 0, 0, 4),
                      caption='Top bar')
    h1 = T('Nutrition tracking that finally works', 'fr_h1', 'ink', align='center',
           margin=fk.pad(24, 0, 0, 8))
    laurel = fk.stack([bf.pill([T('✓ Verified data', 'in_caption', 'ink_muted', width='hug')],
                               'surface_alt', caption='Laurel')],
                      direction='horizontal', align_h='center', caption='Laurels (static only)')
    tl = fk.stack([timeline(TRIAL_STEPS, 'Timeline (trial)', is_trial),
                   timeline(PAID_STEPS, 'Timeline (no trial — PAID_TIMELINE_STEPS)', no_trial)],
                  padding=fk.pad(44, 0, 0, 20), caption='Timeline centerpiece')
    # Price variables resolve only against a declared product, and only a `product` element can
    # be attached to -> hidden attach point (patterns.md "A single-plan screen"). Not a card.
    attach = fk.attach_point(product_id=pid, group_id='plan')

    price = bf.Var(f'{pid}.prod_price')
    terms = fk.stack([
        T(['Free for 3 days, then ', price, f" {p['per']}." + TAIL], 'in_caption_15',
          'ink_faint', align='center', visibility=is_trial, caption='Terms (trial)'),
        T([price, f" {p['per']}." + TAIL], 'in_caption_15', 'ink_faint', align='center',
          visibility=no_trial, caption='Terms (no trial)'),
    ], caption='Terms line')
    above = fk.stack([
        T('✓ No payment due now · Cancel anytime', 'in_caption', 'done_green', align='center',
          visibility=is_trial, caption='Above CTA (trial)'),
        T('✓ Cancel anytime', 'in_caption', 'done_green', align='center', visibility=no_trial,
          caption='Above CTA (no trial)'),
    ], caption='Above CTA')
    buy = {'id': 'act_buy', 'type': 'purchase',
           'payload': {'product': {'type': 'const', 'value': {'id': pid}}}}
    cta = fk.stack([T('Start my 3-day free trial', 'in_button', 'white', align='center',
                      visibility=is_trial, caption='CTA label (trial)'),
                    T('Continue', 'in_button', 'white', align='center', visibility=no_trial,
                      caption='CTA label (no trial)')],
                   fixed_h=54, fill_=fk.fill('terracotta'), corner=fk.radius(12),
                   align_h='center', align_v='center', padding=fk.pad(0, 24, 24, 0),
                   actions=[buy], caption='CTA purchase')
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
    ], direction='horizontal', align_h='center', align_v='center', caption='Legal links')
    foot = fk.footer([above, cta, terms, links], fill_=fk.fill('bg'),
                     padding=fk.pad(8, 20, 20, 8), gap=12, align_v='start')

    scr = fk.screen(p['screen'], [topbar, h1, laurel, tl, attach, foot], caption=p['screen'],
                    fill_=fk.fill('bg'), padding=fk.pad(0, bf.GUTTER, bf.GUTTER, 16),
                    scrollable=True, safe_area=True, status_bar_theme='light',
                    selectable_groups=[{'id': 'plan', 'type': 'product'}])
    meta = fk.predeclare(p['screen'], [(x['id'], x.get('offerId')) for x in scr['products']])
    extra = [('in_small_20', 'Inter 400 · Small 14/20', 14, 'regular', 20),
             ('in_caption_15', 'Inter 500 · Terms 12/15', 12, 'medium', 15)]
    cfg = fk.config(screens=[scr], colors=bf.COLORS, typography=bf.TYPO + extra,
                    meta_screens=meta)

    # Theme + fonts from the builder-saved pw_main (fonts uploaded there, same app).
    src = json.load(open(os.path.join(HERE, 'pw_main.working3.json')))['config']
    fams = {t['id']: t['settings'].get('family') for t in src['theme']['typography']}
    theme = copy.deepcopy(src['theme'])
    have = {t['id'] for t in theme['typography']}
    for t in cfg['theme']['typography']:
        if t['id'] not in have:        # the two new presets: bind the same faces
            t = copy.deepcopy(t)
            t['settings']['family'] = copy.deepcopy(
                fams['in_small'] if t['id'] == 'in_small_20' else fams['in_caption'])
            theme['typography'].append(t)
    cfg['theme'] = theme
    cfg['_meta']['fonts'] = copy.deepcopy(src['_meta']['fonts'])
    return p['flow'], cfg


def main():
    for key in PLANS:
        name, cfg = build(key)
        path = os.path.join(HERE, name + '.json')
        with open(path, 'w') as f:
            json.dump(cfg, f, ensure_ascii=False, indent=1)
        print(f"{name}: {len(cfg['screens'][0]['elements']['map'])} elements -> {path}")


if __name__ == '__main__':
    main()
