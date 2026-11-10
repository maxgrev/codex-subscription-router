# Compatibility

The patcher is intentionally tied to known ChatGPT desktop bundle structures.
It verifies every modified renderer, main-process, and native binary anchor and
stops instead of applying a partial patch.

## Current

| Component | Tested value |
| --- | --- |
| Official ChatGPT version | `26.1103.60933` |
| Official bundle build | `25894` |
| `app.asar` SHA-256 | `a77588b2dcfa9b394d722dd8c2c8b13d3a09bacd49c839cc715245742dba6048` |
| Architecture | Apple silicon (`arm64`) |

Older builds that still match the patcher's anchors are listed in
`scripts/patch_app.py`. A build that is not on that list is rejected unless
you pass `--allow-untested-source`.

## Release 0.1.0

| Component | Tested value |
| --- | --- |
| Official ChatGPT version | `26.803.61601` |
| Official bundle build | `6396` |
| `app.asar` SHA-256 | `d5a44ed9e2f1db5f81dbbe85408aed256f3203c5b16f00817bb9d7cd941343cf` |
| Architecture | Apple silicon (`arm64`) |

A different official version may work when all anchors remain identical, but
it is unverified. The patcher rejects a version, build, or ASAR hash mismatch by
default; `--allow-untested-source` is an explicit diagnostic override. Never
weaken an anchor-count or binary-constant check merely to make a new build
complete. Review the upstream change and update the patch deliberately.
