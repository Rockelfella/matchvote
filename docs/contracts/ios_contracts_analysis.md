# iOS Contracts Analyse (Matchvote)
Stand: 2026-01-31

## A. Quellen
- docs/contracts/network_contract_ios_matchvote.md - nicht gefunden (Suche: rg --files -g "*network_contract_ios_matchvote*")
- docs/contracts/ios_localization_documentation.md - nicht gefunden (Suche: rg --files -g "*ios_localization_documentation*")
- docs/contracts/backend_i18n_contract.md - nicht gefunden (Suche: rg --files -g "*backend_i18n_contract*")

Hinweis: Die angeforderten iOS-Contract-Dateien sind im Repo nicht vorhanden. Die folgenden Contracts sind daher aus dem aktuellen Code-Stand abgeleitet und entsprechend als Ist-Stand markiert.

Zusaetzlich ausgewertete Code-Quellen (Ist-Stand):
- api/app/core/application.py
- api/app/api/v1/auth.py
- api/app/core/deps.py
- api/app/core/user_auth.py
- api/app/api/v1/scenes.py
- api/app/api/v1/admin_scenes.py
- api/app/schemas/scenes.py
- api/backend/resources/i18n/football_terms.de.json
- api/backend/resources/i18n/football_terms.en.json
- api/tests/test_contracts.py
- web/ratings.js
- web/auth.html
- web/admin.html
- web/user.html

## B. Extrahierte iOS-Contracts (aus Ist-Stand Code)

### API Base URLs (welche, wo verwendet)
- Default API Base: `/api` (relativ) in Web-Clients; gespeichert in `localStorage.mv_api_base`, Normalisierung entfernt trailing `/`.
  - Quellen: `web/auth.html`, `web/ratings.js`, `web/admin.html`, `web/user.html`.
- Backend Root-Path: FastAPI `root_path="/api"`.
  - Quelle: `api/app/core/application.py`.
- Public Base fuer Verify-Link: `PUBLIC_BASE_URL` default `https://matchvote.online` (nur fuer E-Mail-Verify-Link, nicht API-Basis).
  - Quelle: `api/app/api/v1/auth.py`.
- Externe API (nicht iOS, aber Backend intern): SportMonks `https://api.sportmonks.com/v3/football`.
  - Quelle: `api/app/core/client.py`.

### Pflicht-Header + genaue Werte/Logik
- `Authorization: Bearer <token>` fuer geschuetzte Endpoints (User/Admin). Backend erwartet explizit Scheme `Bearer`.
  - Quellen: `api/app/core/user_auth.py`, `api/app/core/deps.py`.
- `Accept-Language` optional; nur bestimmte Endpoints werten ihn aus.
  - Scenes API liest `Accept-Language` und akzeptiert primär `de` oder `en` (Rest faellt auf Default).
  - Admin voice-draft nutzt `Accept-Language` oder `lang` Formularfeld.
  - Quellen: `api/app/api/v1/scenes.py`, `api/app/api/v1/admin_scenes.py`.
- `Content-Type: application/json` bei JSON-Body; Web-Clients setzen Header nur wenn Body vorhanden.
  - Quellen: `web/ratings.js`, `web/auth.html`, `web/user.html`, `web/admin.html`.
- Uploads (`/admin/scenes/voice-draft`): `multipart/form-data` (Form-Fields `lang`, `audio`/`transcript`).
  - Quelle: `api/app/api/v1/admin_scenes.py`.

### Token Storage/Refresh
- Login liefert `access_token` und `token_type: "bearer"`.
  - Quellen: `api/app/api/v1/auth.py`, `api/app/schemas/auth.py`.
- Web-Clients speichern `access_token` in `localStorage.mv_access_token`.
  - Quellen: `web/auth.html`, `web/ratings.js`, `web/user.html`, `web/admin.html`.
- Anhaengen: `Authorization: Bearer <token>` in Fetch-Wrappern.
  - Quellen: `web/ratings.js`, `web/user.html`, `web/admin.html`.
- Verhalten bei 401/403: Token loeschen und Login-Redirect.
  - Quellen: `web/ratings.js`, `web/user.html`, `web/admin.html`.
- Kein Refresh-Endpoint im Backend gefunden (Suche: `rg -n "refresh" api`).
  - Status: nicht verifiziert fuer iOS; im Ist-Stand existiert kein Token-Refresh.

### Localization
- Default Language (Backend Scenes): `en` wenn `Accept-Language` fehlt oder nicht `de/en`.
  - Quelle: `api/app/api/v1/scenes.py`.
- Default Language (Admin voice-draft): `de` wenn `lang`/`Accept-Language` fehlt.
  - Quelle: `api/app/api/v1/admin_scenes.py`.
- `scene_type_label` wird serverseitig anhand `SCENE_TYPE_LABELS` berechnet; Response enthaelt `description_de`, `description_en` sowie `description` (legacy = `description_de`).
  - Quellen: `api/app/schemas/scenes.py`, `api/app/api/v1/scenes.py`.
- Web-Clients setzen `Accept-Language` aus `navigator.languages[0]` oder `navigator.language` (ohne `mv_lang` Persistenz) in `ratings.js` und `admin.html`.
  - Quellen: `web/ratings.js`, `web/admin.html`.
- Einige Seiten nutzen `localStorage.mv_lang` als Persistenz (z.B. `user.html`, `credits.html`, `privacy.html`).
  - Quelle: `web/user.html` (und Suche `rg -n "mv_lang" web`).
- `setAPIAcceptLanguage` nicht gefunden (Suche: `rg -n "setAPIAcceptLanguage"`).
  - Status: nicht verifiziert.
- `date-fns` nicht gefunden (Suche: `rg -n "date-fns|datefns"`).
  - Status: nicht verifiziert.
- Zentrale i18n-Dateien fuer Glossar/Begriffe: `api/backend/resources/i18n/football_terms.de.json`, `api/backend/resources/i18n/football_terms.en.json`.
  - Quelle: `api/app/api/v1/admin_scenes.py`.

## C. Code-Abgleich (Drift Check)

Suche nach iOS-Pfaden/Modulen (z.B. `src/lib/api.ts`, `src/lib/i18n.ts`, `authStore.ts`):
- Ergebnis: nicht gefunden (Suche: `rg --files -g "*api.ts" -g "*i18n.ts" -g "*authStore*"`).

Drift-Tabelle:

| Contract-Punkt | Erwartung | Ist-Stand (Fundstelle) | Abweichung | Fix-Vorschlag |
| --- | --- | --- | --- | --- |
| iOS Contract Quellen | Drei Contract-Dateien vorhanden und aktuell | Nicht gefunden (Suche: `rg --files -g "*network_contract_ios_matchvote*" -g "*ios_localization_documentation*" -g "*backend_i18n_contract*"`) | Ja | Dateien unter `docs/contracts/` anlegen oder Pfade korrigieren. |
| API Base URL | API unter `/api` erreichbar | `/api` in Web-Clients, `root_path="/api"` im Backend | Nein | Keine Aenderung. |
| Authorization Header | `Authorization: Bearer <token>` | Backend erwartet Bearer-Token | Nein | Keine Aenderung. |
| Token Response | `access_token`, `token_type: bearer` | Login liefert `access_token`, `token_type` default `bearer` | Nein | Keine Aenderung. |
| Token Refresh | Refresh-Flow vorhanden | Kein Refresh-Endpoint gefunden | Nicht verifiziert vs. Contract | Falls iOS Refresh nutzt: Endpoint und Doku ergaenzen. |
| Accept-Language | Wird serverseitig ausgewertet | `scenes` und `admin_scenes` werten `Accept-Language` aus | Teilweise (nur bestimmte Endpoints) | Doku ergaenzen, welche Endpoints es nutzen. |
| Localization Persistenz | Persistenter App-Locale | `mv_lang` nur in einigen Seiten; `ratings.js` nutzt Navigator | Moegliche Drift zu iOS | Einheitliche Locale-Quelle definieren und dokumentieren. |
| iOS Client Pfade | `src/lib/api.ts` etc. existieren | Nicht gefunden | Ja | Repo-Pfad der iOS-App dokumentieren oder Submodule einbinden. |
| Response-Formate | Szenen enthalten `scene_type_label` und `description` | Backend setzt `scene_type_label` + `description` (legacy = `description_de`) | Nein | Keine Aenderung. |
| Accept-Language Tests | Contract abgesichert | Test vorhanden: `test_accept_language_no_4xx` | Nein | Optional: test fuer Label-Auswahl ergaenzen. |

## D. Risiken fuer iOS Release (Top 5)
1. API-Base Drift von `/api` (z.B. Wechsel zu `/v1` ohne Redirect) wuerde alle Requests brechen.
2. Aenderung des Authorization-Schemes (z.B. von `Bearer` auf `Token`) wuerde Auth sofort brechen.
3. Login Response ohne `access_token` oder geaenderter Feldname wuerde Token-Speicherung brechen.
4. Entfernen/Umbenennen von `description_de`/`description_en`/`description` oder `scene_type_label` bricht iOS-UI, wenn es diese Felder nutzt.
5. Aenderung der Accept-Language-Logik (Default oder Auswertung) fuehrt zu falschen Labels/Descriptions.

## E. Konkrete Next Steps (klein, repo-spezifisch)
1. Fehlende Contract-Quellen anlegen: `docs/contracts/network_contract_ios_matchvote.md`, `docs/contracts/ios_localization_documentation.md`, `docs/contracts/backend_i18n_contract.md`.
2. Contract-Test fuer Login-Response hinzufuegen: `api/tests/test_contracts.py` (assert `access_token`, `token_type`).
3. Contract-Test fuer `scene_type_label` Sprache hinzufuegen: `api/tests/test_contracts.py` (Accept-Language `de` vs `en`).
4. Einheitliche Locale-Quelle dokumentieren/angleichen: `web/ratings.js` (ggf. `mv_lang` nutzen wie `web/user.html`).
5. Accept-Language auch in `web/user.html` Requests setzen (falls Profil/Me-Locale relevant).
6. Doku fuer `mv_api_base` und Normalisierung ergaenzen: `web/auth.html`, `web/ratings.js`, `web/admin.html`.
7. iOS-App-Pfad im Repo festhalten (z.B. `docs/contracts/ios_contracts_analysis.md` oder `README.md`).
8. Optional: OpenAPI JSON fuer Clients dokumentieren (Admin-only aktuell): `api/app/main.py`.
