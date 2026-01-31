# Workflow (Kurznotiz)

- main ist protected: Aenderungen nur via Branch + PR (Squash).
- Falls versehentlich auf main committed wurde und der Push abgelehnt wird:
  1) Branch vom aktuellen Stand erstellen, pushen, PR oeffnen.
  2) Nach Merge lokal main resync: git fetch origin && git reset --hard origin/main.
- Keine Server-Edits ausser Notfall; danach sofort ins Repo nachziehen.
