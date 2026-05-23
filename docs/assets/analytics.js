/* ===================================================================
   YumYummy — Web Analytics (PostHog)
   ===================================================================
   What this file does
   - Loads PostHog with `person_profiles: 'always'` so every visitor
     (including anonymous LP traffic from paid ads) gets a person
     profile and `$initial_utm_*` properties are auto-populated.
   - Captures pageviews (manually inside the `loaded` callback so they
     carry registered UTM super-properties from the very first event)
     and pageleaves.
   - Registers `utm_*` / `gclid` / `fbclid` / `ttclid` from the landing
     URL as PostHog super-properties so they appear on **every** event
     this browser sends, not just on the person profile. Event-level
     breakdowns by campaign/creative in the PostHog UI then work
     without having to know it's a person property.
   - Fires a custom `landed_from_ad` event once per session for any
     visitor with utm_source, giving us a clean first step for the
     paid-acquisition funnel.
   - Captures a custom "cta_clicked" event for any link/button that
     either points at the Telegram bot OR is explicitly tagged with
     a `data-cta` attribute, with explicit cta_id / cta_location / utm_*
     properties so we can build a proper attribution funnel in PostHog.
   - Rewrites every Telegram bot link (https://t.me/yum_yummybot...)
     to include `?start=<posthog_distinct_id>` so the bot can identify
     the same person on the backend and continue the funnel
     (web pageview → bot start → trial → subscription) in one place.
   - Forwards UTM tags from the page URL into a sessionStorage cache so
     they're preserved across in-page navigation (footer links, etc).
   =================================================================== */

(function () {
  // -- 1. PostHog snippet (official, copied verbatim from the dashboard)
  !function(t,e){var o,n,p,r;e.__SV||(window.posthog=e,e._i=[],e.init=function(i,s,a){function g(t,e){var o=e.split(".");2==o.length&&(t=t[o[0]],e=o[1]),t[e]=function(){t.push([e].concat(Array.prototype.slice.call(arguments,0)))}}(p=t.createElement("script")).type="text/javascript",p.crossOrigin="anonymous",p.async=!0,p.src=s.api_host.replace(".i.posthog.com","-assets.i.posthog.com")+"/static/array.js",(r=t.getElementsByTagName("script")[0]).parentNode.insertBefore(p,r);var u=e;for(void 0!==a?u=e[a]=[]:a="posthog",u.people=u.people||[],u.toString=function(t){var e="posthog";return"posthog"!==a&&(e+="."+a),t||(e+=" (stub)"),e},u.people.toString=function(){return u.toString(1)+".people (stub)"},o="init me ls ks ws ys ps bs capture Ee calculateEventProperties $s register register_once register_for_session unregister unregister_for_session Is getFeatureFlag getFeatureFlagPayload isFeatureEnabled reloadFeatureFlags updateEarlyAccessFeatureEnrollment getEarlyAccessFeatures on onFeatureFlags onSurveysLoaded onSessionId getSurveys getActiveMatchingSurveys renderSurvey canRenderSurvey canRenderSurveyAsync identify setPersonProperties group resetGroups setPersonPropertiesForFlags resetPersonPropertiesForFlags setGroupPropertiesForFlags resetGroupPropertiesForFlags reset _addCaptureHook _calculateEventProperties _handle_unload _handle_queued_event __compress_and_send_json_request _send_request opt_in_capturing opt_out_capturing has_opted_in_capturing has_opted_out_capturing clear_opt_in_out_capturing _is_bot _send_pageview".split(" "),n=0;n<o.length;n++)g(u,o[n]);e._i.push([i,s,a])},e.__SV=1)}(document,window.posthog||[]);

  // -- 1a. Pre-allocate a stable distinct_id BEFORE PostHog finishes
  //        loading. Why: rewriteBotLinks() needs ?phid=<id> on the CTA
  //        href at the moment the user taps it. On slow Android Chrome
  //        on tier-3 mobile networks PostHog's array.js can take >2 s
  //        to load and assign a distinct_id, so the original retry loop
  //        (20 × 100 ms) would expire and CTAs would ship without phid.
  //        May 20 Meta launch replays showed 4 of 6 handoffs hit /open
  //        with no phid, which broke the LP→bot→trial identity
  //        stitching in PostHog.
  //
  //        Solution: we generate a UUID v4 ourselves, persist it in
  //        localStorage, and pass it to posthog.init as
  //        `bootstrap.distinctID`. PostHog then adopts our id as its
  //        own distinct_id (no random reassignment), so the same
  //        identity is used end-to-end: web events, /open ?phid=,
  //        Telegram /start payload, and bot_started server event.
  function uuidv4() {
    try {
      if (window.crypto && typeof crypto.randomUUID === 'function') {
        return crypto.randomUUID();
      }
    } catch (e) {}
    var rnd = new Array(16);
    if (window.crypto && typeof crypto.getRandomValues === 'function') {
      var buf = new Uint8Array(16);
      crypto.getRandomValues(buf);
      for (var i = 0; i < 16; i++) rnd[i] = buf[i];
    } else {
      for (var j = 0; j < 16; j++) rnd[j] = Math.floor(Math.random() * 256);
    }
    rnd[6] = (rnd[6] & 0x0f) | 0x40;
    rnd[8] = (rnd[8] & 0x3f) | 0x80;
    var hex = rnd.map(function (b) { return (b + 0x100).toString(16).slice(1); });
    return (hex[0]+hex[1]+hex[2]+hex[3]+'-'+hex[4]+hex[5]+'-'+
            hex[6]+hex[7]+'-'+hex[8]+hex[9]+'-'+
            hex[10]+hex[11]+hex[12]+hex[13]+hex[14]+hex[15]);
  }

  function getOrCreatePhid() {
    // Telegram bot /start payload accepts [A-Za-z0-9_-]{1,64}.
    // A canonical UUID v4 is 36 chars with [0-9a-f-], well within the
    // allowed alphabet, so we can reuse the same value for both the
    // PostHog distinct_id and the Telegram start payload.
    try {
      var existing = window.localStorage && localStorage.getItem('yy_phid');
      if (existing && /^[A-Za-z0-9_-]{1,64}$/.test(existing)) return existing;
    } catch (e) {}
    var fresh = uuidv4();
    try {
      if (window.localStorage) localStorage.setItem('yy_phid', fresh);
    } catch (e) {}
    return fresh;
  }

  var bootstrapPhid = getOrCreatePhid();

  // We disable `capture_pageview` here and fire it ourselves AFTER
  // registering UTMs as super-properties. Otherwise PostHog's auto
  // $pageview races the snippet's async `array.js` load and the very
  // first pageview event lands without `utm_*` super-properties
  // attached — which is exactly the bug we're trying to fix.
  posthog.init('phc_u8XVgBexJVuggFASRTw7AL6mmpwoZDa6moycSxz7FrpD', {
    api_host: 'https://eu.i.posthog.com',
    // Hand PostHog our pre-allocated distinct_id so it doesn't generate
    // its own UUID v7 and we end up with two identities for the same
    // person (one on /, one on /open). The PostHog SDK persists this
    // value in its own localStorage key on first load and reuses it
    // for every subsequent event from this browser.
    bootstrap: { distinctID: bootstrapPhid },
    // 'always' (vs 'identified_only') creates a person profile for every
    // visitor — anonymous LP visitors included — so PostHog auto-fills
    // person properties like `$initial_utm_source/medium/campaign/...`
    // on the very first pageview. With 'identified_only' the LP never
    // calls identify(), so ~20% of visitors had no person profile and
    // breakdowns by initial_utm_* were missing them entirely. The cost
    // tradeoff is acceptable: every paid-traffic visitor is worth a
    // person row for attribution, and we'll filter bots out at the
    // dashboard level (or via PostHog's bot blocklist).
    person_profiles: 'always',
    capture_pageview: false,
    capture_pageleave: true,
    loaded: function (ph) {
      // `loaded` fires once the real array.js has replaced the stub
      // and the SDK has assigned a distinct_id. Register UTMs as
      // super-properties FIRST, then send the initial pageview, so
      // that pageview carries `utm_source`/`utm_campaign`/etc. and
      // PostHog's auto-attribution lands the person on the right
      // initial campaign on the very first event.
      try {
        attributeUtmsToPostHog();
        syncDeviceContextToPostHog();
        captureLandedFromAd();
        ph.capture('$pageview');
      } catch (e) {}
    },
  });

  // -- 2. Helpers ----------------------------------------------------

  // Anything that ultimately lands the user in the Telegram bot:
  //   1. Direct t.me/yum_yummybot links (legacy CTAs, footer links,
  //      hard-coded links inside the bot fallback UI).
  //   2. Our own /open deep-link bridge page, which then fires
  //      tg://resolve and falls back to t.me. Introduced to bypass
  //      TikTok / Meta / Twitter in-app webviews that intercept
  //      universal links on t.me/*.
  //
  // We treat both forms as "bot target" for two purposes:
  //   - rewriteBotLinks() — appends ?phid, ?start, and ?utm_* so the
  //     bot (or /open) has full attribution context.
  //   - bindCtaTracking() — fires cta_clicked with target_is_bot:true
  //     and mirrors the click to Meta+TikTok as a Lead.
  var DIRECT_BOT_RE = /^https?:\/\/(?:t|telegram)\.me\/yum_yummybot/i;
  var OPEN_PAGE_RE = /^(?:\/open(?:[\/?#]|$)|https?:\/\/(?:[^/]*\.)?yumyummy\.ai\/open(?:[\/?#]|$))/i;
  // Kept for backwards-compat with any inline call site that might
  // still reference the original name.
  var BOT_HOST_RE = DIRECT_BOT_RE;

  function isBotTarget(href) {
    if (!href) return false;
    return DIRECT_BOT_RE.test(href) || OPEN_PAGE_RE.test(href);
  }

  var UTM_KEYS = [
    'utm_source', 'utm_medium', 'utm_campaign',
    'utm_term', 'utm_content', 'gclid', 'fbclid', 'ttclid'
  ];

  // Meta and TikTok pixels each drop browser-level cookies that we
  // want to keep alongside our PostHog person profile:
  //   _fbp  — Meta browser id, set on the very first PageView and
  //           persisted across pages.
  //   _fbc  — Meta click id, set when the visitor lands with
  //           ?fbclid=... and used to attribute later conversions
  //           back to the originating ad click.
  //   _ttp  — TikTok browser id, set on the very first ttq.page()
  //           and persisted across pages.
  //   ttclid — TikTok click id, only present in the URL when the
  //           visitor lands from a TikTok ad. Captured into our
  //           sessionStorage UTM cache (UTM_KEYS) so we don't need
  //           to read it from a cookie.
  // Stashing these on the PostHog person profile means that when we
  // later wire up the Meta Conversions API and TikTok Events API
  // server-side (to send `Subscribe`/`StartTrial` from the bot
  // backend), we can look up the right fbp/fbc/ttp by
  // posthog_distinct_id and properly deduplicate browser + server
  // events.
  function readPixelCookies() {
    var out = {};
    try {
      document.cookie.split(';').forEach(function (c) {
        var idx = c.indexOf('=');
        if (idx === -1) return;
        var name = c.slice(0, idx).trim();
        if (name === '_fbp' || name === '_fbc' || name === '_ttp') {
          out[name] = decodeURIComponent(c.slice(idx + 1));
        }
      });
    } catch (e) {}
    return out;
  }

  function syncPixelsToPostHog() {
    if (!window.posthog || typeof posthog.register !== 'function') return;
    var ck = readPixelCookies();
    var props = {};
    if (ck._fbp) props.$fbp = ck._fbp;
    if (ck._fbc) props.$fbc = ck._fbc;
    if (ck._ttp) props.$ttp = ck._ttp;
    if (currentUtms.ttclid) props.$ttclid = currentUtms.ttclid;
    if (!Object.keys(props).length) return;
    try {
      posthog.register(props);
      if (typeof posthog.setPersonProperties === 'function') {
        posthog.setPersonProperties(props);
      }
    } catch (e) {}
  }

  // -- Server-side attribution push --------------------------------
  //
  // Meta CAPI scores every server event by Event Match Quality (EMQ).
  // The strongest match keys are fbp/fbc (set by the browser pixel) plus
  // client IP and User-Agent. PostHog's Persons API can surface fbp/fbc
  // (we already stash them on the person profile in syncPixelsToPostHog)
  // but NOT IP — PostHog stores `$ip` on the event row, not the person
  // row, so the lookup our backend does for CAPI sees a null IP every
  // time. Result: EMQ ~2-3/10 and zero campaign attribution.
  //
  // To fix that, we POST the same match keys (+ landing URL + UTMs)
  // straight to our backend so it can persist them in `landing_attribution`
  // keyed by phid. The backend grabs the real client IP from the request
  // headers (Render fronts us with X-Forwarded-For) and the UA from the
  // request headers — both of which the browser can't reliably tell us
  // and PostHog can't reliably forward. When the same user then hits
  // /start in the bot, the Meta CAPI client looks up that row by phid
  // and ships fbp + fbc + IP + UA + external_id in user_data, lifting
  // EMQ to ~7+/10.
  //
  // The push is fire-and-forget via navigator.sendBeacon so it survives
  // page unloads (critical: the user typically taps the CTA right after
  // the LP loads). Idempotent on the server side — same phid pushing
  // again merges fresh non-null values without overwriting earlier
  // signals (e.g. fbclid that was on the LP URL but isn't on
  // subsequent in-app navigations).
  var ATTRIBUTION_API_URL = 'https://yumyummy-mvp-eu.onrender.com/api/v1/landing-attribution';
  var lastAttributionHash = null;

  function pushLandingAttribution() {
    if (!bootstrapPhid) return;
    var ck = readPixelCookies();
    var url = '';
    try { url = window.location && window.location.href ? String(window.location.href) : ''; } catch (e) {}
    var payload = {
      phid: bootstrapPhid,
      fbp: ck._fbp || null,
      fbc: ck._fbc || null,
      fbclid: currentUtms.fbclid || null,
      ttp: ck._ttp || null,
      ttclid: currentUtms.ttclid || null,
      landing_url: url || null,
      utm_source: currentUtms.utm_source || null,
      utm_medium: currentUtms.utm_medium || null,
      utm_campaign: currentUtms.utm_campaign || null,
      utm_term: currentUtms.utm_term || null,
      utm_content: currentUtms.utm_content || null,
    };
    var body;
    try { body = JSON.stringify(payload); } catch (e) { return; }
    // De-duplicate: only fire when something actually changed since the
    // last push. Without this we'd send 3-4 identical requests per page
    // load (initial sync, pixel settle timer, pre-CTA refresh).
    if (body === lastAttributionHash) return;
    try {
      if (navigator && typeof navigator.sendBeacon === 'function') {
        // sendBeacon with an application/json Blob triggers a CORS
        // preflight, which the backend accepts via the CORSMiddleware
        // it enables for yumyummy.ai. The preflight cost is paid once
        // per origin (browser caches OPTIONS for 24h).
        var blob = new Blob([body], { type: 'application/json' });
        var ok = navigator.sendBeacon(ATTRIBUTION_API_URL, blob);
        if (ok) {
          lastAttributionHash = body;
          return;
        }
      }
      // Fallback for browsers without sendBeacon, or when the beacon
      // queue is full. `keepalive` lets the request finish even after
      // the page navigates away (same survivability as sendBeacon).
      if (typeof fetch === 'function') {
        fetch(ATTRIBUTION_API_URL, {
          method: 'POST',
          body: body,
          headers: { 'Content-Type': 'application/json' },
          keepalive: true,
          mode: 'cors',
          credentials: 'omit',
        }).catch(function () {});
        lastAttributionHash = body;
      }
    } catch (e) {}
  }

  // Server-side ad attribution (Meta CAPI, TikTok EAPI) needs the raw
  // User-Agent and the actual landing URL — Meta's match-quality scoring
  // weighs these heavily (~+2 EMQ points combined). PostHog auto-captures
  // a parsed $browser / $os but NOT the raw UA string, so we stash it
  // ourselves on the person profile as `raw_user_agent`. We also keep
  // the first landing URL with full UTM/fbclid in `initial_landing_url`
  // so the backend can pass it as `event_source_url` instead of the
  // homepage default.
  function syncDeviceContextToPostHog() {
    if (!window.posthog || typeof posthog.setPersonProperties !== 'function') return;
    try {
      var ua = navigator && navigator.userAgent ? String(navigator.userAgent) : '';
      var url = '';
      try { url = window.location && window.location.href ? String(window.location.href) : ''; } catch (e) {}
      var props = {};
      if (ua) props.raw_user_agent = ua;
      if (url) props.initial_landing_url = url;
      if (!Object.keys(props).length) return;
      // $set_once-style: only the first landing URL wins (so attribution
      // sticks to the very first ad click, not the most recent visit).
      var initialOnly = {};
      if (url) initialOnly.initial_landing_url = url;
      // raw_user_agent we keep refreshed because the same person can
      // legitimately switch browser/device between sessions.
      posthog.setPersonProperties(props, initialOnly);
    } catch (e) {}
  }

  // Persist UTMs from the first landing URL into sessionStorage so
  // they survive in-page navigation. Telegram bot links across the
  // site (CTA buttons, footer links, etc.) all read from this cache,
  // not from window.location, so a user who lands on /?utm_source=tt
  // and then clicks "Open in Telegram" from /privacy still carries
  // tt as their attribution.
  function readUtms() {
    var qs = new URLSearchParams(window.location.search);
    var fromUrl = {};
    var hasAny = false;
    UTM_KEYS.forEach(function (k) {
      var v = qs.get(k);
      if (v) { fromUrl[k] = v; hasAny = true; }
    });
    if (hasAny) {
      try { sessionStorage.setItem('yy_utms', JSON.stringify(fromUrl)); } catch (e) {}
      return fromUrl;
    }
    try {
      var cached = sessionStorage.getItem('yy_utms');
      if (cached) return JSON.parse(cached);
    } catch (e) {}
    return {};
  }

  var currentUtms = readUtms();

  // Attach the visitor's UTMs to both their event stream and their
  // person profile so attribution is queryable two ways:
  //
  //   1. `posthog.register(utms)` — adds the UTMs as **super-properties**,
  //      meaning every event from this browser (pageviews, cta_clicked,
  //      $autocapture, $web_vitals, etc.) will carry `properties.utm_source`,
  //      `properties.utm_campaign`, etc. PostHog UI breakdowns at the event
  //      level (Trends, Funnels filtered by `event property`) then "just
  //      work" without us having to remember it's a person property.
  //
  //   2. `posthog.setPersonProperties({...}, $initial...)` — writes them
  //      to the person profile. PostHog already auto-fills `$initial_utm_*`
  //      from $pageview's $current_url, but we set them explicitly too as a
  //      belt-and-suspenders measure for the rare path where the UTM cache
  //      was hydrated from sessionStorage rather than the current URL
  //      (e.g. user navigated to /privacy first and came back to /).
  //
  // The split also matters for the bot funnel: when the bot later sends
  // `bot_started` from the backend using the same posthog_distinct_id,
  // PostHog stitches it to this person and inherits `$initial_utm_*`.
  // That's how the LP→bot→trial→subscription funnel becomes filterable
  // by campaign/creative in one place.
  function attributeUtmsToPostHog() {
    if (!window.posthog) return;
    var hasUtm = false;
    var props = {};
    UTM_KEYS.forEach(function (k) {
      if (currentUtms[k]) {
        props[k] = currentUtms[k];
        hasUtm = true;
      }
    });
    if (!hasUtm) return;

    try {
      if (typeof posthog.register === 'function') {
        posthog.register(props);
      }
      if (typeof posthog.setPersonProperties === 'function') {
        // The second arg `$set_once` semantics — only set initial_* on
        // first touch, so the *first* paid campaign that brought a
        // visitor wins attribution even if they come back later from a
        // different ad. Acquisition cost should be paid to the campaign
        // that actually acquired them.
        var initialProps = {};
        Object.keys(props).forEach(function (k) {
          initialProps['initial_' + k] = props[k];
        });
        posthog.setPersonProperties(props, initialProps);
      }
    } catch (e) {}
  }

  function captureLandedFromAd() {
    if (!window.posthog || typeof posthog.capture !== 'function') return;
    if (!currentUtms.utm_source) return;
    // Idempotency: only fire once per session, even if the user
    // navigates between pages on the same site. Without this we'd
    // double-count a landed_from_ad for /privacy or /support visits
    // after the initial / pageview.
    try {
      if (sessionStorage.getItem('yy_landed_fired') === '1') return;
      sessionStorage.setItem('yy_landed_fired', '1');
    } catch (e) {}
    try {
      posthog.capture('landed_from_ad', Object.assign({
        landing_path: window.location.pathname,
        landing_url: window.location.href,
      }, currentUtms));
    } catch (e) {}
  }

  // Telegram deep-link start params accept [A-Za-z0-9_-]{1,64}.
  // PostHog distinct_ids are UUIDs by default (e.g.
  // "0190abcd-1234-7890-abcd-ef1234567890") which fits.
  function isValidStartParam(s) {
    return typeof s === 'string' && /^[A-Za-z0-9_-]{1,64}$/.test(s);
  }

  // Pick the best deep-link start param for the bot:
  //   1. PostHog distinct_id — preferred so the bot's first /start
  //      lands on the same person profile that already has the web
  //      pageview + utm_* properties attached. The full funnel
  //      (LP pageview → bot signup → trial → subscription) then
  //      flows through one identity in PostHog without any joins.
  //   2. utm_source as a fallback for the rare case PostHog never
  //      assigned a distinct_id (e.g. ad-blocker), so we still get
  //      campaign-level attribution in users.acquisition_source.
  function pickStartParam(distinctId) {
    if (distinctId && isValidStartParam(distinctId)) return distinctId;
    var src = (currentUtms.utm_source || '').toString().trim();
    if (src && isValidStartParam(src)) return src;
    return null;
  }

  // Decorate every "bot-bound" anchor on the page with attribution
  // params so the funnel is reconstructable end-to-end:
  //
  //   - LP CTA  ->  /open?ref=hero  (after rewrite: /open?ref=hero&phid=<id>&utm_*=...)
  //   - /open page fires tg://resolve?domain=yum_yummybot&start=<id>
  //   - Telegram /start handler reads the start payload and stitches
  //     the bot user to the PostHog person row identified by <id>.
  //
  // We also still rewrite raw t.me/yum_yummybot links (footer link,
  // any legacy CTA) for backward compatibility — even if the user
  // somehow bypasses /open (e.g. shared link, deep link from email),
  // the bot still gets a usable ?start= payload.
  //
  // Elements tagged with `data-no-rewrite` are skipped. This is
  // critical for the fallback "Open Telegram" button on /open itself,
  // which is the LAST chance to reach the bot when tg:// has been
  // blocked — rewriting it back to /open would loop the user.
  function rewriteBotLinks(distinctId) {
    var anchors = document.querySelectorAll('a[href]');
    var startParam = pickStartParam(distinctId);
    anchors.forEach(function (a) {
      if (a.hasAttribute('data-no-rewrite')) return;
      var href = a.getAttribute('href') || '';
      var direct = DIRECT_BOT_RE.test(href);
      var bridge = OPEN_PAGE_RE.test(href);
      if (!direct && !bridge) return;
      try {
        var url = new URL(href, window.location.href);

        // distinct_id propagates to BOTH targets. /open reads it from
        // ?phid; direct t.me links carry it both as ?phid (informational)
        // and as the Telegram /start payload below.
        if (distinctId && !url.searchParams.get('phid')) {
          url.searchParams.set('phid', distinctId);
        }

        // ?start= is only meaningful for DIRECT t.me links — Telegram
        // strips unknown query params on the bot landing page but
        // honours `start`. On /open we don't set ?start because the
        // /open page itself prefers ?phid over ?start when constructing
        // the tg:// URL, and forcing ?start= here would unnecessarily
        // expose the distinct_id in the URL bar of the bridge page.
        if (direct && startParam && !url.searchParams.get('start')) {
          url.searchParams.set('start', startParam);
        }

        // Forward UTMs as standard query params so:
        //   - /open's $pageview is correctly attributed by PostHog's
        //     auto-UTM logic (without depending on sessionStorage).
        //   - any server-side reporting on the bot side that inspects
        //     the bridge URL has the campaign context.
        UTM_KEYS.forEach(function (k) {
          if (currentUtms[k] && !url.searchParams.get(k)) {
            url.searchParams.set(k, currentUtms[k]);
          }
        });

        a.setAttribute('href', url.toString());
      } catch (e) {}
    });
  }

  function inferCtaLocation(el) {
    if (!el) return 'unknown';
    var explicit = el.getAttribute('data-cta-location');
    if (explicit) return explicit;
    var section = el.closest('section, header, footer, nav');
    if (section) {
      return section.id || section.tagName.toLowerCase();
    }
    return 'unknown';
  }

  function inferCtaId(el) {
    if (!el) return 'unknown';
    var explicit = el.getAttribute('data-cta-id');
    if (explicit) return explicit;
    var href = el.getAttribute('href') || '';
    if (isBotTarget(href)) return 'open_bot';
    return (el.textContent || '').trim().slice(0, 60).toLowerCase().replace(/\s+/g, '_') || 'unknown';
  }

  // Just-in-time href refresher for bot-target anchors. Runs in the
  // click event's CAPTURE phase BEFORE the browser navigates, so any
  // mutation we make to the href is honoured by the navigation that
  // follows synchronously.
  //
  // Why we need this on top of the page-load rewrite: the page-load
  // rewrite uses `bootstrapPhid`, but PostHog (especially for returning
  // visitors) may load and report a *different* distinct_id a few
  // hundred ms later. Without this hook a user who taps a CTA inside
  // that window would carry the stale bootstrap id to /open and the
  // bot, then PostHog would emit web events under the canonical id —
  // splitting the LP→bot identity. Refreshing at click time guarantees
  // the freshest id is used regardless of timing.
  function refreshBotHrefAtClick(el, isBot, href) {
    if (!isBot || !href || el.tagName !== 'A') return;
    if (el.hasAttribute('data-no-rewrite')) return;
    var live = window.posthog && typeof posthog.get_distinct_id === 'function'
      ? posthog.get_distinct_id() : null;
    var startParam = pickStartParam(live || bootstrapPhid);
    if (!live && !startParam) return;
    try {
      var url = new URL(href, window.location.href);
      var direct = DIRECT_BOT_RE.test(href);
      if (live && url.searchParams.get('phid') !== live) {
        url.searchParams.set('phid', live);
      }
      if (direct && startParam && url.searchParams.get('start') !== startParam) {
        url.searchParams.set('start', startParam);
      }
      el.setAttribute('href', url.toString());
    } catch (e) {}
  }

  function bindCtaTracking() {
    document.addEventListener('click', function (ev) {
      var el = ev.target;
      while (el && el !== document.body) {
        if (el.tagName === 'A' || el.tagName === 'BUTTON' ||
            el.hasAttribute('data-cta') || el.hasAttribute('data-cta-id')) {
          var href = (el.getAttribute && el.getAttribute('href')) || null;
          // "Bot-bound" now includes both direct t.me links and the
          // /open deep-link bridge. The Lead event still fires once
          // per CTA click — the click happens on the LP, and the
          // /open page deliberately does NOT refire it (see
          // docs/open/index.html for the rationale).
          var isBot = isBotTarget(href);
          var isTagged = el.hasAttribute && (el.hasAttribute('data-cta') || el.hasAttribute('data-cta-id'));
          if (isBot || isTagged) {
            // Synchronously refresh phid before the browser follows
            // the link. Must run in the same tick as the click; the
            // PostHog .capture below is fire-and-forget and won't
            // delay navigation.
            refreshBotHrefAtClick(el, isBot, href);
            href = (el.getAttribute && el.getAttribute('href')) || href;
            // Last-chance push of match keys before the user leaves the
            // page. sendBeacon survives navigation; this is critical for
            // the bot-bound CTA because the next event our backend sees
            // for this user is /start, and CAPI fires within milliseconds
            // of that — so we want the freshest fbp/fbc/UTMs on file
            // BEFORE the user even reaches Telegram.
            try { pushLandingAttribution(); } catch (e) {}
            var ctaId = inferCtaId(el);
            var ctaLocation = inferCtaLocation(el);
            try {
              window.posthog && posthog.capture && posthog.capture('cta_clicked', Object.assign({
                cta_id: ctaId,
                cta_location: ctaLocation,
                cta_text: (el.textContent || '').trim().slice(0, 120),
                cta_href: href,
                target_is_bot: isBot,
                page_path: window.location.pathname,
              }, currentUtms));
            } catch (e) {}
            // Mirror the conversion to Meta + TikTok as a `Lead`
            // event so the ads algorithms can optimize toward
            // bot-link clicks. Ads platforms never see the actual
            // signup (it happens inside Telegram), so this is the
            // strongest in-browser signal we can give them until
            // the server-side Conversions / Events APIs deliver
            // CompleteRegistration / StartTrial.
            //
            // We deliberately suppress Lead for `open_bot_fallback`:
            // that CTA only fires on /open AFTER the user has
            // already triggered the canonical Lead on the LP. Firing
            // a second Lead for the same intent would double-count
            // the conversion in the ads platform and degrade
            // optimization. cta_clicked above still fires for
            // PostHog so our funnel can measure the fallback rate.
            if (ctaId !== 'open_bot_fallback') {
              if (window.fbq) {
                try {
                  fbq('track', 'Lead', {
                    content_name: ctaId,
                    content_category: ctaLocation,
                  });
                } catch (e) {}
              }
              if (window.ttq && typeof window.ttq.track === 'function') {
                try {
                  window.ttq.track('Lead', {
                    content_name: ctaId,
                    content_category: ctaLocation,
                  });
                } catch (e) {}
              }
            }
          }
          break;
        }
        el = el.parentElement;
      }
    }, { capture: true });
  }

  // -- 3. Wire it all up --------------------------------------------

  function ready(fn) {
    if (document.readyState !== 'loading') return fn();
    document.addEventListener('DOMContentLoaded', fn);
  }

  ready(function () {
    bindCtaTracking();

    // Stage 1 — synchronous rewrite with the pre-allocated phid. This
    // is the critical path: even if PostHog's array.js never loads
    // (ad-blocker, offline, slow network) the CTA buttons already
    // carry ?phid=<bootstrapPhid> and the bot can stitch the user to
    // a PostHog person row by that same id once posthog.identify runs
    // anywhere in the funnel.
    rewriteBotLinks(bootstrapPhid);

    // First attribution push — fires immediately with whatever we have
    // (phid + UTMs + any pixel cookies already set on returning
    // visitors). Subsequent pushes (below) refine the payload as Meta
    // and TikTok pixels finish setting their cookies.
    pushLandingAttribution();

    // Stage 2 — re-rewrite once posthog.get_distinct_id() agrees with
    // bootstrapPhid (sanity check) and pixel cookies have settled.
    // This is mostly a no-op for phid (we already wrote it in stage 1)
    // but lets syncPixelsToPostHog pick up _fbp/_fbc/_ttp once Meta
    // and TikTok pixels have populated their cookies.
    var attempts = 0;
    function tryFinalize() {
      var did = window.posthog && typeof posthog.get_distinct_id === 'function'
        ? posthog.get_distinct_id() : null;
      if (did) {
        if (did !== bootstrapPhid) {
          // Returning visitor who had a PostHog distinct_id from before
          // this bootstrap code shipped. PostHog wins (it's the
          // canonical id used in their existing person rows); adopt
          // it as the new yy_phid so cross-page rewrites and future
          // visits stay consistent.
          try {
            if (window.localStorage) localStorage.setItem('yy_phid', did);
          } catch (e) {}
          bootstrapPhid = did;
          rewriteBotLinks(did);
        }
        syncPixelsToPostHog();
        pushLandingAttribution();
        return;
      }
      if (attempts++ < 20) setTimeout(tryFinalize, 100);
      else {
        syncPixelsToPostHog();
        pushLandingAttribution();
      }
    }
    tryFinalize();

    // Meta + TikTok pixels set their cookies asynchronously after
    // their respective SDK scripts load, so re-sync once more after
    // they've had time to settle. Belt + suspenders.
    setTimeout(function () {
      syncPixelsToPostHog();
      pushLandingAttribution();
    }, 1500);

    // Final attribution push at 4s: catches pixel cookies that finished
    // settling after the 1.5s tick (slow tier-3 mobile networks where
    // Meta/TikTok SDK loads take >2s). After this point the CTA click
    // hook below is the only remaining touchpoint.
    setTimeout(pushLandingAttribution, 4000);
  });
})();
