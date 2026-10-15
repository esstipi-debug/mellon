# MEETING-KILLER OS — verificación de plataforma

**Consultado el 2026-10-14** (el brief decía 2025; se leyó todo hoy).

## 1. Google Calendar API — push

- **`events.watch` sigue vigente** (también Acl, CalendarList, Settings). [Push notifications](https://developers.google.com/workspace/calendar/api/guides/push)
- **Expiración:** la más restrictiva entre tu `expiration` y el límite interno; el valor real llega en la respuesta del `watch` y en `X-Goog-Channel-Expiration`. **Sin renovación automática**: hay que re-llamar `watch` con un `id` nuevo (con solapamiento). **Máximo numérico: NO CONFIRMADO** (no publicado; en la práctica, días).
- **Límite de canales por usuario: NO CONFIRMADO.** No hay tope documentado. Cuotas publicadas: 10.000 req/min por proyecto, 600 req/min por usuario, y umbral de facturación de 1.000.000 req/día. [Usage limits](https://developers.google.com/workspace/calendar/api/guides/quota)
- **`syncToken`: sí existe.** `nextSyncToken` → incremental con `syncToken`; si el servidor lo invalida responde **410 GONE** → borrar store y full sync. [Sync](https://developers.google.com/workspace/calendar/api/guides/sync)
- **Push al crear un evento: sí**, con `X-Goog-Resource-State: exists` (también modificaciones y borrados). **Pero el POST no lleva body**: es un ping sin datos; hay que resolver con sync incremental. **No distingue** created/updated/deleted.
- **Coste 2026:** superar el umbral diario **pasará a facturarse** ("later in 2026").

## 2. Add-ons de Google Calendar

Triggers reales hoy: **`calendar.homepageTrigger`**, **`calendar.eventOpenTrigger`**, **`calendar.eventUpdateTrigger`**, **`calendar.eventAttachmentTrigger`**, más conferencing solutions. [Interfaces](https://developers.google.com/workspace/add-ons/calendar/building-calendar-interfaces) · [Triggers](https://developers.google.com/workspace/add-ons/concepts/workspace-triggers)

- **No existe trigger de composición** (nada tipo `eventComposeTrigger`): **imposible interceptar al organizador mientras arma la invitación.** `eventOpenTrigger` corre al **abrir** un evento ya existente.
- `eventUpdateTrigger` corre **antes de guardar**, pero solo dispara si se añaden asistentes, se quitan asistentes, o se añade/cambia la solución de conferencia.
- **Modificar el evento: sí, limitado.** Solo vía `CalendarEventActionResponse`: `addAttendees()`, `setConferenceData()`, `addAttachments()`, con `currentEventAccess = WRITE|READ_WRITE` y scope `calendar.addons.current.event.write`. **No hay edición arbitraria de campos** y **no se persiste hasta que el usuario guarda**. [Calendar actions](https://developers.google.com/workspace/add-ons/calendar/calendar-actions). Sin soporte en móvil.

## 3. Microsoft Graph + add-in de Outlook

- **Suscripción `/users/{id}/events`: máximo 10.080 min (<7 días)**; con **rich notifications baja a 1.440 min (<1 día)**; mínimo 45 min. **1.000 suscripciones activas por buzón** (todas las apps). **Latencia de `event`: "Unknown"** en la tabla oficial (sin SLA de entrega). [subscription](https://learn.microsoft.com/en-us/graph/api/resources/subscription?view=graph-rest-1.0) · [overview](https://learn.microsoft.com/en-us/graph/change-notifications-overview)
- **Lifecycle notifications: 3 tipos** — `reauthorizationRequired` (todos los recursos), `subscriptionRemoved` y `missed` (Outlook message/event/contact). **Obligan a:** endpoint `lifecycleNotificationUrl` (**no se puede añadir a una suscripción existente**: hay que recrearla), responder `202` inmediato, reautorizar con `POST /subscriptions/{id}/reauthorize` o `PATCH` con nuevo `expirationDateTime` (no ambas en 10 min) y **resincronizar con delta query** (en los huecos no llega nada). [lifecycle](https://learn.microsoft.com/en-us/graph/change-notifications-lifecycle-events)
- **Rich notifications: sí**, para Outlook `event` en `/users/{id}/events`, con datos del recurso cifrados. Requieren `includeResourceData`, certificado RSA 2048–4096, **`$select` obligatorio** y validar `validationTokens` (`azp = 0bf30f3b-4a52-48df-9a82-234910c4a086`). [rich notifications](https://learn.microsoft.com/en-us/graph/change-notifications-with-resource-data)
- **Add-in Outlook — nombre exacto: `OnNewAppointmentOrganizer`** (manifest unificado `newAppointmentOrganizerCreated`), **requirement set Mailbox 1.10**, y **solo al crear** (no al editar). Para crear **y** editar: **`OnAppointmentOrganizer`** (1.12, `appointmentOrganizerOpened`). Al enviar: `OnAppointmentSend` (1.12, Smart Alerts).
- **Límite duro:** en activación por eventos **`displayDialogAsync` y `messageParent` están bloqueados** → **no se puede mostrar un diálogo**; solo infobar y mutar el item (asunto, asistentes). Exige despliegue por **admin del tenant**, timeout ~300 s, máximo 5 add-ins event-based activos. [autolaunch](https://learn.microsoft.com/en-us/office/dev/add-ins/outlook/autolaunch)

## 4. NotebookLM — audio de 2 locutores

**Sí existe API** (la premisa "no hay API pública" es incorrecta). Dos rutas:

- **Audio Overview**: `projects.locations.notebooks.audioOverviews.create` (Discovery Engine, `v1alpha`); **1 por notebook**; `sourceIds[]`, `episodeFocus`, `languageCode`. Requiere Gemini Notebook Enterprise = **licencia por usuario** + IdP corporativo (Cloud Identity o Workforce Identity Federation). [API](https://docs.cloud.google.com/gemini/enterprise/notebooklm-enterprise/docs/api-audio-overview?hl=es) · [setup](https://docs.cloud.google.com/gemini/enterprise/notebooklm-enterprise/docs/set-up-notebooklm)
- **Mejor opción: Podcast API standalone** (`projects.locations.podcasts`). **No requiere notebook, ni licencia de Gemini Enterprise, ni data store**: solo proyecto GCP + Discovery Engine API + rol `roles/discoveryengine.podcastApiUser`. Entrada `contexts` (texto/imagen/audio/video, **<100.000 tokens**); salida **MP3**; `length` = `SHORT` (4–5 min) / `STANDARD` (~10 min); `languageCode` BCP47 (español OK). **No cumple CMEK.** [Podcast API](https://docs.cloud.google.com/gemini/enterprise/notebooklm-enterprise/docs/podcast-api)
- **NO CONFIRMADO:** el número exacto de voces del audio overview (la doc no lo especifica).

## 5. TTS multi-locutor (PAYG, consultado hoy)

| Proveedor | Multi-hablante nativo | Precio | Fuente |
|---|---|---|---|
| **ElevenLabs** | **Sí:** `POST /v1/text-to-dialogue` (`inputs[]` con `voice_id` por turno), modelos v3/v4; ≤10 voces y ≤2.000 car./request. Multilingual v2/Turbo **no** | **0,08 USD/1.000 car.** (v3/v4), 0,04 (Flash/Turbo) ≈ **0,08 USD/min** | [pricing](https://elevenlabs.io/pricing/api) · [API](https://elevenlabs.io/docs/api-reference/text-to-dialogue/convert) |
| **Google Gemini TTS** | **Sí:** `speech_config.speakers` + etiqueta `speaker` por turno; **2 voces máx.** con voces prebuilt; es-ES/es-US OK | Gemini 2.5 Flash TTS 10 USD/1M tokens de audio (25 tok = 1 s) ≈ **0,11 USD/episodio de 7 min** | [Gemini](https://ai.google.dev/gemini-api/docs/speech-generation) · [Cloud](https://cloud.google.com/text-to-speech/pricing) |
| **Azure AI Speech** | **Sí** por SSML multi-`<voice>`; diálogo nativo `MultiTalker` solo en inglés (preview) | Neural 15 USD/1M car.; HD 22 USD/1M | [precios](https://azure.microsoft.com/en-us/pricing/details/speech/) |
| **PlayHT / Play.ai** | Sí (`PlayDialog`: `voice`+`voice_2`) | **NO CONFIRMADO** (dominios caídos; producto discontinuado tras la compra por Meta) → **descartar** | [docs](https://docs.play.ht/reference/models) |
| **OpenAI TTS** | **No:** un solo `voice` por request → trocear y unir | tts-1 15 USD/1M car.; gpt-4o-mini-tts 12 USD/1M tokens de audio | [pricing](https://developers.openai.com/api/docs/pricing) |
| **Cartesia** | **No:** un `voice` por request | ≈37–50 USD/1M car. vía créditos | [pricing](https://cartesia.ai/pricing) |

- **Chirp 3: HD de Google Cloud no soporta multi-locutor**: `multiSpeakerMarkup` funciona solo con la voz `en-US-Studio-MultiSpeaker` (sin español). Gemini TTS es la vía multi-voz de Google.
- **Calidad (referencia externa):** ElevenLabs v4 Turbo nº1 del leaderboard de Artificial Analysis (Elo 1328); Gemini 3.8 Flash TTS 1273.
- **Recomendación:** para episodios de 5–10 min y bajo volumen, **Gemini TTS multi-voz** (~0,11 USD/episodio en una sola request, español nativo). Si el realismo máximo es requisito, **ElevenLabs Text to Dialogue** (~0,56 USD/episodio troceando a ≤2.000 caracteres).

## 6. Remotion

- **Sigue siendo el estándar** para video programático en React: [repo](https://github.com/remotion-dev/remotion) ~64k ⭐, npm ~8,4 M descargas/mes, release ~semanal (v4.0.535).
- **Licencia:** gratis para individuos, **empresas de ≤3 personas** y non-profits; **Company License (4+) = 25 USD/asiento/mes** (Creators) o **0,01 USD/render con mínimo 100 USD/mes** (Automators); Enterprise desde **500 USD/mes**. **No es open source OSI.** [pricing](https://www.remotion.dev/docs/license/pricing) · [FAQ](https://www.remotion.dev/docs/license/faq)
- **Remotion Lambda: Remotion no cobra por render.** Pagas **solo AWS**: ≈**0,017–0,021 USD por minuto** de video y 0,103–0,108 USD por 10 min HD, **más** la Company License si sois 4+. [cost example](https://www.remotion.dev/docs/lambda/cost-example)
- **Alternativas:** [Shotstack](https://shotstack.io/pricing/) (API cloud, 10 USD/50 min), [Revideo](https://github.com/midrender/revideo) y [Motion Canvas](https://github.com/motion-canvas/motion-canvas) (MIT), [Hyperframes](https://github.com/heygen-com/hyperframes) (Apache 2.0), [Creatomate](https://creatomate.com/pricing) (USD **NO CONFIRMADO**), FFmpeg.

## 7. Orquestación durable

| Opción | Estado | Precio de entrada | Cuándo usarlo |
|---|---|---|---|
| [Temporal Cloud](https://temporal.io/pricing) | Activo | **50 USD/M acciones** (25 USD/M por volumen); 150 USD créditos | Durabilidad fuerte; tolerás operar o pagar SaaS |
| Temporal OSS | Activo | **MIT**, self-host gratis | Querés control total del clúster |
| [Inngest](https://www.inngest.com/pricing) | Activo | Free (50k ejecuciones); **Pro 99 USD/mes** (1M) | Durable por pasos + cron sin infra |
| [pg-boss](https://github.com/timgit/pg-boss) | Activo | **MIT, 0 USD** | Ya tenés Postgres: cron, reintentos, DLQ |
| [Graphile Worker](https://worker.graphile.org/docs/cron) | Activo | **MIT, 0 USD** | Cola Postgres minimalista, SQL-first |
| [Hatchet](https://hatchet.run/pricing) | Activo | MIT + self-host; 30 USD/M runs | Querés UI y durable multi-paso sobre Postgres |

**Recomendación:** **pg-boss** (Postgres puro, MIT, RRULE + reintentos + DLQ, TS nativo; riesgo: mantenedor único). Si necesitás UI/estado multi-paso: **Hatchet self-hosted**. **Temporal** solo si la durabilidad es el core del producto.

## 8. Cumplimiento (focus time / monitorización)

1. **Alemania — § 87 BetrVG**: la introducción de dispositivos técnicos de vigilancia del rendimiento es **co-determinada** por el Betriebsrat. [texto](https://www.gesetze-im-internet.de/betrvg/__87.html) → Sin *Betriebsvereinbarung* previa no se despliega en Alemania.
2. **España — AEPD**: [FAQ laboral](https://www.aepd.es/preguntas-frecuentes/3-proteccion-de-datos-en-el-ambito-laboral) + resolución [PS-00454-2024](https://www.aepd.es/documento/ps-00454-2024.pdf) (200.000 € por monitorizar con apps en móviles personales; arts. 5.1.c, 6.1 y 13 RGPD) → Minimización estricta, información granular y nunca apps en dispositivos personales.
3. **UE — art. 88 RGPD + STJUE C-34/21** ([ECLI:EU:C:2023:270](https://eur-lex.europa.eu/legal-content/ES/TXT/?uri=CELEX:62021CJ0034)): ni convenio ni consentimiento sustituyen la base del art. 6 ni las garantías del art. 88(2).

**Conclusión:** medir "focus time" por persona es monitorización laboral de alto riesgo; el diseño defendible son **métricas agregadas por equipo** + evaluación de impacto + co-determinación en Alemania.
