# Second environment for the GSP-CRV2-01 cross-environment replay.
#
# Deliberately unlike the host it is compared against: a different base OS
# image, a different Python patch line, a half-hour timezone offset, and a
# locale whose decimal separator is a comma. If any of those reached the
# hashed bytes, the competitive hash would move.
FROM python:3.11-slim-bookworm

# postgresql-client-18 from PGDG: the dumps are written by pg_dump 18, which a
# stock bookworm client (15) cannot read.
RUN apt-get update && apt-get install -y --no-install-recommends \
        locales git ca-certificates curl gnupg \
    && curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc \
        | gpg --dearmor -o /usr/share/keyrings/pgdg.gpg \
    && echo 'deb [signed-by=/usr/share/keyrings/pgdg.gpg] https://apt.postgresql.org/pub/repos/apt bookworm-pgdg main' \
        > /etc/apt/sources.list.d/pgdg.list \
    && apt-get update && apt-get install -y --no-install-recommends postgresql-client-18 \
    && sed -i 's/^# *\(de_DE.UTF-8\)/\1/' /etc/locale.gen \
    && locale-gen \
    && rm -rf /var/lib/apt/lists/*

ENV TZ=Asia/Kolkata \
    LANG=de_DE.UTF-8 \
    LC_ALL=de_DE.UTF-8 \
    PYTHONHASHSEED=random \
    PYTHONDONTWRITEBYTECODE=1
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Only what Phase 1 and the manifest need. The RAG/embedding stack is left out
# on purpose: it belongs to Phase 2, which is outside the competitive hash.
RUN pip install --no-cache-dir \
        'Django==5.2.4' 'djangorestframework==3.15.2' 'django-cors-headers==4.4.0' \
        'django-filter==1.1.0' 'psycopg2-binary==2.9.9' 'PyJWT>=2.0.0' \
        'httpx>=0.27.0' 'PyYAML>=6.0' 'requests>=2.31.0' 'qdrant-client>=1.7.0'

# Mounted at the host's own absolute path so the manifest's recorded
# backup path resolves identically inside the container.
WORKDIR /home/ubuntu/projects/globalstrat+/backend
