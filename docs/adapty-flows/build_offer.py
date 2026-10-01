#!/usr/bin/env python3
"""Build the after-cancel offer paywall flow `pw_after_cancel` (screen PW_OFFER_weekly299).

    python3 build_offer.py    # writes pw_after_cancel.json

Theme + fonts lifted from pw_single_monthly.working.json (variant S, same app). No custom tags.
"""
import copy
import json
import os

import build_flows as bf
import build_single as bs

fk, T = bf.fk, bf.T
HERE = bf.HERE
PID = '394d6da2-9b85-4674-9fd2-f172c0bad724'   # ai.yumyummy.app.weekly2.99.3d
SCREEN = 'PW_OFFER_weekly299'


def build():
    bf.ids('el_po')
    trial = fk.ref(f'{PID}.is_free_trial')
    is_trial = fk.when(fk.eq(trial, fk.lit(True)))
    no_trial = fk.when(fk.neq(trial, fk.lit(True)))
    price = bf.Var(f'{PID}.prod_price')
    lead = 'Same full access, lower price. '
    tail = ' a week instead of the regular weekly plan.'

    head = fk.stack([
        bf.eyebrow('One-time offer', align='center'),
        T('Not ready yet? Try it for less', 'fr_h1', 'ink', align='center',
          margin=fk.pad(4, 0, 0, 0)),
        T([lead + '3 days free, then ', price, tail], 'in_body', 'ink_muted', align='center',
          visibility=is_trial, caption='Body (trial)'),
        T([lead, price, tail], 'in_body', 'ink_muted', align='center', visibility=no_trial,
          caption='Body (no trial)'),
    ], gap=8, align_h='center', caption='Offer header')

    badge = bf.pill([T('LOWER PRICE', 'jb_overline', 'white', width='hug')], 'terracotta',
                    pad_v=2, pad_h=8, caption='Badge')
    badge['props']['borderRadius'] = fk.radius(8)
    row = fk.stack([T('Weekly', 'in_title', 'ink'),
                    T([price, '/week'], 'in_title', 'ink', align='right', width='hug')],
                   direction='horizontal', gap=12, align_v='center', caption='Plan row')
    sub = T('3 days free, then billed weekly', 'in_caption', 'ink_muted', visibility=is_trial,
            caption='Plan sub (trial)')
    sub_p = T('Billed weekly', 'in_caption', 'ink_muted', visibility=no_trial,
              caption='Plan sub (no trial)')
    # One card, always the (only) selection: the highlight is its base look, not a state.
    card = fk.product([badge, row, sub, sub_p], product_id=PID, group_id='offer', default=True,
                      gap=6, padding=fk.pad(14, 16, 16, 14), fill_=fk.fill('surface'),
                      corner=fk.radius(16), border='terracotta', border_width=1.5,
                      margin=fk.pad(24, 0, 0, 0), caption='Offer plan card')

    content = fk.stack([head, card], padding=fk.pad(96, 0, 0, 16), caption='Offer content')

    buy = {'id': 'act_buy', 'type': 'purchase',
           'payload': {'product': {'type': 'const', 'value': {'id': PID}}}}
    cta = fk.stack([T('Start 3 days free', 'in_button', 'white', align='center',
                      visibility=is_trial, caption='CTA label (trial)'),
                    T('Continue', 'in_button', 'white', align='center', visibility=no_trial,
                      caption='CTA label (no trial)')],
                   fixed_h=54, fill_=fk.fill('terracotta'), corner=fk.radius(12),
                   align_h='center', align_v='center', padding=fk.pad(0, 24, 24, 0),
                   actions=[buy], caption='CTA purchase')
    dismiss = T('No thanks, back to plans', 'in_small', 'ink_muted', align='center',
                actions=[fk.custom_action('offer_dismiss', 'act_dismiss')],
                caption='Dismiss link (custom offer_dismiss)')
    tail_terms = (' per week. Renews automatically unless cancelled at least 24 hours before the '
                  'end of the current period. Cancel anytime in your Apple Account settings.')
    terms = fk.stack([
        T(['Free for 3 days, then ', price, tail_terms], 'in_caption_15', 'ink_faint',
          align='center', visibility=is_trial, caption='Terms (trial)'),
        T([price, tail_terms], 'in_caption_15', 'ink_faint', align='center',
          visibility=no_trial, caption='Terms (no trial)'),
    ], caption='Terms line')
    sep = lambda: T(' · ', 'in_caption', 'ink_faint', width='hug')  # noqa: E731
    links = fk.stack([
        T('Restore', 'in_caption', 'ink_faint', width='hug', actions=[fk.restore('act_restore')],
          caption='Restore'), sep(),
        T('Terms', 'in_caption', 'ink_faint', width='hug',
          actions=[fk.open_url(bs.TERMS_URL, external=True, action_id='act_terms')],
          caption='Terms'), sep(),
        T('Privacy', 'in_caption', 'ink_faint', width='hug',
          actions=[fk.open_url(bs.PRIVACY_URL, external=True, action_id='act_privacy')],
          caption='Privacy'),
    ], direction='horizontal', align_h='center', align_v='center', caption='Legal links')
    foot = fk.footer([cta, dismiss, terms, links], fill_=fk.fill('bg'),
                     padding=fk.pad(8, 20, 20, 8), gap=12, align_v='start')

    scr = fk.screen(SCREEN, [content, foot], caption=SCREEN, fill_=fk.fill('bg'),
                    padding=fk.pad(0, bf.GUTTER, bf.GUTTER, 16), scrollable=True,
                    safe_area=True, status_bar_theme='light',
                    selectable_groups=[{'id': 'offer', 'type': 'product'}])
    meta = fk.predeclare(SCREEN, [(x['id'], x.get('offerId')) for x in scr['products']])
    cfg = fk.config(screens=[scr], colors=bf.COLORS, typography=bf.TYPO, meta_screens=meta)
    src = json.load(open(os.path.join(HERE, 'pw_single_monthly.working.json')))['config']
    cfg['theme'] = copy.deepcopy(src['theme'])
    cfg['_meta']['fonts'] = copy.deepcopy(src['_meta']['fonts'])
    return cfg


if __name__ == '__main__':
    cfg = build()
    path = os.path.join(HERE, 'pw_after_cancel.json')
    with open(path, 'w') as f:
        json.dump(cfg, f, ensure_ascii=False, indent=1)
    print(f"pw_after_cancel: {len(cfg['screens'][0]['elements']['map'])} elements -> {path}")
