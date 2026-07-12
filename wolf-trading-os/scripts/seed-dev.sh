#!/usr/bin/env bash
# Reset the DEVELOPMENT database and load the synthetic sample fixtures.
# Refuses to run outside WTOS_ENVIRONMENT=development (enforced by the CLI).
set -euo pipefail
cd "$(dirname "$0")/.."

wolf-trading-os database-reset-dev --yes
wolf-trading-os import-option-alpha \
  tests/fixtures/option_alpha_sample.csv \
  tests/fixtures/option_alpha_overlap.csv
echo "Development database seeded with synthetic fixture trades."
