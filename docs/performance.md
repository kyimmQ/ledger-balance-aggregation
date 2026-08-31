# Local ingestion performance

Measured on 31 August 2026 at 13:55 ICT (UTC+07). These measurements cover the
complete replacement-ingestion lifecycle: table reset, rate persistence, all
per-row atomic upserts, worker completion, and final database statistics. The
sequential oracle calculation and the complete stored-row comparison run outside
the timed region.

Every measured case matched every ordered account row and the exact total from
the independent sequential `Decimal` oracle.

## Environment

- CPU: AMD Ryzen 5 5600H, 6 cores / 12 logical CPUs
- Memory: 7.6 GiB
- OS/kernel: Linux 7.0.0-30-generic x86_64
- Docker Engine: 29.7.2
- Python: 3.12.5
- asyncpg: 0.31.0
- PostgreSQL: 17.11 (`postgres:17-alpine` in local Docker Compose)
- Database pool maximum: 10 connections
- Write strategy: bounded concurrent per-row upserts

## Baseline workload

The baseline fixture contains 50,000 transactions, 900 accounts, and 50 rates.
Its exact total is `-97516.970386899600000000` USD (the fixture summary's
equivalent unpadded value is `-97516.9703868996`).

| Workers | Transactions | Accounts | Rates | Total USD | Elapsed (s) | Rows/s | Pool max | Queue capacity | Max connections |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 50000 | 900 | 50 | -97516.970386899600000000 | 40.919 | 1221.9 | 10 | 1 | 1 |
| 2 | 50000 | 900 | 50 | -97516.970386899600000000 | 19.777 | 2528.2 | 10 | 2 | 2 |
| 5 | 50000 | 900 | 50 | -97516.970386899600000000 | 11.927 | 4192.3 | 10 | 5 | 5 |
| 10 | 50000 | 900 | 50 | -97516.970386899600000000 | 9.663 | 5174.4 | 10 | 10 | 10 |

## Hot-account workload

The hotspot fixture contains 50,000 transactions, one account, and 50 rates. Its
exact total is `788150.493642082600000000` USD (the fixture summary's equivalent
unpadded value is `788150.4936420826`). Every write contends on the same account
row.

| Workers | Transactions | Accounts | Rates | Total USD | Elapsed (s) | Rows/s | Pool max | Queue capacity | Max connections |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 50000 | 1 | 50 | 788150.493642082600000000 | 40.659 | 1229.7 | 10 | 1 | 1 |
| 2 | 50000 | 1 | 50 | 788150.493642082600000000 | 19.700 | 2538.1 | 10 | 2 | 2 |
| 5 | 50000 | 1 | 50 | 788150.493642082600000000 | 18.472 | 2706.8 | 10 | 5 | 5 |
| 10 | 50000 | 1 | 50 | 788150.493642082600000000 | 19.461 | 2569.3 | 10 | 10 | 10 |

## Default concurrency

The configured default remains 10. It delivered the best baseline result at
5,174.4 rows/s, about 23% more throughput than five workers, while maintaining
the same exact result and respecting the ten-connection pool bound. The
single-account workload peaked at five workers; ten workers were about 5% slower
because PostgreSQL must serialize updates to the same row. That fixture is an
intentional maximum-contention extreme, and the ten-worker result remains close
to its best measurement while performing best on the broad-account workload.

The evidence therefore supports 10 as a reasonable general local default, not
as a claim that it is optimal for every account distribution. A deployment with
a known single-account-heavy workload could deliberately configure five workers.
No batching or automatic concurrency tuning was introduced.

## Commands

```bash
docker compose up -d db
uv run --project backend --locked alembic -c backend/alembic.ini upgrade head
make benchmark
make benchmark \
  TRANSACTIONS=backend/fixtures/generated/hotspot/transactions.csv \
  RATES=backend/fixtures/generated/hotspot/exchange_rates.csv
```

The benchmark is destructive: each case clears and replaces the configured
ledger tables. These results describe one local machine and one run per measured
configuration. They are not a production capacity guarantee; hardware, Docker
resources, storage, background activity, network latency, and PostgreSQL tuning
can materially change performance.
