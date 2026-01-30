#!/usr/bin/env bash
set -euo pipefail
set -a
source /etc/matchvote/matchvote.env
set +a

cd /opt/matchvote/api
exec /opt/matchvote/venv/bin/python -m app.cli.matchvote sportmonks-shadow-inplay
