/* ===================================================================
   YumYummy — /open v2: environment-aware deep-link bridge
   ===================================================================
   v1 tried to fire tg://resolve via window.location.replace and hoped
   the OS would intercept it. It worked in regular browsers but failed
   silently in TikTok / Instagram / Facebook webviews, because Apple
   requires a *user-initiated tap* for Universal Link interception and
   programmatic redirects don't count (Linkrunner article, Mar 2026).
   The user landed on a t.me page inside the same webview, tapped
   "Start Bot", and that button used a Universal Link too — also
   blocked. Dead end.

   v2 splits behaviour by environment:

     - Normal browser:
         Same auto-tg:// path as v1. tg:// is intercepted by the OS
         and Telegram opens. Fallback button shows after 1.5 s if
         Telegram isn't installed.

     - Known in-app webview (TikTok/Instagram/Facebook/Twitter/etc.):
         Skip the auto-redirect entirely (it doesn't work, and
         spinning a "Opening Telegram…" message is misleading).
         Show the webview escape UI immediately with:
           1. A real <a href> "Open Telegram" tap that some webviews
              still honour as a user-initiated click.
           2. A "Copy bot link" button (universal escape, copies the
              t.me URL with attribution preserved).
           3. Step-by-step instructions to use the platform's
              "Open in browser" menu.
           4. On Android, an extra intent:// anchor that forces
              Chrome's Android intent handler to launch Telegram
              by package name.

   Analytics additions over v1:
     - bot_open_webview_detected   — fires once on load when we know
                                     we're inside an in-app webview.
     - bot_open_copy_link_clicked  — user used the universal escape.
     - bot_open_intent_clicked     — Android intent:// link tap.
     - cta_clicked (existing event, fires via analytics.js) — captures
       open_bot_fallback / open_bot_webview_try / open_bot_android_intent /
       copy_bot_link so the PostHog funnel can compare conversion of
       each remedy.
   =================================================================== */

(function () {
  'use strict';

  // -- Helpers ------------------------------------------------------

  function $(id) { return document.getElementById(id); }

  function getParam(name) {
    try {
      return new URLSearchParams(window.location.search).get(name);
    } catch (e) {
      return null;
    }
  }

  function isValidStartParam(s) {
    return typeof s === 'string' && /^[A-Za-z0-9_-]{1,64}$/.test(s);
  }

  function safePostHog(fn) {
    try {
      if (window.posthog && typeof window.posthog.capture === 'function') {
        fn(window.posthog);
      }
    } catch (e) {}
  }

  // -- 1. Detect environment FIRST (before any redirect attempt) ---

  // We treat the following as "in-app webviews" where the auto-tg://
  // redirect is known to fail:
  //   - TikTok: ad UA "trill_*" (Android) / BytedanceWebview (iOS) /
  //             generic "TikTok" UA segment
  //   - Instagram: "Instagram"
  //   - Facebook: FBAN, FBAV, FB_IAB, FBIOS markers
  //   - Twitter/X: "Twitter" segment
  //   - Snapchat: "Snapchat"
  //   - LINE: "Line/" segment
  // Anything else (Safari/Chrome/Firefox/Edge/Telegram Desktop) is
  // treated as a "regular browser" and gets the auto-redirect path.
  function detectWebview() {
    var ua = (navigator.userAgent || '').toLowerCase();
    if (/trill_|bytedancewebview|bytedance|musical_ly|tiktok/.test(ua))
      return { id: 'tiktok', label: 'TikTok' };
    if (/instagram/.test(ua))
      return { id: 'instagram', label: 'Instagram' };
    if (/fbav|fban|fb_iab|fbios|fbss|facebook/.test(ua))
      return { id: 'facebook', label: 'Facebook' };
    if (/\btwitter\b/.test(ua))
      return { id: 'twitter', label: 'X (Twitter)' };
    if (/snapchat/.test(ua))
      return { id: 'snapchat', label: 'Snapchat' };
    if (/line\//.test(ua))
      return { id: 'line', label: 'LINE' };
    if (/pinterest/.test(ua))
      return { id: 'pinterest', label: 'Pinterest' };
    return null;
  }

  function detectPlatform() {
    var ua = (navigator.userAgent || '').toLowerCase();
    if (/android/.test(ua)) return 'android';
    if (/iphone|ipad|ipod/.test(ua)) return 'ios';
    return 'desktop';
  }

  var webview = detectWebview();
  var platform = detectPlatform();

  // -- 2. Read attribution params ----------------------------------

  var phid    = getParam('phid');
  var startQ  = getParam('start');
  var refQ    = getParam('ref');
  var utmSrc  = getParam('utm_source');

  var startPayload = null;
  var startKind = 'none';
  if (isValidStartParam(phid))       { startPayload = phid;   startKind = 'phid'; }
  else if (isValidStartParam(startQ)){ startPayload = startQ; startKind = 'start'; }
  else if (isValidStartParam(refQ))  { startPayload = refQ;   startKind = 'ref'; }
  else if (isValidStartParam(utmSrc)){ startPayload = utmSrc; startKind = 'utm_source'; }

  // -- 3. Build the various URL forms we might need -----------------

  var BOT_DOMAIN = 'yum_yummybot';

  function buildTgUrl() {
    var u = 'tg://resolve?domain=' + BOT_DOMAIN;
    if (startPayload) u += '&start=' + encodeURIComponent(startPayload);
    return u;
  }

  function buildTmeUrl() {
    var u = 'https://t.me/' + BOT_DOMAIN;
    if (startPayload) u += '?start=' + encodeURIComponent(startPayload);
    return u;
  }

  // Android's intent:// scheme. Chrome and most Android system
  // WebView builds will:
  //   1. Try to launch the activity for `tg://resolve?...` in the
  //      org.telegram.messenger package.
  //   2. If Telegram isn't installed (or the webview blocks it),
  //      navigate to browser_fallback_url instead.
  // We URL-encode the fallback so & inside it doesn't break the
  // intent string. TikTok's Android WebView honours this in many
  // builds where plain tg:// is silently dropped — it's a cheap
  // win to offer as an Android-only escape hatch.
  function buildIntentUrl() {
    var tgPath = 'resolve?domain=' + BOT_DOMAIN;
    if (startPayload) tgPath += '&start=' + encodeURIComponent(startPayload);
    var fallback = encodeURIComponent(buildTmeUrl());
    return 'intent://' + tgPath
      + '#Intent;scheme=tg;package=org.telegram.messenger'
      + ';S.browser_fallback_url=' + fallback
      + ';end';
  }

  // -- 4. Shared analytics emit -------------------------------------

  function emit(event, props) {
    safePostHog(function (ph) {
      ph.capture(event, Object.assign({
        ref: refQ || null,
        phid_present: !!phid,
        start_payload_kind: startKind,
        in_app_browser: webview ? webview.id : 'browser',
        platform: platform,
      }, props || {}));
    });
  }

  // -- 5. Two distinct flows ----------------------------------------

  var openingEl   = $('state-opening');
  var fallbackEl  = $('state-fallback');
  var webviewEl   = $('state-webview');

  // 5a. WEBVIEW FLOW ------------------------------------------------
  if (webview) {
    renderWebviewFlow();
  } else {
    renderRegularBrowserFlow();
  }

  // ---- helpers used by both flows ----

  function setFallbackHref() {
    var btns = ['open-tg-btn', 'webview-try-anyway'];
    btns.forEach(function (id) {
      var el = $(id);
      if (el) el.setAttribute('href', buildTmeUrl());
    });
    var intentBtn = $('webview-android-intent');
    if (intentBtn) intentBtn.setAttribute('href', buildIntentUrl());
  }

  function showToast(msg) {
    var t = $('toast');
    if (!t) return;
    t.textContent = msg;
    t.hidden = false;
    t.classList.add('show');
    setTimeout(function () {
      t.classList.remove('show');
      setTimeout(function () { t.hidden = true; }, 250);
    }, 2200);
  }

  // ---- 5b. REGULAR BROWSER FLOW ----
  function renderRegularBrowserFlow() {
    setFallbackHref();

    // tg:// works in regular browsers — fire it shortly after load
    // so the inline pixel snippets in <head> have time to enqueue
    // their initial events (PostHog $pageview, fbq PageView, ttq.page).
    setTimeout(function () {
      emit('bot_open_attempted', {
        tg_url: buildTgUrl(),
        fallback_url: buildTmeUrl(),
      });
      try {
        window.location.replace(buildTgUrl());
      } catch (e) {
        try { window.location.href = buildTgUrl(); } catch (e2) {}
      }
    }, 250);

    // If we're still here after 1.5 s, Telegram didn't take over.
    // Most likely the app isn't installed. Swap to the fallback
    // state which is just the "Open Telegram" button (it opens
    // t.me, which then offers a "Download Telegram" path).
    setTimeout(function () {
      if (document.hidden) return; // user handed off to Telegram
      if (!fallbackEl) return;
      if (openingEl) openingEl.classList.add('hidden');
      fallbackEl.classList.remove('hidden');
      emit('bot_open_fallback_shown', {});
    }, 1500);

    // Visibility-change as a proxy for "Telegram took over"
    document.addEventListener('visibilitychange', function onVis() {
      if (!document.hidden) return;
      emit('bot_open_handoff', {});
      document.removeEventListener('visibilitychange', onVis);
    });
  }

  // ---- 5c. IN-APP WEBVIEW FLOW ----
  function renderWebviewFlow() {
    setFallbackHref();

    if (openingEl) openingEl.classList.add('hidden');
    if (webviewEl) webviewEl.classList.remove('hidden');

    // Personalize the screen with the detected app name so the
    // user sees "You're inside TikTok" rather than the generic
    // "in-app browser" placeholder.
    var nameEl = $('webview-name');
    if (nameEl && webview.label) nameEl.textContent = webview.label + "'s in-app browser";

    // Surface the Android-only intent:// button only on Android.
    var intentBtn = $('webview-android-intent');
    if (intentBtn && platform === 'android') {
      intentBtn.classList.remove('hidden');
    }

    emit('bot_open_webview_detected', {
      tme_url: buildTmeUrl(),
      intent_url: buildIntentUrl(),
    });

    // Wire up the copy-link button. We copy the t.me URL with full
    // attribution preserved so even if the user pastes it into
    // Telegram chat or browser address bar, the bot still receives
    // the right ?start= payload.
    var copyBtn = $('copy-link-btn');
    var labelEl = $('copy-link-label');
    if (copyBtn) {
      copyBtn.addEventListener('click', function () {
        var url = buildTmeUrl();
        var done = function (ok) {
          if (labelEl) {
            labelEl.textContent = ok ? 'Copied!' : 'Copy failed — long-press the link instead';
            setTimeout(function () {
              labelEl.textContent = 'Copy bot link';
            }, 2200);
          }
          if (ok) showToast('Link copied. Paste it in Telegram or your browser.');
          emit('bot_open_copy_link_clicked', { ok: ok, copied_url: url });
        };
        // Prefer the modern Clipboard API, fall back to a hidden
        // textarea + execCommand for older webviews that don't
        // expose navigator.clipboard inside an in-app browser.
        if (navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText(url).then(
            function () { done(true); },
            function () { done(legacyCopy(url)); }
          );
        } else {
          done(legacyCopy(url));
        }
      });
    }

    // Track the Android intent button click so we can measure
    // conversion uplift from offering it.
    if (intentBtn) {
      intentBtn.addEventListener('click', function () {
        emit('bot_open_intent_clicked', { intent_url: intentBtn.href });
      });
    }
  }

  // Hidden-textarea copy fallback for legacy webviews.
  function legacyCopy(text) {
    try {
      var ta = document.createElement('textarea');
      ta.value = text;
      ta.setAttribute('readonly', '');
      ta.style.position = 'absolute';
      ta.style.left = '-9999px';
      document.body.appendChild(ta);
      ta.select();
      var ok = document.execCommand('copy');
      document.body.removeChild(ta);
      return ok;
    } catch (e) {
      return false;
    }
  }
})();
