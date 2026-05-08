/* ===================================================================
   YumYummy — Web Analytics (PostHog)
   ===================================================================
   What this file does
   - Loads PostHog and captures pageviews, pageleaves and autocapture
     (so every click is tracked out of the box).
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

  posthog.init('phc_u8XVgBexJVuggFASRTw7AL6mmpwoZDa6moycSxz7FrpD', {
    api_host: 'https://eu.i.posthog.com',
    person_profiles: 'identified_only',
    capture_pageview: true,
    capture_pageleave: true,
  });

  // -- 2. Helpers ----------------------------------------------------

  var BOT_HOST_RE = /^https?:\/\/(?:t|telegram)\.me\/yum_yummybot/i;
  var UTM_KEYS = [
    'utm_source', 'utm_medium', 'utm_campaign',
    'utm_term', 'utm_content', 'gclid', 'fbclid', 'ttclid'
  ];

  // Meta Pixel sets two cookies that we want to keep alongside our
  // PostHog person profile:
  //   _fbp — browser-level Facebook id, set on the very first
  //          PageView fire and persisted across pages.
  //   _fbc — click id, set when the visitor lands with ?fbclid=...
  //          and used by Meta to attribute later conversions back
  //          to the originating ad click.
  // Stashing them on the PostHog person profile means that when we
  // later wire up the Meta Conversions API server-side (to send
  // `Subscribe`/`StartTrial` from the bot backend) we can look up
  // the right fbp/fbc by posthog_distinct_id and properly
  // deduplicate browser + server events.
  function readFbCookies() {
    var out = {};
    try {
      document.cookie.split(';').forEach(function (c) {
        var idx = c.indexOf('=');
        if (idx === -1) return;
        var name = c.slice(0, idx).trim();
        if (name === '_fbp' || name === '_fbc') {
          out[name] = decodeURIComponent(c.slice(idx + 1));
        }
      });
    } catch (e) {}
    return out;
  }

  function syncFbToPostHog() {
    if (!window.posthog || typeof posthog.register !== 'function') return;
    var fb = readFbCookies();
    var props = {};
    if (fb._fbp) props.$fbp = fb._fbp;
    if (fb._fbc) props.$fbc = fb._fbc;
    if (!Object.keys(props).length) return;
    try {
      posthog.register(props);
      if (typeof posthog.setPersonProperties === 'function') {
        posthog.setPersonProperties(props);
      }
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

  function rewriteBotLinks(distinctId) {
    var anchors = document.querySelectorAll('a[href]');
    var startParam = pickStartParam(distinctId);
    anchors.forEach(function (a) {
      var href = a.getAttribute('href') || '';
      if (!BOT_HOST_RE.test(href)) return;
      try {
        var url = new URL(href, window.location.href);
        // Don't clobber an explicit start that the page author set.
        if (!url.searchParams.get('start') && startParam) {
          url.searchParams.set('start', startParam);
        }
        // Always carry distinct_id as a separate param so the bot
        // can pick it up even if `start` already contained a UTM
        // source slug.
        if (distinctId && !url.searchParams.get('phid')) {
          url.searchParams.set('phid', distinctId);
        }
        // Also forward UTMs as standard query params for any
        // reporting that reads them server-side later.
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
    if (BOT_HOST_RE.test(href)) return 'open_bot';
    return (el.textContent || '').trim().slice(0, 60).toLowerCase().replace(/\s+/g, '_') || 'unknown';
  }

  function bindCtaTracking() {
    document.addEventListener('click', function (ev) {
      var el = ev.target;
      while (el && el !== document.body) {
        if (el.tagName === 'A' || el.tagName === 'BUTTON' ||
            el.hasAttribute('data-cta') || el.hasAttribute('data-cta-id')) {
          var href = (el.getAttribute && el.getAttribute('href')) || null;
          var isBot = href ? BOT_HOST_RE.test(href) : false;
          var isTagged = el.hasAttribute && (el.hasAttribute('data-cta') || el.hasAttribute('data-cta-id'));
          if (isBot || isTagged) {
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
            // Mirror the conversion to Meta as a `Lead` event so the
            // ads algorithm can optimize toward bot-link clicks. Meta
            // never sees the actual signup (it happens in Telegram),
            // so this is the strongest in-browser signal we can give
            // it until we add server-side Conversions API.
            if (window.fbq) {
              try {
                fbq('track', 'Lead', {
                  content_name: ctaId,
                  content_category: ctaLocation,
                });
              } catch (e) {}
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

    // PostHog assigns distinct_id synchronously after init, but the
    // SDK script itself is loaded async via `array.js`. We retry up
    // to ~2s so the very first page render still gets the right
    // start= param. If posthog never loads (ad-blocker, offline) we
    // fall back to UTM-only attribution and skip the phid param.
    var attempts = 0;
    function tryRewrite() {
      var did = window.posthog && typeof posthog.get_distinct_id === 'function'
        ? posthog.get_distinct_id() : null;
      if (did) {
        rewriteBotLinks(did);
        syncFbToPostHog();
        return;
      }
      if (attempts++ < 20) {
        setTimeout(tryRewrite, 100);
      } else {
        rewriteBotLinks(null);
        syncFbToPostHog();
      }
    }
    tryRewrite();

    // Meta Pixel sets _fbp/_fbc asynchronously after fbevents.js
    // loads, so re-sync once more after the script has had time to
    // settle. Belt + suspenders.
    setTimeout(syncFbToPostHog, 1500);
  });
})();
