# Release assets and publication commands

The versioned GitHub release and Zenodo deposit use these frozen assets:

```text
ESTHER_RP001_v0_8_1_PUBLIC_RESEARCH_RELEASE_2026-07-19.zip
SHA-256: c57eb0d267c100b069f1b74402ee62d1693b495f1454b9275e17964f1ea31ce7

ESTHER_RP001_v0_8_1_BLIND_REVIEW_PACKET.zip
SHA-256: 38288d2000a8295c8eb8bc540c3fab4491aa66b1dca60a4d45135a957e4834f6
```

## GitHub release

From the local directory containing the four asset and checksum files:

```powershell
gh release create esther-rp-001-v0.8.1 `
  .\ESTHER_RP001_v0_8_1_PUBLIC_RESEARCH_RELEASE_2026-07-19.zip `
  .\ESTHER_RP001_v0_8_1_PUBLIC_RESEARCH_RELEASE_2026-07-19.zip.sha256.txt `
  .\ESTHER_RP001_v0_8_1_BLIND_REVIEW_PACKET.zip `
  .\ESTHER_RP001_v0_8_1_BLIND_REVIEW_PACKET.zip.sha256.txt `
  --repo Kot141078/ester-theoretical-core `
  --title "ESTHER-RP-001 v0.8.1 — Public research release" `
  --notes-file .\GITHUB_RELEASE_NOTES.md
```

Verify that `ester-theoretical-core` is enabled in Zenodo's GitHub integration before creating the GitHub release. If it is not enabled, upload the complete public-release ZIP manually to Zenodo and use the metadata from `.zenodo.json` and `CITATION.cff`.

Do not reuse the earlier v0.1 DOI as the version DOI for this new file set. Relate the new record to `10.5281/zenodo.20679718` as `isSupplementTo`.
