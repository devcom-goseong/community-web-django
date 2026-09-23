"""Turning away marketing pitches sent through the join form.

The form exists so people can join the community or ask about it. What it
mostly attracts otherwise is cold outreach: offers to improve the site's Google
ranking, build backlinks, redesign the site, run ads. Those are refused outright
and never stored, so nobody on the leadership team has to read them.

How the matching works
----------------------
The text is normalised first — accents folded, punctuation turned into spaces,
runs of spaces collapsed — so "S.E.O." and "S E O" read the same as "seo". Every
term is then matched on whole words, so "seo" does not fire inside "museology"
and "ads" does not fire inside "roads".

Terms are matched against what somebody typed: the name and the message. Not
the email address, because a person with a marketing agency's address may still
be a genuine student, and not the interests, which are fixed tick boxes.

Tuning it
---------
BLOCKED holds the built-in list. Two environment variables adjust it without
touching this file:

    EXTRA_BLOCKED_TERMS   more terms to refuse, comma separated
    UNBLOCKED_TERMS       terms from the list below to allow again

UNBLOCKED_TERMS matters more than it looks. "seo" on its own is in the list
because that is what the community asked for, and it will also refuse a student
who writes "I want to learn SEO". If that happens, put seo in UNBLOCKED_TERMS —
the longer phrases like "seo services" will still catch the real pitches.
"""

import logging
import re
import unicodedata

from django.conf import settings

log = logging.getLogger(__name__)

# Terms that are only ever marketing. One per line, lower case. Multi-word
# terms match with any spacing between the words.
BLOCKED = (
    # Search ranking
    "seo",
    "search engine optimization",
    "search engine optimisation",
    "search engine ranking",
    "search engine marketing",
    "google search",
    "google ranking",
    "google ranking factors",
    "rank on google",
    "rank higher",
    "ranking higher",
    "higher ranking",
    "first page of google",
    "top of google",
    "google first page",
    "page one of google",
    "search rankings",
    "organic traffic",
    "organic ranking",
    "keyword research",
    "keyword ranking",
    "target keywords",
    "domain authority",
    "page authority",
    "alexa rank",
    "backlink",
    "backlinks",
    "link building",
    "guest post",
    "guest posting",
    "do follow links",
    "dofollow",
    "off page",
    "on page optimization",
    "on page optimisation",
    "google my business",
    "google business profile",
    "search console audit",
    # Adverts and agencies
    "google ads",
    "google adwords",
    "adwords",
    "ppc campaign",
    "ppc services",
    "paid ads",
    "ad campaign",
    "digital marketing",
    "internet marketing",
    "online marketing",
    "social media marketing",
    "influencer marketing",
    "email marketing",
    "bulk email",
    "cold email",
    "marketing agency",
    "marketing services",
    "marketing proposal",
    "our agency",
    "seo agency",
    "seo company",
    "seo expert",
    "seo specialist",
    "seo consultant",
    "seo services",
    "seo package",
    "seo audit",
    "seo report",
    "seo plan",
    "seo strategy",
    # Sales pitches about the site itself
    "i came across your website",
    "i visited your website",
    "we noticed your website",
    "i noticed your website",
    "while browsing your website",
    "your website is not ranking",
    "your website needs",
    "redesign your website",
    "revamp your website",
    "website audit",
    "free audit",
    "free quote",
    "no obligation quote",
    "affordable price",
    "affordable packages",
    "cost effective packages",
    "web design services",
    "web development services",
    "website development services",
    "app development services",
    "mobile app development company",
    "software development company",
    "outsourcing services",
    "white label",
    "hire our team",
    "our developers",
    "our portfolio",
    "our clients include",
    # Generic money and lead spam
    "increase traffic",
    "boost traffic",
    "drive traffic",
    "more visitors",
    "increase sales",
    "boost sales",
    "increase your revenue",
    "grow your business",
    "generate leads",
    "lead generation",
    "b2b leads",
    "sales leads",
    "email list",
    "verified leads",
    "make money online",
    "passive income",
    "investment opportunity",
    "loan offer",
    "crypto investment",
    "forex trading",
    "binary options",
    "casino",
    "betting site",
    "adult content",
    "buy followers",
    "buy likes",
)

# A couple of shapes a plain word list cannot express. Each carries the term it
# counts as, so UNBLOCKED_TERMS switches the pattern off along with the word.
SPECIAL = (
    # s.e.o / s-e-o, but not a sentence that happens to end in s before "e o".
    (r"\bs\W?e\W?o\b", "seo"),
    # "#1 on Google", "no.1 in search results". There is no \b before the "#":
    # a word boundary needs a word character on one side, so one there would
    # never match after a space.
    (r"(?:#\s*1|\bnumber one\b|\bno\.?\s*1\b)[^.]{0,30}?\b(?:google|search)\b",
     "number one on google"),
)


def _normalise(text):
    """Fold accents, drop punctuation, and flatten spacing."""
    text = unicodedata.normalize("NFKD", str(text or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower()
    # Keep the raw form too, so SPECIAL patterns can still see punctuation.
    flat = re.sub(r"[^a-z0-9]+", " ", text)
    return f" {flat.strip()} ", text


def _allowed():
    return {t.strip().lower() for t in getattr(settings, "UNBLOCKED_TERMS", []) if t.strip()}


def _terms():
    """The live list: built-in, plus any extras, minus anything unblocked."""
    extra = {t.strip().lower() for t in getattr(settings, "EXTRA_BLOCKED_TERMS", []) if t.strip()}
    return sorted((set(BLOCKED) | extra) - _allowed(), key=len, reverse=True)


def find_blocked_term(*texts):
    """The first marketing term found in these texts, or None.

    Longer terms are checked first, so a refusal names "seo services" rather
    than "seo" when both would match, which makes the log easier to read.
    """
    terms = _terms()
    allowed = _allowed()
    specials = [(pattern, label) for pattern, label in SPECIAL if label not in allowed]
    for text in texts:
        if not text:
            continue
        flat, raw = _normalise(text)
        for term in terms:
            needle = " " + re.sub(r"[^a-z0-9]+", " ", term).strip() + " "
            if needle in flat:
                return term
        for pattern, label in specials:
            if re.search(pattern, raw):
                return label
    return None
