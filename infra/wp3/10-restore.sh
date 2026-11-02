#!/bin/sh
set -eu
pg_restore --exit-on-error --no-owner --no-acl --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" /backup/catalog.dump
psql --set ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" --file /opt/wp3/search.sql
psql --set ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" --set reader_password="$WP3_READER_PASSWORD" <<'SQL'
CREATE ROLE wp3_reader LOGIN PASSWORD :'reader_password';
GRANT CONNECT ON DATABASE wp3 TO wp3_reader;
GRANT USAGE ON SCHEMA wp3_search TO wp3_reader;
GRANT SELECT ON wp3_search.documents TO wp3_reader;
ALTER ROLE wp3_reader SET default_transaction_read_only = on;
ALTER ROLE wp3_reader SET statement_timeout = '10s';
SQL
