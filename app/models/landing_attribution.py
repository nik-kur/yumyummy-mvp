"""Server-side capture of LP attribution signals keyed by PostHog phid.

Why this exists
---------------
Meta CAPI / TikTok EAPI rate every server event by Event Match Quality
(EMQ). The strongest match keys are ``fbp`` / ``fbc`` (set by the browser
pixel) plus client IP and User-Agent. We can't rely on PostHog's
person-profile API for those because:

  - ``$ip`` is stored on the event row, not the person row, so the
    Persons API regularly returns ``None`` even when the LP visit was
    captured.
  - PostHog ingestion lags 10-30s; for a user who clicks the bot CTA
    immediately, the CAPI call fires before the person profile has
    been written.
  - ``raw_user_agent`` we have to set ourselves (PostHog parses UA but
    drops the raw string).

So we also write a server-side row right when the visitor lands on
yumyummy.ai. Same identity (phid) ties this row to the bot user once
they hit ``/start``. The Meta CAPI client reads this table FIRST and
only falls back to PostHog if no row exists yet.

Single row per phid (UPSERT). Latest non-null values win — a returning
visitor's IP/UA is more relevant than their first-touch values, but the
very first fbp/fbc are stickier (Meta sets them on first PageView and
doesn't rotate them).
"""

from sqlalchemy import Column, DateTime, Integer, String, func

from app.db.base import Base


class LandingAttribution(Base):
    __tablename__ = "landing_attribution"

    phid = Column(String, primary_key=True)

    # Meta match keys: fbp (browser id) is set on first pixel PageView and
    # persists for ~90 days. fbc (click id) only appears when the visitor
    # arrives with ?fbclid=, so it's mostly populated for paid traffic.
    fbp = Column(String, nullable=True)
    fbc = Column(String, nullable=True)
    fbclid = Column(String, nullable=True)

    # TikTok match keys. ttp is the browser id (cookie), ttclid is the
    # click id from ?ttclid=. Both lift TikTok Events API match quality
    # the same way fbp/fbc lift Meta CAPI.
    ttp = Column(String, nullable=True)
    ttclid = Column(String, nullable=True)

    # Captured from the HTTP request headers on our side rather than
    # echoed from the browser. The browser can't reliably tell us its
    # outbound IP (NATs, proxies) and lying about it would tank EMQ;
    # the request itself is the source of truth.
    ip = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)

    # Full landing URL with UTM/fbclid query string. Used as Meta's
    # event_source_url so the conversion attributes to the same URL the
    # ad was pointed at.
    landing_url = Column(String, nullable=True)

    # Campaign attribution, mirrored from the URL so we can do quick
    # diagnostics ("which campaign is generating the most weak-match
    # phids?") without joining back to PostHog.
    utm_source = Column(String, nullable=True)
    utm_medium = Column(String, nullable=True)
    utm_campaign = Column(String, nullable=True)
    utm_term = Column(String, nullable=True)
    utm_content = Column(String, nullable=True)

    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
