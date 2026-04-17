# Bootstrap schema for globalstrat+

## What

`unmanaged_tables_schema.sql` — DDL for the 10 tables declared as
`managed=False` in `backend/core/migrations/0001_initial.py` that actually
exist in the original `globalstrat_db`. Django's migration machinery won't
create these, so a fresh `globalstrat_plus` database is missing them until
this file is applied.

Migration `core.0016_cc21_instructor_alerts_change_log` adds an FK to
`core.user` (table `users`), so without the bootstrap the migrate step
fails with `relation "users" does not exist`.

## Tables

course, enrollment, grading_component_mapping, grading_rubric,
grading_rubric_category, section, simulation_instance,
student_grade_adjustment, team_grade, users

(The migration declares 50 `managed=False` tables, but only these 10 were
ever provisioned in the original DB. The other 40 are ghost models.)

## How it was produced

On a host with `pg_dump` matching the server major version (16):

```
pg_dump -h <host> -U <user> --schema-only --no-owner --no-privileges \
    -t public.course -t public.enrollment -t public.grading_component_mapping \
    -t public.grading_rubric -t public.grading_rubric_category -t public.section \
    -t public.simulation_instance -t public.student_grade_adjustment \
    -t public.team_grade -t public.users \
    -d globalstrat_db -f unmanaged_tables_schema.sql
```

`--schema-only` deliberately excludes row data: users, enrollment rows,
grading records etc. must never be cloned between databases.

## How to apply

Against a fresh `globalstrat_plus` before running `manage.py migrate`:

```
psql -h <host> -U <user> -d globalstrat_plus -f unmanaged_tables_schema.sql
cd backend && python3 manage.py migrate
```
