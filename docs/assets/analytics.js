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

  // We disable `capture_pageview` here and fire it ourselves AFTER
  // registering UTMs as super-properties. Otherwise PostHog's auto
  // $pageview races the snippet's async `array.js` load and the very
  // first pageview event lands without `utm_*` super-properties
  // attached — which is exactly the bug we're trying to fix.
  posthog.init('phc_u8XVgBexJVuggFASRTw7AL6mmpwoZDa6moycSxz7FrpD', {
    api_host: 'https://eu.i.posthog.com',
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
        captureLandedFromAd();
        ph.capture('$pageview');
      } catch (e) {}
    },
  });

  // -- 2. Helpers ----------------------------------------------------

  var BOT_HOST_RE = /^https?:\/\/(?:t|telegram)\.me\/yum_yummybot/i;
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
            // Same idea for TikTok: fire a standard `Lead` event on
            // every CTA click so TikTok ads can optimize for it. The
            // actual trial/subscription happens in the Telegram bot
            // and will be sent server-side later via the TikTok
            // Events API using $ttp/$ttclid stored on the PostHog
            // person profile.
            if (window.ttq && typeof window.ttq.track === 'function') {
              try {
                window.ttq.track('Lead', {
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
        syncPixelsToPostHog();
        return;
      }
      if (attempts++ < 20) {
        setTimeout(tryRewrite, 100);
      } else {
        rewriteBotLinks(null);
        syncPixelsToPostHog();
      }
    }
    tryRewrite();

    // Meta + TikTok pixels set their cookies asynchronously after
    // their respective SDK scripts load, so re-sync once more after
    // they've had time to settle. Belt + suspenders.
    setTimeout(syncPixelsToPostHog, 1500);
  });
})();
