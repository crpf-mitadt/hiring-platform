# Screening engine contract fixture

This test-only package snapshots the `StructuredJD` schema used by the
screening engine at baseline `3162575b1a15ecdb53b354da927c78340062f94c`.
It lets the platform's synthetic backend suite validate the cross-repository
contract on an isolated GitHub runner without credentials, live services, or a
second private-repository checkout.

Keep `common.py` and `jd.py` synchronized when the engine changes the
`structured-jd-v1` contract. Production continues to load the schema from the
configured `HIRING_SCREENING_ENGINE_ROOT`; this fixture is not production code.
