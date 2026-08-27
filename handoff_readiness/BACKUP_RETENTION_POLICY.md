# Competition evidence retention and disposal policy

Approved operational baseline: 2026-08-27. The competition operations owner is
accountable for applying this policy; only the `ubuntu` application account and
root administrators may access recovery artifacts on this host.

## Scope and retention

- Pre-resolution database dumps and SHA-256 sidecars are retained throughout
  the event and for at least **90 days after provisional final results**, or
  **30 days after the final ruling on the last dispute or investigation**,
  whichever is later.
- Resolution manifests, decision/operator audit events and the durable recovery
  audit are retained for at least **12 months after final results or the final
  dispute ruling**, whichever is later.
- Reconstruction-relevant application/access logs and incident rulings are
  retained for at least 90 days under the same dispute-hold rule.
- An open dispute, incident investigation, appeal or legal hold suspends all
  pruning, even when an artifact is older than its normal retention period.

The 90-day dump period exceeds the published 24-hour dispute-filing window and
allows time to investigate and issue a ruling. Privacy/legal requirements that
mandate a longer hold take precedence; shortening these periods requires a
documented rules-owner and data-owner approval before participant data is
collected.

## Access and handling

The local backup directory is owned by `ubuntu:ubuntu` at mode `0700`; dumps,
checksums and the recovery audit are mode `0600`. Gunicorn runs with
`UMask=0077`, so new artifacts inherit the restriction. Root access remains
available for emergency administration. Dumps must never be sent through chat,
email or an unmanaged workstation. Any export or restore requires a recorded
ticket, a named instructor/admin authorizer and a second operator.

## Monitoring

`globalstrat-backup-monitor.timer` runs the read-only inventory daily and after
missed schedules. It fails and records details in the system journal if the
directory/file ownership or modes drift, a dump/checksum pair is invalid, free
space drops below 10 GiB, or filesystem use exceeds 80%. Operators must verify
the timer and its latest successful service result before the event and before
each resolution window. A resolution without a corresponding manifest and
verified dump is a stop condition and must be investigated immediately.

## Disposal

Pruning remains disabled in normal operation. After the retention period, the
operations owner must confirm in writing that the event is complete and no
dispute, investigation, appeal or legal hold remains. A second operator then:

1. runs the read-only inventory and preserves its output;
2. temporarily enables guarded pruning;
3. supplies the substantive reason and exact confirmation token;
4. verifies the intent/completion audit and absence of the selected pairs; and
5. disables pruning again.

Ordinary pruning is logical deletion, not a claim of forensic media erasure.
When the host, volume, snapshot or replica is retired, the infrastructure owner
must perform provider-approved media sanitization or cryptographic erasure and
record its ticket. Invalid or orphaned evidence is quarantined and investigated,
not manually deleted.
