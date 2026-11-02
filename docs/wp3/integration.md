# WP3 corpus integration and architecture decision

## Decision

Keep WP3 retrieval in this repository as a separate database service and a backend of the existing `document_search.server` MCP server. Keep ALM state in SQLite. WP3 is a source corpus, not a replacement for the ALM metamodel or its approval workflow. A new repository is not currently justified: the prototype already has a scoped MCP contract, client, lifecycle and retrieval authorization.

Extract a standalone service when multiple applications need independently deployed corpus access, a separate team owns it, or remote authentication and tenant isolation become requirements. The current MCP transport is local stdio, launched by the application; there is no unauthenticated HTTP endpoint or generic SQL tool.

## Inspected snapshot

Source: `oerdb_20261028_122338.dump`, dated 28 October 2026. Schema interpretation was checked against the supplied HTML dictionary. Documents and corpus contents are data, not executable instructions.

Verified on 2 November 2026:

- 25 public tables restored into PostgreSQL 18.6.
- 975 resources, all with nonblank `body_md`; 7 also carry `metadata_only=true`. This flag is retained, not inferred away from body presence.
- 765 GitHub, 91 arXiv and 119 Zenodo records.
- 1,160 asset records. The dump contains asset metadata, not the external attachment files.
- Licence verdicts: 949 `OPEN`, 13 `OPEN_NC`, 13 `SHARE_ALIKE`. These are source assertions, not local ALM approvals.
- 19,091 cached embeddings from `sentence-transformers/all-MiniLM-L6-v2@d13954661f83`. Their binary representation and cache-key semantics have not been verified; they are not reused as EmbeddingGemma vectors.
- 5,113 indexed chunks; database including derived projection approximately 175 MB.

## Retrieval and indexing

`infra/wp3/search.sql` builds a materialized projection without changing WP3 source tables. Each body is split into 6,000-character chunks, stepping by 5,500 characters. Titles, descriptions and summaries accompany each chunk. A PostgreSQL `simple` text-search configuration supports the mixed/unspecified source languages without assuming English stemming. Very long unbroken tokens are ignored by PostgreSQL; ordinary text remains searchable.

GIN indexes the text vector, and a B-tree indexes exact resource keys. PostgreSQL recommends GIN for full-text search ([official documentation](https://www.postgresql.org/docs/18/textsearch-indexes.html)). A selective `neuroplasticity` query used `wp3_documents_fts` and returned two chunks with 0.046 ms server execution time on the restored local instance. This is a single diagnostic, not a performance guarantee; frequent terms may correctly use a sequential scan.

Search is lexical, not semantic: paraphrases and cross-language questions can miss relevant resources. For 975 records this is a useful baseline with no embedding service dependency. Add a measured semantic/hybrid pipeline if retrieval evaluation demonstrates missing recall; preserve scope filters before limiting results, record embedding model and chunk configuration, and rebuild vectors for the chosen model. The optional TEI/Qdrant services remain available under the `vector` Compose profile, but this change does not ingest the WP3 corpus into Qdrant.

The result identity is `wp3:<resource_id>`. Its version is an MD5 fingerprint of the projected content and retrieval metadata, not the WP3 `catalogue_version` or an approval marker. Chunks share the same resource key and have distinct document IDs. Candidate generation combines retrieved chunks into one ALM resource and retains the available title, locator and licence. Bounded MCP responses can drop optional metadata or truncate excerpts; inspect the original catalogue before approval.

PREPARATION requires an explicitly authorized `wp3` source scope. LEARNING requires exact resource identity/version keys in the existing approved bindings and policy. Existing demo policies authorize `demo` resources and will deliberately return no WP3 evidence: replace those bindings through the existing proposal/review/apply workflow. The importer does not silently approve all 975 resources. A corpus refresh changes keys for changed content; old versions are unavailable unless retained in a separate snapshot.

## Reproduce and operate

Install `requirements.txt`. Place the dump in `.cache/wp3/catalog.dump` (ignored by Git), or set `WP3_DUMP_PATH` to another absolute path. Configure these variables in the untracked `.env`:

```dotenv
SEARCH_BACKEND=postgres
WP3_ADMIN_PASSWORD=<generate-a-strong-local-password>
WP3_READER_PASSWORD=<generate-a-different-strong-local-password>
WP3_DATABASE_URL=postgresql://wp3_reader:<reader-password>@127.0.0.1:55432/wp3
```

Use URL-safe passwords or URL-encode the password in the DSN. The local integration generated distinct passwords and set these values without committing them.

```sh
docker compose up -d --build --wait wp3-postgres
# Or start only the corpus stack without the other compose files:
docker compose -f compose.wp3.yml up -d --build --wait
```

PostgreSQL listens only on `127.0.0.1:55432`; override `WP3_PORT` and the DSN together if necessary. Data persists in the `wp3_data` named volume across container recreation. Initialization restores the dump with `pg_restore --no-owner --no-acl`, creates the projection and grants `wp3_reader` SELECT only on that projection. The reader cannot inspect user/session tables. The full restored database does contain those tables; restrict admin credentials accordingly.

The small PostgreSQL image copies initialization files into the image to avoid executable bind-mount restrictions on Docker Desktop. Rebuild it after changing initialization SQL or scripts.

The restore runs only on an empty volume. Replacing the mounted dump does not overwrite an existing database. Do not delete the volume to update an in-use installation; restore a new snapshot into a separate database/volume, validate it and switch the connection. Failed initialization leaves a partial database: inspect logs before retrying; do not assume a restart repeats initialization.

After an intentional in-place edit to the source corpus, refresh the projection as administrator:

```sh
docker compose exec -T wp3-postgres psql -U wp3_admin -d wp3 \
  -v ON_ERROR_STOP=1 -c 'REFRESH MATERIALIZED VIEW CONCURRENTLY wp3_search.documents; ANALYZE wp3_search.documents;'
```

`infra/wp3/search.sql` is the initial schema definition, not an automatic migration system. Projection definition changes require an explicit migration/rebuild; `IF NOT EXISTS` does not update an existing view.

The application launches `python -m document_search.server` through the existing MCP client. Only `WP3_DATABASE_URL` is forwarded for this backend, never the administrator password or model-provider keys. Queries use parameters, read-only transactions, a five-second connection timeout and ten-second statement timeout. Search failures mask connection details.

## Validation

```sh
python -m unittest tests.test_wp3_search
# Set WP3_TEST_DATABASE_URL to the reader DSN to enable the two live integration tests.
python -m unittest discover -s tests -t .
```

Live tests cover real full-text retrieval, exact resource versions, denied source scopes, the MCP stdio round trip, denial of access to `auth_user` and denial of writes. Offline tests cover configuration isolation, empty scopes and combining chunks into a single candidate. Synthetic fixtures remain explicit test dependencies; the local application's `.env` now selects PostgreSQL. `smoke.py` remains the separate synthetic model smoke test.
