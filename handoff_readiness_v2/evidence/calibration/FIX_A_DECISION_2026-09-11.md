# CRV2-11 AI diffusion decision — Fix A retained

**Decision date:** 2026-09-11  
**Decision owner:** competition owner  
**Rule for the release candidate:** retain **Fix A only**.

AI competitors remain in the competitive-attractiveness denominator and their
take is recorded. Each resolved segment-market therefore continues to reconcile
to:

```text
human adoption + AI adoption + unserved adoption = Bass adoption pool
```

Only human adoption enters Bass cumulative adoption (`N`). AI adoption must not
be added to `N` for this competition release.

This decision deliberately does not claim that Fix B is unsound. Adding AI
adoption to `N` would steepen early imitation and deplete later adoption sooner;
it is a future rules/calibration change, not an accounting correction. The
existing ten-round runtime evidence remains the baseline for later comparison.

Remaining CRV2-11 work under this decision is fixed-policy sensitivity and
field-size/saturation measurement. Neither may change pricing, production,
profile, market, AI, or scoring dials merely to make a measurement look more
favourable.
