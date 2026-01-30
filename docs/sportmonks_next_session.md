# SportMonks – Next Session

## Current state
- Provider scaffold exists (SportMonks provider module + central switch).
- SPORTMONKS_ENABLED defaults to false.
- Neutral provider_service anchor exists.
- No endpoints changed.
- No database models changed.
- No jobs or scripts changed.

## Next big step (choose one consumer)
Wire exactly one OpenLigaDB job/script to call provider_service (still returns OpenLigaDB by default).

## Concrete plan
- [ ] Pick one job: `sync_openligadb` OR `import_openligadb_goals`
- [ ] Add minimal adapter function call in the job to `provider_service`
- [ ] Keep old code path behind a fallback comment
- [ ] Run the job locally / dry-run command
- [ ] Commit message suggestion: "Wire one job to provider_service"
