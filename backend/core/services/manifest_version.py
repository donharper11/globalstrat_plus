"""The manifest schema version, alone, so both sides can read it.

`resolution_manifest` writes it onto every manifest; `manifest_schema` names
the reviewed inventory file after it. Keeping it here rather than in either
one lets the schema inventory depend on the version without the version
module having to import the whole manifest machinery.
"""

# Bump whenever the reviewed inventory changes what bytes a round hashes to.
# Two envelope definitions sharing one number is the failure this cannot
# survive: a stored hash would be compared against a differently-defined
# envelope of the same version and the difference read as tampering.
#
# 1 -> 2: canonical snapshots through `manifest_sections`.
# 2 -> 3: CRV2-10 Stage 4 -- the `team_product_platform_history` section and
#         the `platform_switch_write_off` financial line.
# 3 -> 4: CRV2-11 -- recorded AI adoption and per-pool demand reconciliation.
MANIFEST_SCHEMA_VERSION = 4
