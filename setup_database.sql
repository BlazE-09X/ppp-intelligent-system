-- Этот файл создаёт пользователя и базу данных для проекта.
-- Запускается один раз через pgAdmin

-- 1. Создаём пользователя
CREATE USER gcp_user WITH PASSWORD 'gcp_password';

-- 2. Создаём базу данных
CREATE DATABASE gcp_db OWNER gcp_user;

-- 3. Даём права
GRANT ALL PRIVILEGES ON DATABASE gcp_db TO gcp_user;
