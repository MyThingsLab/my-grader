# Changelog

## [Unreleased]
### Added/Changed
- MyGrader v0: grade a whole mock exam (TOML [[answer]]) against a corpus in ONE Engine call; per-question Attempt (kind=exam) to mastery ledger; per-topic weakest-first report; short-reply degrades missing items to stub, never drops questions. 14 tests, 94% cov.
- Mechanical migration to mythings.testing: inline ScriptedEngine replaced by the shared one (drop-in).
