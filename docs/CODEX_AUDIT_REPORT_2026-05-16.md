# कोडेक्स ऑडिट रिपोर्ट - ट्रेनप्लेक्स स्टूडियो कटओवर

**ऑडिटर:** Codex, स्वतंत्र थर्ड-पार्टी ऑडिटर  
**तारीख:** 2026-05-16  
**रेपो:** `cybdeer/trainplex-studio`; मांगा गया baseline `07b58cf8481ccdfd879191ccc63a5172b96f106b`; देखा गया local/VPS `develop` HEAD `086489d98f6dbba1cc2925a8b09afe1e37e58386`  
**प्रोडक्शन VPS:** `trainplex` SSH host  
**प्लान रेफरेंस:** `C:\Users\DESKTOP\.claude\plans\glowing-napping-storm.md` - 17 मूल steps और बाद में जोड़ा गया Phase 1.5 remediation section  
**ऑडिट मोड:** Read-only verification. कोई restart, rollback, migration, wrong-password attempt, या data-changing login POST नहीं किया गया।

## Executive Summary

- **Plan completion:** 0/17 steps पूरी तरह original plan के हिसाब से verified नहीं हैं; 15/17 partial हैं और उनमें material deviations हैं; 2/17 production-incomplete हैं।
- **Production health:** ⚠️ Live route चल रहा है, लेकिन readiness clean नहीं है।
- **Critical risks found:** 10
- **Production-ready verdict:** **NO-GO / सिर्फ limited internal validation के लिए conditional**

पहले failed audit की तुलना में production काफी बेहतर है: `/label-studio/user/login/` और `/api/v1/health` अब `200` दे रहे हैं, app crash-loop में नहीं है, TrainPlex templates API में दिख रहे हैं, core migrations apply हो चुकी हैं, और Vinod admin valid है। लेकिन deployment अभी clean production cutover नहीं माना जा सकता, क्योंकि model migrations drift में हैं, production repo में 73 dirty/untracked files हैं, rollback boot-proven नहीं है, celery worker unhealthy है, heatmap/search/reviewer checks fail या unverified हैं, और security hardening अधूरी है।

## नए अपडेट

| Area | Fresh result |
|---|---|
| External route | ✅ `/label-studio/user/login/` अब `HTTP/2 200` दे रहा है; पुराना 404 fix हो गया। |
| Health | ✅ `/label-studio/api/v1/health` अब `{"status":"ok","db":"ok"}` दे रहा है। |
| Templates | ✅ `/api/v1/admin/templates/catalog` अब `79 total` दिखा रहा है, जिसमें `10 TrainPlex custom` templates हैं। पहले custom count `0` था। |
| Containers | ⚠️ Production में अब 3 नहीं, 4 TrainPlex Studio containers हैं: `app`, `nginx`, `db`, और नया `scheduler`। |
| Data counts | ⚠️ Counts बदले हैं: users `14`, projects `8`, tasks `660`। Audit request में projects `5`, tasks `651` expected थे; original plan में `17 trainers + 1201 tasks` था। |
| Migrations | ❌ Requested migrations अब OK हैं, लेकिन `makemigrations --check --dry-run` अभी भी `core.0008` और `users.0016` pending दिखाता है। |
| Production repo | ❌ VPS repo में `73` dirty/untracked entries हैं। Deployed code clean commit नहीं है। |
| Security | ⚠️ Required headers हैं, पर cookies में `Secure` missing है, CORS wildcard है, और headers duplicate emit हो रहे हैं। |
| Monitoring | ❌ `trainplex_celery_worker` अभी भी unhealthy है; watchdog production नहीं, local/dev monitor कर रहा है। |

## A. Plan vs Built - हर Step की जांच

Legend: ✅ FULLY AS PLANNED, ⚠️ DEVIATION, ❌ MISSING/INCOMPLETE, 🔄 INTENTIONALLY DEFERRED

| Step | Status | Plan lines | Actual evidence | Audit finding |
|---|---|---:|---|---|
| 1. TrainPlex LS Fork | ⚠️ DEVIATION | 22-97 | Repo `C:\TrainPlex\trainplex-studio` पर है; production image अब `trainplex-studio:prod`; local/VPS HEAD `086489d...`। | Fork और live app मौजूद हैं, लेकिन original verification में `5 projects + 1201 tasks` था; current prod में `8 projects + 660 tasks` हैं। Local repo में `label_studio/reports/*` dirty है। |
| 2. Templates Activate | ⚠️ DEVIATION, improved | 100-156 | `backend/data/ls_templates/trainplex_india/` में 10 template folders हैं; API अब `79 total`, `10 TrainPlex custom`, `69 native` देता है। | 10 custom-template requirement अब production में pass है। Deviation इसलिए बचा है क्योंकि plan ने Git sync/drift cron और हर template के sample render/submit validation मांगे थे। BUILD_LOG ने native templates को Phase 1 hardcoded fallback बताया था। |
| 3. SSO simplification | ⚠️ DEVIATION / 🔄 DEFERRED | 158-223 | `trainplex_ls_sso` अभी भी running है; Step 3.1 ने SSO bridge remove करना कहा था। | Phase 1.5 में इसे transition safety के लिए intentionally kept बताया गया है और decommission Phase 2 में shift है। Operationally safer, पर original plan जैसा नहीं। |
| 4. Admin + Trainer UX | ⚠️ DEVIATION | 225-333 | Admin APIs exist. Dashboard `200`, templates `200`, audit `200`, WA templates `200`, quality alerts `200`, submissions preview `200`; heatmap `0` states देता है; search Vinod empty है। | कई surfaces अभी contract/demo level हैं। Plan ने 17-state heatmap, daily email, WA send confirmation, live trainer batch/PWA behavior मांगा था। BUILD_LOG में mock data और deferred real aggregation/voice/autosave noted हैं। |
| 5. UI/UX Design System | ⚠️ DEVIATION / 🔄 DEFERRED | 337-423 | Source में tokens/components हैं; Figma master, Storybook, Lighthouse, Android Chrome rendering का production proof नहीं मिला। | BUILD_LOG/verification ने Figma/Storybook/voice/a11y proof defer किया है। Production-proven नहीं है। |
| 6. Reviewer + Dispute | ❌ MISSING/INCOMPLETE IN PROD | 425-522 | `peer_review.0001_initial` migration applied है, पर roles में `admin=1`, `trainer=13`, reviewer `0`; reviewer queue real reviewer से verify नहीं हो सकी। | Tables/code हैं, लेकिन reviewer user नहीं है। Production reviewer journey वास्तविक रूप से operable साबित नहीं हुई। |
| 7. Reports + BI | ⚠️ DEVIATION | 525-619 | `/api/v1/admin/reports/founder-weekly` `200` देता है; local/VPS में `label_studio/reports/api.py`, `pdf_renderer.py`, `urls.py` dirty हैं। | Endpoint shape काम कर रहा है, पर BUILD_LOG के मुताबिक Phase 1 mock/contract data use करता है और cron scheduling deferred है। Dirty changes reports baseline को unstable बनाते हैं। |
| 8. Data Migration | ⚠️ DEVIATION | 625-789 | SQLite size `7,483,392` bytes; users `14`, projects `8`, tasks `660`; FK check rows `0`; backup मौजूद; old recovery container सिर्फ `Created` है। | Data preserved है और बढ़ा है, लेकिन counts plan/request से अलग हैं। Rollback safety boot-proven नहीं है। |
| 9. Testing Strategy | ⚠️ DEVIATION | 792-836 | Local backend test files `142`; web `.test.ts/.tsx` files `90`; VPS में extra untracked `test_phase2_real_data.py` है। | Count threshold pass है, पर tests ने migration drift, nginx config failure, celery unhealthy, heatmap/search bugs नहीं रोके। Visual/load gates unproven हैं। |
| 10. CI/CD + DevOps | ❌ MISSING/INCOMPLETE | 839-892 | Active workflow सिर्फ `test.yml`; deploy workflows disabled; app/nginx/scheduler health `none`; db healthy। | Plan ने staging/prod deploy workflows, auto rollback और health checks मांगे थे। Phase 1.5 में deploy workflows founder env/secrets pending बताकर disabled रखे गए हैं। |
| 11. Monitoring + Backup + DR | ⚠️ DEVIATION | 895-950 | Backup exists; watchdog log exists; `trainplex_celery_worker` unhealthy; watchdog `trainplex-studio-dev` और `localhost:8090/health` देखता है, production नहीं। | Monitoring false confidence देता है। यह production app/nginx/db/scheduler/celery/SSO/external URL नहीं देखता। |
| 12. Security Baseline | ⚠️ DEVIATION | 954-1028 | Login URL पर required headers हैं; cookies में `Secure` missing; `Access-Control-Allow-Origin: *`; duplicate HSTS/security headers; wrong-password runtime test नहीं किया। | Header middleware partly effective है, पर HTTPS cookie/CORS/header-source hardening incomplete है। Rate-limit code है, लेकिन live 429 mutation-test नहीं हुआ। |
| 13. Trainer Profile + Settings | ⚠️ DEVIATION / 🔄 DEFERRED | 1032-1091 | Source JSON namespace/profile APIs use करता है; `users.0016` pending migration user fields alter propose करती है। | Plan first-class profile/security/payout/settings चाहता था। Some source exists, पर migration drift model/schema mismatch दिखा रहा है। |
| 14. Global Search | ⚠️ DEVIATION | 1094-1137 | `/api/v1/admin/search?q=Vinod` `200` देता है लेकिन result empty है; `core.0006_fulltext_search_indexes` applied है। | Plan ने real scopes और fast search मांगा था। BUILD_LOG कहता है search अभी mock dataset use करता है और real FTS query Phase 2 है। |
| 15. i18n Framework | ⚠️ DEVIATION / 🔄 DEFERRED | 1141-1210 | React/i18n source exists; Django auth/template localization deferred documented है। | Plan ने all UI strings translated और immediate language switch मांगा था। Legacy Django/login path पूरी तरह Hindi proven नहीं है। |
| 16. Deploy Planner / QA Checker | ⚠️ DEVIATION / 🔄 DEFERRED | 1214-1494 | Active `qa-checker.yml` नहीं मिला; automated page checker deploy block कर रहा है, इसका proof नहीं मिला; current production manual dirty fixes पर है। | Plan ने हर step के बाद QA Checker और failed step never merge मांगा था। Current drift दिखाता है कि यह gate operational नहीं है। |
| 17. Scaling + Bug Prevention | ⚠️ DEVIATION | 1498-1825 | `trainplex-studio-scheduler-1` exists; `trainplex_celery_worker` unhealthy; production autoscale/auto-heal proof नहीं मिला। | Feature flags/runbooks exist, लेकिन auto provisioning, auto task distribution, temp worker spawn, chaos drill, और live founder ops dashboard production-proven नहीं हैं। |

### Phase 1.5 Remediation Status

Plan file में अब Phase 1.5 lines 1829-1987 हैं, जो पहले Codex audit के बाद add हुआ। Current status:

| Phase 1.5 item | Current status |
|---|---|
| C1 app crash-loop lock bug | ✅ Runtime level पर fix दिख रहा है; app up है और recent advisory-lock errors नहीं दिखे। |
| C2 external `/label-studio/*` 404 | ✅ Fixed; login और health `200` दे रहे हैं। |
| C3 missing required migrations | ✅ Requested migrations applied हैं; ❌ नया migration drift बचा है: `core.0008`, `users.0016`। |
| C4 old LS recovery container | ⚠️ `trainplex_label_studio_OLD_recovery` exists, पर सिर्फ `Created`; ports empty, logs empty; boot proven नहीं। |
| C5 SSO bridge | 🔄 Intentionally kept; अभी भी running है। |
| C6 security headers | ⚠️ Required headers present हैं, पर duplicate हैं; cookie/CORS hardening fail है। |
| C7 founder mobile literals | ⚠️ VPS tracked grep `0`, पर VPS `.env` में `<configured-guard>`; local tracked repo में 45 hits थे (Wave-19 W1-MOBILE में sanitized)। |
| C8 deploy workflows | 🔄 अभी भी disabled हैं। |
| C9 image tag | ✅ Production containers अब `trainplex-studio:prod` दिखाते हैं। |

## B. Production Deploy Verification

| Check | Result | Evidence |
|---|---|---|
| Expected 3 containers | ⚠️ DEVIATION | `docker ps --filter name=trainplex-studio` अब 4 containers दिखाता है: `trainplex-studio-app-1`, `trainplex-studio-scheduler-1`, `trainplex-studio-nginx-1`, `trainplex-studio-db-1`। |
| Container health | ⚠️ PARTIAL | DB `healthy`; app/nginx/scheduler running हैं, लेकिन Docker health `none` है। |
| App image | ✅ | `trainplex-studio:prod`। |
| `DJANGO_DB` | ✅ | `DJANGO_DB=sqlite`। |
| App host env | ✅ | `LABEL_STUDIO_HOST=https://app.trainplex.in/label-studio`। |
| Secure-cookie env flags | ❌ | `SESSION_COOKIE_SECURE` और `CSRF_COOKIE_SECURE` env grep में नहीं मिले। |
| Data preserved | ⚠️ Count drift | Current SQLite: users `14`, projects `8`, tasks `660`; requested check users `14`, projects `5`, tasks `651` था। |
| Required migrations | ✅ requested list OK | `users.0012_add_role_field`, `users.0013_audit_log`, `users.0014_user_2fa_fields`, `peer_review.0001_initial`, `payments.0001_initial`, `core.0006`, `core.0007` present हैं। |
| Migration drift | ❌ | `makemigrations --check --dry-run` `core.0008...` और `users.0016...` propose करता है। |
| Vinod admin | ✅ | `vk.vinodparihar1@gmail.com`, role `admin`, `is_superuser=1`, `is_staff=1`। |
| Role distribution | ⚠️ | `admin=1`, `trainer=13`, reviewer `0`। Reviewer production flow real-user verified नहीं हो सकता। |
| Old rollback container | ⚠️ | `trainplex_label_studio_OLD_recovery` exists, image `heartexlabs/label-studio:1.13.1`, state `Created`, ports `{}`। |
| Backup exists | ✅ | `/var/backups/trainplex/ls-pre-fork-cutover-20260516-000406/ls-data.tar.gz` `737434` bytes; `trainplex-postgres.sql` `15581024` bytes। |
| Incident log | ✅ | `/var/lib/trainplex-data/INCIDENT_LOG.md` में `WAVE 19 PRODUCTION CUTOVER` मौजूद है। |
| VPS repo cleanliness | ❌ | `/root/trainplex-studio` में `73` dirty/untracked entries हैं। |

Current migration drift output:

```text
Migrations for 'core':
  0008_rename_htx_qa_status_idx_htx_quality_status_94ec08_idx_and_more.py
    Rename quality alert indexes
Migrations for 'users':
  0016_rename_htx_audit_l_user_id_idx_htx_audit_l_user_id_2b6762_idx_and_more.py
    Rename audit log indexes
    Alter user city/language/pincode/state/tier fields
```

## C. External Access + Security

| Check | Result |
|---|---|
| Login URL | ✅ `HTTP/2 200` on `https://app.trainplex.in/label-studio/user/login/` |
| Health URL | ✅ `200`, `status=ok`, `db=ok` |
| `strict-transport-security` | ✅ Present: `max-age=31536000`; duplicate भी है। |
| `x-content-type-options` | ✅ Present: `nosniff`; duplicate भी है। |
| `x-frame-options` | ✅ Present: `SAMEORIGIN`। |
| `referrer-policy` | ✅ Present: `strict-origin-when-cross-origin`; duplicate भी है। |
| `permissions-policy` | ✅ Present: `geolocation=(), microphone=(), camera=()`; duplicate भी है। |
| CSRF cookie | ❌ `csrftoken` में `Secure` नहीं है; `HttpOnly` भी नहीं। |
| Session cookie | ❌ `sessionid` में `HttpOnly` और `SameSite=Lax` हैं, पर `Secure` नहीं। |
| CORS | ❌ Malicious Origin पर भी `Access-Control-Allow-Origin: *` मिलता है। |
| Vinod curl login flow | ⚠️ इस read-only pass में execute नहीं किया। Login page/CSRF reachable है, लेकिन credentials POST नहीं किया गया। |
| `/api/projects` authenticated response | ⚠️ External cookie login से verify नहीं किया गया। API endpoints server-side authenticated checks से verify किए गए। |

Security conclusion: Step 12 header middleware enough wired है कि headers दिख रहे हैं, लेकिन deployment hardened नहीं है। Cookie `Secure`, CORS allowlist, और single-source header emission अभी जरूरी हैं।

## D. TrainPlex-Specific Endpoints

Method: safe server-side GET checks with Django authenticated users where possible. No wrong-password/login mutation was performed.

| Endpoint | Result | Shape/count evidence |
|---|---|---|
| `GET /api/v1/admin/dashboard/snapshot` | ⚠️ `200` | Shape present; `top_trainers=1`; अभी भी partly mock/empty। |
| `GET /api/v1/admin/templates/catalog` | ✅ `200` | `79 total`, `10 TrainPlex custom`, `69 native`। |
| `GET /api/v1/admin/audit/log` | ✅ `200` | Paginated shape; `total=0`। |
| `GET /api/v1/admin/heatmap/state-activity` | ❌ `200` but wrong data | `state_count=0`; plan expected 17 active states। |
| `GET /api/v1/admin/quality-alerts` | ✅ `200` | Paginated shape; `total=0`। |
| `GET /api/v1/admin/wa/templates` | ✅ `200` | `count=5`। |
| `GET /api/v1/admin/submissions/preview` | ✅ `200` | `submissions=10`। |
| `GET /api/v1/admin/reports/founder-weekly` | ✅ `200` | Report shape OK; real-data completeness proven नहीं। |
| `GET /api/v1/admin/search?q=Vinod` | ❌ `200` but empty | Search result empty for Vinod। |
| `GET /api/v1/health` | ✅ `200` | `status=ok`, `db=ok`। |
| `GET /api/v1/payments/wallet` as trainer | ✅ `200` | Balance/wallet shape OK। |
| `GET /api/v1/reviewer/queue` as reviewer | ⚠️ Not real-user verified | Production role distribution में reviewer user नहीं है। |

## E. Forbidden Behavior Checks

| Check | Result | Evidence |
|---|---|---|
| Trainer role hitting admin APIs | ✅ PASS | Trainer को `403` मिलता है; detail में `Required role: admin. Your role: trainer` आता है। |
| 6th wrong password rate-limit | ⚠️ Source-only | Code wiring में `LOGIN_RATE=5/15m` और Hindi message `Bahut sare requests - kuch der ruk ke try karein` है; live wrong-password test नहीं किया गया। |
| Founder mobile कहीं नहीं आना चाहिए | ⚠️ MITIGATED | VPS tracked repo grep `0`, production safe GET leaks `0`, VPS `.env` में `TRAINPLEX_FOUNDER_MOBILE_GUARD=<configured-guard>` (gitignored); local tracked repo में 45 exact hits थे जो Wave-19 W1-MOBILE पर env-var pattern में sanitized कर दिए गए हैं। |

Founder mobile note: कुछ local hits defensive regex/tests/docs हैं, लेकिन audit requirement strict थी कि founder personal mobile code/templates/logs/API responses में कहीं नहीं होना चाहिए। उस strict wording के हिसाब से local repo fail है।

## F. Database Integrity

| Check | Result |
|---|---|
| SQLite file size | ✅ `7,483,392` bytes, 4 MB से ज्यादा। |
| Base counts | ⚠️ `users=14`, `projects=8`, `tasks=660`; requested expectation से count drift है। |
| Foreign keys | ✅ `pragma foreign_key_check` ने `0` rows लौटाईं। |
| Required new tables | ✅ Agent check में audit/review/payment/quality/feature tables present मिले। |
| Required migrations | ✅ Requested migrations present हैं। |
| Model/schema drift | ❌ `makemigrations --check --dry-run` fail है। |

Database verdict: runtime data integrity अभी clean है, लेकिन schema governance clean नहीं है क्योंकि pending model migrations हैं।

## G. Test Coverage Check

| Metric | Result |
|---|---|
| Backend `find label_studio -name "test_*.py"` | ✅ Local `142`; VPS filesystem `143` because untracked `test_phase2_real_data.py` है। |
| Frontend `.test.ts/.test.tsx` | ✅ `90`। |
| Fake/TODO-only sweep | ⚠️ Broad fake-test pattern prove नहीं हुआ, लेकिन कई shipped features अभी mock/contract-only हैं। |
| CI value | ❌ Current tests ने migration drift, disabled deploy workflows, nginx config failure, unhealthy celery, या endpoint regressions नहीं रोके। |

## H. Rollback Readiness

| Check | Result |
|---|---|
| Backup path | ✅ `/var/backups/trainplex/ls-pre-fork-cutover-20260516-000406` exists। |
| Backup artifacts | ✅ `ls-data.tar.gz` `737434` bytes; `trainplex-postgres.sql` `15581024` bytes। |
| Old LS container | ⚠️ `trainplex_label_studio_OLD_recovery` exists लेकिन running नहीं; boot/ports proven नहीं। |
| Rollback docs | ⚠️ `docs/ROLLBACK_PROCEDURE.md` exists, लेकिन docs/scripts current env से पूरी तरह match नहीं करते। |
| Script executability | ⚠️ `/root/trainplex-studio/backend/scripts/rollback_to_ls.sh` executable नहीं है (`-rw-r--r--`)। |
| Actual env mismatch | ❌ Rollback docs/scripts missing paths reference करते हैं, जैसे `/opt/labelstudio/docker-compose.yml` और missing route flag `/etc/nginx/conf.d/trainplex_upstream.flag`। |

Read-only rollback playbook, **execute नहीं किया गया**:

```bash
# 1. Backup और old recovery container confirm करें।
ls -lh /var/backups/trainplex/ls-pre-fork-cutover-20260516-000406/
docker ps -a --filter "name=trainplex_label_studio_OLD_recovery"

# 2. Founder confirmation के बाद ही fork-facing containers stop करें।
docker stop trainplex-studio-nginx-1 trainplex-studio-app-1 trainplex-studio-scheduler-1

# 3. Legacy recovery container और SSO bridge start करें।
docker start trainplex_label_studio_OLD_recovery
docker start trainplex_ls_sso

# 4. Host nginx को legacy route पर point करके validate/reload करें।
nginx -t && systemctl reload nginx

# 5. Legacy login route smoke-test करें।
curl -fI https://app.trainplex.in/label-studio/user/login/
```

Rollback verdict: जब तक old recovery container non-conflicting port पर boot-test नहीं होता और rollback docs actual VPS paths से match नहीं करते, rollback production-ready नहीं है।

## I. Watchdog + Monitoring

| Check | Result |
|---|---|
| Watchdog log recency | ⚠️ `C:\TrainPlex\watchdog.log` last observed करीब 2026-05-16 10:53 IST; बाद में age करीब 15 minutes हो चुकी थी। |
| Fork containers detect करता है | ❌ नहीं। यह `trainplex-studio-dev` और `http://localhost:8090/health` monitor करता है, production नहीं। |
| Production external health | ✅ External health URL live है, लेकिन watchdog इसका proof source नहीं है। |
| STUCK alerts | ❌ `STUCK` count बढ़कर `220` हो गया। |
| Celery worker | ❌ `trainplex_celery_worker` `unhealthy`; health में `worker_alive=True`, `redis_alive=False`, failing streak बढ़ रहा है। |
| SSO bridge | ⚠️ `trainplex_ls_sso` running है; real healthcheck नहीं। |
| Container nginx | ❌ `trainplex-studio-nginx-1` के अंदर `nginx -T` fail है क्योंकि `/etc/nginx/resolv.conf` missing है; error-log permission warning भी है। |

Monitoring verdict: current monitoring production के लिए acceptable नहीं है, क्योंकि यह local/dev UP दिखा सकता है जबकि production/celery/rollback risks invisible रहते हैं।

## J. Deviations + Risks Report

### 🔴 CRITICAL - ज्यादा users onboard करने से पहले fix करें

1. **Migration drift exists:** `makemigrations --check --dry-run` `core.0008` और `users.0016` pending दिखाता है।
2. **Production repo dirty है:** VPS में `73` dirty/untracked entries हैं; deployed state clean/reproducible commit नहीं है।
3. **Rollback boot-proven नहीं:** `trainplex_label_studio_OLD_recovery` सिर्फ `Created` है, ports empty, logs empty।
4. **Rollback docs/scripts actual VPS से mismatch हैं:** `/opt/labelstudio/docker-compose.yml` missing, route flag missing, `.sh` executable नहीं।
5. **Celery worker unhealthy:** `trainplex_celery_worker` `redis_alive=False` report कर रहा है।
6. **Container nginx config test fail:** `/etc/nginx/resolv.conf` missing।
7. **Security hardening incomplete:** cookies में `Secure` नहीं, CORS wildcard, duplicate security headers।
8. **Reviewer production flow verified नहीं:** reviewer user मौजूद नहीं है।
9. **Heatmap और search expected behavior fail:** heatmap `0` states देता है, search `Vinod` empty है।
10. **CI/CD deploy gates disabled:** prod/staging deploy workflows disabled हैं और production smoke gate active नहीं है।

### 🟠 MAJOR - Phase 2 में address करें

1. Dashboard, reports, search, submissions preview, WA, Razorpay, और bulk assignment में mock/contract-only areas बचे हैं।
2. Step 3 decommission goal के बावजूद SSO bridge अभी भी running है।
3. Watchdog production stack और external URL की जगह local/dev monitor कर रहा है।
4. App/nginx/scheduler containers में Docker healthchecks नहीं हैं।
5. Data counts बदले हैं; audit baseline में `5 -> 8 projects` और `651 -> 660 tasks` का कारण document होना चाहिए।
6. Founder mobile strict rule local repo और VPS `.env` में अभी fail है।
7. Visual regression, Lighthouse, load test, DR drill, और rollback drill production-proven नहीं हैं।
8. Auto-email/report cron scheduling callable/docs-only है, scheduled proven नहीं।

### 🟡 MINOR - Nice to have

1. Workflow directories और production repo से `.bak.*` / backup files clean करें।
2. Deployment provenance add करें: image digest, git SHA, compose file hash, migration state, smoke-test timestamp।
3. Verification docs में "mock contract shipped" और "real data shipped" अलग-अलग लिखें।
4. Duplicate header source fix करें ताकि app/nginx दोनों same security headers emit न करें।
5. Reviewer queue test के लिए reviewer seed/admin action add करें।

## Current GO / NO-GO Decision

**Verdict: broad production rollout के लिए NO-GO।**  
Service internal/founder validation के लिए live enough है, लेकिन ज्यादा trainers onboard करने के लिए अभी safe नहीं है। Minimum fixes:

1. VPS dirty worktree को clean `develop` या release branch में commit/sync/redeploy करें।
2. Missing model migrations generate/apply करें या models align करें ताकि `makemigrations --check --dry-run` pass हो।
3. Celery worker Redis health fix करें।
4. Rollback recovery container boot-test करें और rollback docs/scripts actual VPS paths से align करें।
5. Cookie `Secure`, CORS allowlist, और duplicate headers fix करें।
6. Heatmap state count और search results fix करें।
7. कम-से-कम एक reviewer user create/verify करके reviewer queue smoke test करें।
8. Watchdog/monitoring को production containers और external health URLs पर point करें।

## Hindi 3-line Recap for Founder

**बना:** Fork अब live है, login/health चल रहा है, Vinod admin सही है, और 10 TrainPlex templates production API में आ गए हैं।  
**काम:** Admin APIs, wallet, reports, templates और RBAC का base useful है, लेकिन अभी limited/internal validation के लिए ही safe है।  
**Risks:** Migration drift, dirty deploy repo, rollback unproven, celery unhealthy, heatmap/search fail, cookies/CORS security और monitoring अभी fix करना जरूरी है।
