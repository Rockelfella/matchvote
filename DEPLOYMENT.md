# MatchVote Deployment

## Voraussetzungen
- Ubuntu 22.04
- Python 3.10+
- PostgreSQL 14+
- NGINX
- Uvicorn

## Dienste
- FastAPI: läuft als systemd Service `matchvote-api`
- NGINX: /etc/nginx/sites-available/matchvote

## Start
systemctl start matchvote-api
systemctl reload nginx

## Ports
- Intern: 127.0.0.1:8000
- Extern: 443 (NGINX)

## ENV
- Konfiguration erfolgt ausschließlich über Umgebungsvariablen (z. B. per systemd `Environment=`).

## OpenLigaDB Sync (Cron)
Beispiel (alle 6 Stunden):
```
0 */6 * * * /bin/bash -lc 'cd /opt/matchvote/api && /opt/matchvote/venv/bin/python scripts/sync_openligadb.py >> /var/log/matchvote-openligadb.log 2>&1'
```
Hinweis: benötigte Umgebungsvariablen für den Job per Cron-Environment oder systemd Timer setzen.
Optional:
- Nur eine Liga: `--league BL1` oder `--league BL2`
- Saison ueberschreiben: `--season 2024`
- Bestehende Saison trotzdem synchronisieren: `--force`
