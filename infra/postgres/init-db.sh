#!/bin/bash
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE USER temporal WITH PASSWORD 'temporal';
    CREATE DATABASE temporal;
    GRANT ALL PRIVILEGES ON DATABASE temporal TO temporal;
    \c temporal
    GRANT ALL ON SCHEMA public TO temporal;

    CREATE DATABASE temporal_visibility;
    GRANT ALL PRIVILEGES ON DATABASE temporal_visibility TO temporal;
    \c temporal_visibility
    GRANT ALL ON SCHEMA public TO temporal;
EOSQL
