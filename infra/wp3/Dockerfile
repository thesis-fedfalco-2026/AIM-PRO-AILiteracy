FROM postgres:18.6
COPY --chmod=0644 10-restore.sh /docker-entrypoint-initdb.d/10-restore.sh
COPY --chmod=0644 search.sql /opt/wp3/search.sql
RUN chmod 0755 /opt/wp3
