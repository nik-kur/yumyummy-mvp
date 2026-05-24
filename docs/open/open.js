/* ===================================================================
   YumYummy — /open deep-link bridge logic
   ===================================================================
   Purpose: bypass TikTok / Meta / Twitter in-app webviews that
   intercept t.me universal links and trap the user inside their own
   browser. We fire the native tg:// URI scheme (which these webviews
   do NOT intercept) and fall back to a t.me link if Telegram never
   takes over.

   Why a separate file (not inline analytics.js):
     - analytics.js handles PostHog/UTM/pixel plumbing and is shared
       with the LP. We don't want it to grow conditional /open logic.
     - The deep-link redirect timing is sensitive (we want tg:// to
       fire as early as possible). Keeping it in its own short script
       makes the critical path obvious.

   Coexistence with analytics.js:
     - analytics.js runs `defer` so DOM is ready when it executes. It
       registers UTM super-properties from window.location.search and
       calls posthog.capture('$pageview') in PostHog's `loaded`
       callback. By the time analytics.js's PostHog instance is ready,
       open.js has already queued its custom events on posthog (the
       PostHog stub queues calls until the SDK loads), so order
       doesn't matter for event delivery.
     - This script never re-registers pixels — analytics.js already
       picked them up via the inline TikTok/Meta snippets in
       open/index.html.
     - The fallback "Open Telegram" button has data-no-rewrite so
       analytics.js's rewriteBotLinks() does NOT loop it back through
       /open. This is critical — without it the page would spin.
   =================================================================== */

(function () {
  'use strict';

  // -- Helpers ------------------------------------------------------

  function getParam(name) {
    try {
      return new URLSearchParams(window.location.search).get(name);
    } catch (e) {
      return null;
    }
  }

  // Same validation as analytics.js: Telegram /start params accept
  // [A-Za-z0-9_-]{1,64}. Reject anything else so we don't ship a
  // broken deep-link that Telegram silently drops.
  function isValidStartParam(s) {
    return typeof s === 'string' && /^[A-Za-z0-9_-]{1,64}$/.test(s);
  }

  // Duplicated from analytics.js so that open.js — which runs BEFORE
  // analytics.js's deferred script — can seed the same yy_phid value.
  // The first direct-to-bot visitor lands here with no ?phid= on the
  // URL and no localStorage either; if we don't generate one
  // synchronously we'd ship the tg:// link with utm_source / ref as
  // the start payload, the bot would treat it as acquisition_source
  // (not posthog_distinct_id), and the CAPI client wouldn't be able
  // to look up the landing_attribution row that analytics.js writes
  // a few hundred ms later. Generating here keeps the bot's
  // posthog_distinct_id and our DB row keyed by the same id.
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

  function getOrCreateStoredPhid() {
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

  function safePostHog(fn) {
    // PostHog's official snippet replaces window.posthog with a stub
    // that queues calls until array.js loads. Calling capture/register
    // before load is safe and the call will execute when ready.
    try {
      if (window.posthog && typeof window.posthog.capture === 'function') {
        fn(window.posthog);
      }
    } catch (e) {}
  }

  // Read a single cookie by name. Used to grab Meta/TikTok pixel ids
  // (_fbp, _fbc, _ttp) which are how the server-side CAPI/EAPI clients
  // match a Telegram /start back to the original ad click.
  function readCookie(name) {
    try {
      var raw = document.cookie || '';
      var prefix = name + '=';
      var parts = raw.split(';');
      for (var i = 0; i < parts.length; i++) {
        var c = parts[i].trim();
        if (c.indexOf(prefix) === 0) return c.substring(prefix.length);
      }
    } catch (e) {}
    return null;
  }

  // Synchronous landing_attribution push.
  //
  // analytics.js also pushes the same payload a few ms later (it's a
  // deferred script, runs after the parser finishes <body>). The catch
  // is that /open redirects to `tg://` 250 ms after this script
  // executes, so on slow mobile networks the deferred script's push
  // may race the page transition. Firing here, *synchronously at the
  // top of the critical path*, buys us the full 250 ms of grace before
  // the OS suspends the webview.
  //
  // Content-Type stays 'text/plain' on purpose — it's one of the three
  // CORS simple types, so the browser skips the OPTIONS preflight that
  // Meta/Instagram in-app browsers would otherwise drop during the
  // tg:// handoff. The server reads the raw body and parses JSON,
  // ignoring the header.
  var ATTRIBUTION_API_URL = 'https://yumyummy-mvp-eu.onrender.com/api/v1/landing-attribution';

  function pushLandingAttributionEarly(phidValue) {
    if (!phidValue) return;
    var params = null;
    try { params = new URLSearchParams(window.location.search); } catch (e) {}
    function q(key) { return params ? (params.get(key) || null) : null; }
    var payload = {
      phid: phidValue,
      fbp: readCookie('_fbp'),
      fbc: readCookie('_fbc'),
      fbclid: q('fbclid'),
      ttp: readCookie('_ttp'),
      ttclid: q('ttclid'),
      landing_url: (function () {
        try { return window.location.href || null; } catch (e) { return null; }
      })(),
      utm_source: q('utm_source'),
      utm_medium: q('utm_medium'),
      utm_campaign: q('utm_campaign'),
      utm_term: q('utm_term'),
      utm_content: q('utm_content'),
    };
    var body;
    try { body = JSON.stringify(payload); } catch (e) { return; }
    try {
      if (navigator && typeof navigator.sendBeacon === 'function') {
        var blob = new Blob([body], { type: 'text/plain' });
        if (navigator.sendBeacon(ATTRIBUTION_API_URL, blob)) return;
      }
      if (typeof fetch === 'function') {
        fetch(ATTRIBUTION_API_URL, {
          method: 'POST',
          body: body,
          headers: { 'Content-Type': 'text/plain' },
          keepalive: true,
          mode: 'cors',
          credentials: 'omit',
        }).catch(function () {});
      }
    } catch (e) {}
  }

  // -- 1. Read incoming attribution params --------------------------

  // Priority for the bot /start payload (must be Telegram-safe):
  //   1. ?phid=<posthog_distinct_id> — preferred, set by analytics.js
  //      when the user clicked a CTA on the LP (LP-first traffic).
  //   2. localStorage('yy_phid') — direct-to-bot ads that target /open
  //      directly arrive without ?phid= on the URL. We seed the same
  //      yy_phid analytics.js will later use, so the bot's
  //      posthog_distinct_id matches the key we write to
  //      landing_attribution. Without this, CAPI lookups by phid
  //      would miss the row for every direct-to-bot ad click.
  //   3. ?start=<value> — explicit Telegram start payload override
  //      (kept for backwards compat with hand-crafted deep-links).
  //   4. ?ref=<location> — landed-CTA-source slug like "hero" or
  //      "footer". Helpful for ad campaigns that link directly to
  //      /open?ref=tiktok_video1 without using utm_source.
  //   5. utm_source — last-resort campaign-level slug.
  //   6. null — open the bot without a /start payload. Telegram will
  //      show the bot intro and the user can tap Start manually.
  var phid    = getParam('phid');
  var startQ  = getParam('start');
  var refQ    = getParam('ref');
  var utmSrc  = getParam('utm_source');
  var storedPhid = getOrCreateStoredPhid();

  var startPayload = null;
  if (isValidStartParam(phid))         startPayload = phid;
  else if (isValidStartParam(storedPhid)) startPayload = storedPhid;
  else if (isValidStartParam(startQ))  startPayload = startQ;
  else if (isValidStartParam(refQ))    startPayload = refQ;
  else if (isValidStartParam(utmSrc))  startPayload = utmSrc;

  // Fire the attribution beacon NOW — synchronously, before the 250 ms
  // tg:// timer below. Direct-to-bot Meta ads land on /open and the
  // OS suspends the webview during the handoff to Telegram; the
  // deferred analytics.js push would race that suspension and lose
  // ~98% of writes on Meta in-app browsers (May 23–24 production).
  // We key by whichever phid we actually pass to the bot, so the CAPI
  // client's later `fetch_landing_attribution(users.posthog_distinct_id)`
  // matches this exact row.
  pushLandingAttributionEarly(phid || storedPhid);

  // -- 2. Build the deep-link + fallback URLs -----------------------

  var BOT_DOMAIN = 'yum_yummybot';

  // tg://resolve is the native Telegram URI scheme. Crucially this
  // is NOT a universal link, so in-app webviews can't intercept it
  // the way they intercept https://t.me/...
  function buildTgUrl() {
    var u = 'tg://resolve?domain=' + BOT_DOMAIN;
    if (startPayload) u += '&start=' + encodeURIComponent(startPayload);
    return u;
  }

  // t.me/<bot>?start=<payload> is the HTTPS fallback. Telegram's
  // landing page detects the OS, offers a native-app handoff, and
  // the ?start= param survives the handoff to /start the bot with
  // the correct payload.
  function buildTmeUrl() {
    var u = 'https://t.me/' + BOT_DOMAIN;
    if (startPayload) u += '?start=' + encodeURIComponent(startPayload);
    return u;
  }

  // -- 3. UA / environment detection (for analytics only — we don't
  //       branch the redirect on it, the redirect strategy is the
  //       same everywhere because tg:// works in all the webviews
  //       we care about) ----------------------------------------------

  function detectEnv() {
    var ua = (navigator.userAgent || '').toLowerCase();
    var inApp = 'browser';
    // TikTok in-app browser identifies as "trill" (Android) or
    // BytedanceWebview (iOS).
    if (/trill_|bytedance|bytedancewebview|tiktok/.test(ua))      inApp = 'tiktok';
    else if (/instagram/.test(ua))                                 inApp = 'instagram';
    else if (/\bfb_iab|fb_iab|fban|fbav|facebook/.test(ua))        inApp = 'facebook';
    else if (/twitter|twitterandroid/.test(ua))                    inApp = 'twitter';
    else if (/snapchat/.test(ua))                                  inApp = 'snapchat';
    else if (/line\//.test(ua))                                    inApp = 'line';

    var platform = 'desktop';
    if (/android/.test(ua))           platform = 'android';
    else if (/iphone|ipad|ipod/.test(ua)) platform = 'ios';

    return { in_app_browser: inApp, platform: platform };
  }

  var env = detectEnv();

  // -- 4. Fire the deep-link --------------------------------------

  // Update the fallback link's href to include the start payload BEFORE
  // we navigate. This way even if the user is fast-thumbed and taps
  // the button while the page is still rendering, the start param is
  // already attached. We also gate the analytics.js rewriteBotLinks
  // on data-no-rewrite, so we set the canonical href here ourselves.
  var fallbackBtn = document.getElementById('open-tg-btn');
  if (fallbackBtn) {
    fallbackBtn.setAttribute('href', buildTmeUrl());
  }

  var tgUrl = buildTgUrl();
  var redirectFiredAt = 0;

  function fireTgRedirect() {
    redirectFiredAt = Date.now();
    safePostHog(function (ph) {
      ph.capture('bot_open_attempted', {
        ref: refQ || null,
        phid_present: !!phid,
        start_payload_kind: startPayload ? (
          startPayload === phid      ? 'phid' :
          startPayload === storedPhid ? 'stored_phid' :
          startPayload === startQ    ? 'start' :
          startPayload === refQ      ? 'ref' :
          startPayload === utmSrc    ? 'utm_source' : 'other'
        ) : 'none',
        in_app_browser: env.in_app_browser,
        platform: env.platform,
        tg_url: tgUrl,
        fallback_url: fallbackBtn ? fallbackBtn.getAttribute('href') : null,
      });
    });
    // window.location.replace (instead of .href) so the user can hit
    // Back from Telegram and NOT land on /open again (which would
    // re-fire the redirect in a loop on some browsers).
    try {
      window.location.replace(tgUrl);
    } catch (e) {
      try { window.location.href = tgUrl; } catch (e2) {}
    }
  }

  // -- 5. Fallback UI -----------------------------------------------

  // Session-replay evidence (May 20): on Android Chrome the OS handoff
  // to Telegram routinely takes 3–7 seconds end-to-end. With the old
  // 1500 ms timer the fallback button appeared mid-handoff, users tapped
  // it, the OS got two competing intents, and Telegram never opened.
  // 2000 ms is the longest we can wait before users start to *feel*
  // the page is broken (UX research baseline for "this isn't loading"
  // sits around 2–3 s) while still giving the OS enough head-room to
  // process tg:// on slow mobile networks.
  var FALLBACK_AFTER_MS = 2000;
  var openingEl = document.getElementById('state-opening');
  var fallbackEl = document.getElementById('state-fallback');

  function showFallback() {
    // Skip if Telegram already opened — when the OS hands off to
    // Telegram, the page becomes hidden. If we're hidden, we did
    // our job; don't pollute analytics with a fallback_shown event.
    if (document.hidden) return;
    if (!fallbackEl || !fallbackEl.classList.contains('hidden')) return;

    if (openingEl) openingEl.classList.add('hidden');
    fallbackEl.classList.remove('hidden');

    safePostHog(function (ph) {
      ph.capture('bot_open_fallback_shown', {
        ref: refQ || null,
        in_app_browser: env.in_app_browser,
        platform: env.platform,
        ms_since_attempt: redirectFiredAt ? (Date.now() - redirectFiredAt) : null,
      });
    });
  }

  // Mark a successful handoff: if the document goes hidden within a
  // few seconds of firing tg://, the user is most likely now inside
  // Telegram. Useful for measuring the real tg:// success rate per
  // in_app_browser segment without needing server-side correlation.
  function onVisibilityChange() {
    if (!document.hidden) return;
    if (!redirectFiredAt) return;
    var dt = Date.now() - redirectFiredAt;
    if (dt > 10000) return; // ignore unrelated tab switches later on
    safePostHog(function (ph) {
      ph.capture('bot_open_handoff', {
        ref: refQ || null,
        in_app_browser: env.in_app_browser,
        platform: env.platform,
        ms_since_attempt: dt,
      });
    });
    document.removeEventListener('visibilitychange', onVisibilityChange);
  }

  document.addEventListener('visibilitychange', onVisibilityChange);

  // -- 6. Wire it up ------------------------------------------------

  // Timing trade-off for the redirect:
  //   - Too soon: PostHog's array.js may not have replaced the stub
  //     yet, so `bot_open_attempted` (and the $pageview that
  //     analytics.js fires in its `loaded` callback) are queued on
  //     the stub. They'll be flushed via sendBeacon at pagehide,
  //     which works on every modern browser but is "best effort".
  //   - Too late: the user stares at "Opening Telegram…" longer than
  //     necessary, which (a) feels broken and (b) lets meta-refresh
  //     creep up on us.
  // 250 ms is the sweet spot we've validated: enough for the inline
  // pixel snippets in <head> to enqueue their initial events, short
  // enough that the redirect feels instant.
  setTimeout(fireTgRedirect, 250);

  // After 1.5 s, if we're still here, the in-app browser swallowed
  // the tg:// scheme. Show the user the explicit "Open Telegram"
  // button so they have an out.
  setTimeout(showFallback, FALLBACK_AFTER_MS);
})();
