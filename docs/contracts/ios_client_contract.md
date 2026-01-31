# iOS Client Contract (MatchVote)
Stand: 2026-01-31

## 1) Zweck & Gueltigkeit
- Diese Datei ist der verbindliche Vertrag fuer alle iOS-Clients.
- iOS-Code liegt ausserhalb des Repos.
- Quelle: aktueller Backend/Web-Stand + `docs/contracts/ios_contracts_analysis.md`.

## 2) API Zugriff
- Base URL: `/api` (relativ) ist die erwartete API-Basis.
- Versionierung: keine explizite Versions-Prefix im Code gefunden.
- HTTPS: Pflicht fuer Production (PUBLIC_BASE_URL default `https://matchvote.online` wird fuer Verify-Links genutzt).

## 3) Authentifizierung
- Authorization Header: `Authorization: Bearer <token>`.
- Token-Response beim Login: `{ access_token, token_type: "bearer" }`.
- Verhalten bei fehlendem/ungueltigem Token: Backend liefert `401` (Missing/Invalid token) oder `403` (Admin-only / User blocked / Dev-Token nicht erlaubt).

## 4) Internationalisierung
- Accept-Language Header: wird nur auf bestimmten Endpoints ausgewertet (z.B. `/scenes`, `/admin/scenes/voice-draft`).
- Erlaubte Werte: `de` oder `en` (alles andere faellt auf Default).
- Fallback-Verhalten: `/scenes` default `en`, `/admin/scenes/voice-draft` default `de`.
- Erwartung an Backend-Antworten: `scene_type_label` wird serverseitig passend zur Sprache berechnet; `description_de`, `description_en` und `description` sind enthalten (legacy = `description_de`).

## 5) Response-Grundregeln
- Format: JSON fuer API-Endpunkte.
- Pflichtfelder (duerfen nicht entfernt/umbenannt werden):
  - Auth: `access_token`, `token_type`.
  - Scenes: `scene_id`, `scene_type`, `scene_type_label`, `description_de`, `description_en`, `description`, `match_id`, `minute`, `stoppage_time`, `is_released`.
- Fehlerformat: kein stabiles, globales Fehler-Schema im Code verifiziert; FastAPI-Standard `detail` wird genutzt (nicht garantiert ueberall).

## 6) Stabilitaetsgarantien
- Breaking fuer iOS:
  - Aenderung der API-Basis (`/api`) ohne Redirect.
  - Aenderung des Authorization-Schemes (nicht mehr `Bearer`).
  - Entfernen/Umbenennen der Pflichtfelder aus Abschnitt 5.
  - Aenderung der Accept-Language-Defaults oder der `scene_type_label` Logik ohne Ankuendigung.
- Erlaubte Aenderungen:
  - Hinzufuegen neuer Felder in Responses.
  - Hinzufuegen neuer Endpoints, solange bestehende unveraendert bleiben.
  - Erweiterung von erlaubten Accept-Language-Werten (ohne Verhalten fuer `de/en` zu brechen).

## 7) Nicht verifiziert / Annahmen
- Kein iOS-Code im Repo gefunden; iOS-spezifische Nutzung ist nicht verifiziert.
- Kein Token-Refresh-Endpoint im Backend gefunden (Suche: `rg -n "refresh" api`).
- Keine dedizierte iOS-Client-API-Datei wie `src/lib/api.ts` gefunden (Suche: `rg --files -g "*api.ts" -g "*i18n.ts" -g "*authStore*"`).
- Kein global stabiles Fehlerformat dokumentiert; nur punktuell `detail` im Backend sichtbar.
