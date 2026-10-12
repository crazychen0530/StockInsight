\set ON_ERROR_STOP on
\set owner_password `cat /run/secrets/owner_password`
\set api_password `cat /run/secrets/api_password`
\set worker_password `cat /run/secrets/worker_password`
\set backup_password `cat /run/secrets/backup_password`
CREATE ROLE si_owner LOGIN PASSWORD :'owner_password';
CREATE ROLE si_api LOGIN PASSWORD :'api_password';
CREATE ROLE si_worker LOGIN PASSWORD :'worker_password';
CREATE ROLE si_backup LOGIN PASSWORD :'backup_password';
ALTER DATABASE stockinsight OWNER TO si_owner;
REVOKE ALL ON DATABASE stockinsight FROM PUBLIC;
GRANT CONNECT ON DATABASE stockinsight TO si_api, si_worker, si_backup;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
ALTER SCHEMA public OWNER TO si_owner;
GRANT USAGE ON SCHEMA public TO si_api, si_worker, si_backup;
ALTER DEFAULT PRIVILEGES FOR ROLE si_owner IN SCHEMA public GRANT SELECT ON TABLES TO si_api, si_backup;
ALTER DEFAULT PRIVILEGES FOR ROLE si_owner IN SCHEMA public GRANT SELECT, INSERT, UPDATE ON TABLES TO si_worker;
ALTER DEFAULT PRIVILEGES FOR ROLE si_owner IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO si_worker;
ALTER ROLE si_api SET default_transaction_read_only = on;
ALTER ROLE si_backup SET default_transaction_read_only = on;
