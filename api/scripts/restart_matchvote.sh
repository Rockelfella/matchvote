#!/usr/bin/env bash
set -euo pipefail

systemctl restart matchvote.service
systemctl status matchvote.service --no-pager --full
