Los 14 criticos son 7 decisiones. Cuatro huecos distintos empujan lo mismo por cuatro puertas: (a) `save()` es un `write_text` desnudo, asi que toda regla nueva que se escriba en un `validate()` es codigo muerto en el unico camino que la necesita (1, 7, 10, 12); (b) no existe UNA definicion de "reunion" ni de "decision medible", asi que cada hueco agrega su propio filtro ad-hoc en `volume_gate`, `circular_minutes` y `touches_to_decide`, en direcciones que se pisan (5, 6, 8, 9, 13, 14); (c) las politicas de canal y de techo se hacen cumplir en el CLI, que es la capa que cualquier ruta nueva esquiva sin querer (4, 11, 14); (d) el estado de captura se ESCRIBE por quien toco un archivo en vez de DERIVARSE de los hechos, y por eso el unico camino que existe para escribirlo es el que no puede (1, 2, 3). La fundacion no agrega ningun modulo nuevo ni ninguna octava entidad: `MeetingProfile` y `Corpus` son tablas/derivados congelados del mismo genero que `HEDGES` y `Coverage`, que ya existen y no cuentan. `seed.py` y `chat.py` se construyen DESPUES, encima de esto, y ahi si son modulos.

DECISIONES ESTRUCTURALES:
  * D1 — Un solo portal de escritura por store, y valida contra el DISCO, no contra el vacio: `DecideStore.save(obj, force=False) -> list[str]` valida siempre. Pero no valida contra la nada: calcula los issues del objeto que se va a escribir y los issues que el ARCHIVO YA TENIA, y solo rechaza la diferencia. Los issues heredados se toleran y se DEVUELVEN para que el llamador los imprima. Regla: una escritura no puede EMPEORAR el registro; puede dejarlo igual de roto que estaba, diciendolo. `_check_roster` (que despacha por string y revienta con TypeError ante un typo) se reemplaza por `_issues(obj)` con despacho por tipo. Twin del lado de lectura: `_load_kind`/`meetings()` degradan por archivo y publican `store.ilegibles()`, porque un campo nuevo vuelve ilegible cada .md para el codigo viejo y un solo archivo no puede tumbar `agenda()`, `tick()` y toda la fase 4. Lo mismo en `AliasStore`: `add()` es el portal y valida, `save_all` pasa a `_save_all` privado.
      porque: Es la decision que hace que TODAS las demas reglas nuevas existan. Hoy los unicos call sites de `.validate()` son `add_meeting`, `_check_roster` y `add_assumption`; `supersede`, `safe_close` y `tick` escriben por `save()` sin validar nada. Cualquier regla que se agregue a `Decision.validate` para CONFLICTO, para `origen` o para el enum de captura es codigo muerto: el unico camino que la crea es el unico que nunca pasa por el validador. Y la variante 'contra el disco' es la que resuelve la tension real: si `save()` validara contra el vacio, escribir la falla de captura sobre una Meeting persistida con `--force` (sin facilitador, sin retencion) seria imposible — H6 reproducido adentro de la solucion de H6. 'No empeorar' deja pasar el heredado y bloquea el nuevo, que es exactamente la semantica que hace falta.
      cierra: 1, 7, 10, 12
  * D2 — Un solo Corpus: la pregunta transversal contestada una vez, con dos predicados y sus exclusiones publicadas: Dos predicados puros en `schema.py` y un join en `store.py`.

  `Meeting.es_serie_de_decision  ==  canal == "SINCRONICO" and profile_of(clase).promotion_budget > 0`
  `Decision.auditable            ==  origen == "REUNION" and bool(meeting_id)`
  y el join, que necesita los dos: `d.auditable and meetings[d.meeting_id].es_serie_de_decision`

Vive en `store.corpus(store) -> Corpus`, porque el store es el unico que tiene el corpus entero, y `eventlog` y `metrics` ya lo importan (metrics importa eventlog, no al reves). `Corpus` trae `meetings`, `decisions`, `meetings_fuera: dict[motivo, ids]`, `decisions_fuera: dict[motivo, ids]` y un `nota()` que se publica AL LADO del numero. Una exclusion silenciosa es la misma mentira que un hueco.

Lo que queda AFUERA de 'reunion': ventana de chat (ASINCRONICO), daily (HANDOVER, techo 0). Lo que queda ADENTRO: la sesion de siembra (KICKOFF, techo 7 — la sesion ocurrio de verdad) y la sesion SIN_AUDIO (la sesion ocurrio; lo que fallo es la captura). Lo que queda afuera de 'decision medible': sembradas, actas historicas, decisiones de pasillo (`meeting_id=""`), y todo lo colgado de una reunion que no es reunion.

Separacion precisa: **canal y clase deciden que es una reunion; la captura decide que es medible en minutos.** `es_serie_de_decision` NO mira `falla_captura`; `circular_minutes` si.
      porque: Sin esto, cada hueco agrega su propio filtro: H5 quiere excluir ASINCRONICO de tres funciones, H4 quiere excluir `origen != REUNION` de dos, H7 quiere un campo `cuenta_minutos_circulares` en el perfil. Son tres reglas para una sola pregunta, escritas en cinco lugares, que se desincronizan el primer dia. Ademas colapsa un campo entero del perfil de H7: `cuenta_minutos_circulares` NO se declara, se DERIVA de `promotion_budget > 0` — que es lo unico que significaba. Y `auditable` exigiendo `meeting_id` no truthy es lo que impide que la decision de pasillo (ruta legitima y documentada en `roster_of`) afirme que salio de una sesion con roster y consentimiento.
      cierra: 6, 8, 9, 13, 14
  * D3 — El event log NO pierde filas: gana una columna. Las metricas de CONTROL filtran; las DESCRIPTIVAS no: `build_event_log(store, c: Corpus | None = None)` agrega la columna booleana `en_serie` (= el `resource` de esa fila es una reunion del corpus) y no borra ni una fila. `touches_to_decide(store, c=None)` aplica DOS filtros que salen del MISMO Corpus:

  - filtro de CASO: `cid in c.decision_ids` — saca la decision entera de la serie.
  - filtro de TOQUE: `previas["en_serie"]` — saca la fila de un daily del conteo de un caso que SI pertenece.

Y la regla de composicion que impide que los dos peleen: **un caso entra a la serie solo si su PROPIA reunion esta en el corpus; una vez adentro, solo cuentan los toques de reuniones del corpus.** `touches_excluidas(store, c=None) -> dict` reporta cuantos casos y cuantos toques se saltearon, y `touches_xmr` los publica.
      porque: Es la interaccion que pedis mirar. El arreglo de #5 quiere SACAR FILAS de un caso que se queda; el de #8/#9 advierte que sacar solo recursos deja a la decision de chat adentro con `toques=1` sistematico —el piso de la escala— porque `_mk_question` nunca llena `blocks`, y eso hunde `mr_bar` y congela los limites en 1,83/4,73 en vez de 2,83/9,36. Los dos son proyecciones del mismo test de pertenencia a dos granularidades distintas, y componen porque un caso que pertenece tiene por construccion al menos su propia reunion (el `+1`): ningun filtro puede deflacionarlo a 1. Y la columna en vez del borrado importa: si `build_event_log` perdiera filas, `lifecycle_rework` sub-reportaria el reproceso (un daily donde el tema volvio OCURRIO) y `circular_minutes` cambiaria de significado el set `con_avance`. Un log de eventos al que se le sacan eventos es exactamente la mentira silenciosa que la regla 3 prohibe.
      cierra: 5, 8, 9
  * D4 — Un solo techo, una sola funcion: el perfil solo BAJA el 7; el origen abre un carril PARALELO: `promotion_ceiling(clase: str, origen: str) -> int` es el unico techo del sistema. Para `origen == "REUNION"` devuelve `min(profile_of(clase).promotion_budget, MAX_PROMOTIONS_PER_MEETING)`; para los origenes declarados devuelve `DECLARED_BUDGET[origen]`. `_check_budget_ceiling()` corre al importar `store.py`, al lado del comentario de la regla 7, y falla el import si algun perfil declara un techo mayor a 7. `add_decision` cuenta por `(meeting_id, origen)`, asi que 30 sembradas no consumen los 7 de la sesion de siembra y los 7 de una reunion normal siguen siendo 7. `MAX_PROMOTIONS_PER_MEETING` conserva nombre, valor y su lugar en `__all__`.
      porque: H4 quiere `PROMOTION_BUDGET` por origen y H7 quiere `promotion_budget` por clase: son dos techos que se pisan sobre la misma linea de `add_decision`, y con dos numeros la regla 7 deja de ser demostrable. Con una funcion y una asercion de import, 'el 7 no sube' es una propiedad que un test fija en una linea. Ademas nombra la evasion que el techo por clase abre sola: `add_decision` aplica el presupuesto dentro de `if decision.meeting_id:` — borrar `--meeting` saltea cualquier techo sin flag y sin rastro. El techo no lo puede cerrar; lo cierra D2, contando y publicando `decisiones_sin_reunion`.
      cierra: 14
  * D5 — `estado_captura` no se escribe: se DERIVA. Solo se persiste la falla observada: Se persiste unicamente lo que nadie puede recomputar despues: `Meeting.falla_captura: str = ""` (uno de `CAPTURE_FALLA`) y `motivo_captura: str = ""`. Todo el resto es una funcion PURA en `schema.py`:

  `capture_state(meeting, n_decisiones, n_en_cola, hay_transcripto) -> tuple[str, str]`

con precedencia de mas especifica a mas generica: falla declarada > COLA_NO_REVISADA > CAPTURADA (hay decisiones) > SIN_RITUAL (hubo transcripto y no salio nada) > NO_REGISTRADA (ausencia de dato). `metrics.capture_report(store)` la arma leyendo el store, el `DraftStore` y el `TranscriptStore`.

Se eliminan del diseno de H6: el modulo `capture.py`, `set_capture`, `estado_tras_borradores`, `asr_gate` y `Meeting.mediana_confianza_asr` (no existe ningun productor de confianza de ASR en ninguna capa; un campo sin escritor es peso muerto que despues nadie borra). `ASR_DEGRADADO` pasa a ser una falla que un humano declara o que `cmd_transcribe` registra cuando Whisper levanta.
      porque: El sintoma #2 —el flujo canonico de fase 2 nunca escribe CAPTURADA— y el arreglo propuesto —que lo escriba `cmd_review`— son la misma enfermedad: hacer que la salud dependa de que alguien corra un comando. El propio argumento de H6 ('nadie corre `review`, por lo tanto no puede ser event-driven') aplica identico un paso antes. Derivandolo, CAPTURADA significa lo que tiene que significar (hay decisiones registradas para esta sesion, un hecho del canal DECIDIDA) en vez de lo que significaba (alguien transcribio, un hecho del canal HABLADA), y SIN_RITUAL con decisiones registradas se vuelve IMPOSIBLE POR CONSTRUCCION en vez de una asercion falsa. Y sin `set_capture` no hay ninguna escritura nueva sobre `Meeting` que pueda chocar con una Meeting invalida en disco.
      cierra: 1, 2, 3
  * D6 — El perfil declara solo lo no derivable, y cada campo se hace cumplir en el modulo DUENO DEL RECURSO, nunca en el CLI: `MeetingProfile` frozen con CINCO campos, cada uno con un lector unico y nombrado: `promotion_budget` (lo lee `promotion_ceiling`), `gate_binding` (`query._gate`), `audio_allowed` (`schema.hablada_permitida`), `requires_facilitator` (`Meeting.validate`), `cancelable` (`Agenda.verdict`). `cuenta_minutos_circulares` NO existe: se deriva (D2).

La politica de habla verbatim vive en UNA funcion pura, `schema.hablada_permitida(meeting, *, con_audio=False) -> list[str]`, y la consultan las DOS unicas puertas que persisten habla textual: `TranscriptStore.write()` (por la que pasan `ingest_text`, `ingest_segments` y `transcribe_meeting`) y `DraftStore.append()` (que persiste el `utterance` literal). `con_audio=True` solo lo pasa `transcribe_meeting`, que es el unico que leyo un archivo de audio; ahi se chequean consentimiento y retencion. Si `meeting` es None pero el .md EXISTE en el root, `write()` lo lee igual: la politica no se esquiva omitiendo un argumento.

El chequeo de `cmd_transcribe` (cli.py:248) se borra: quedo cubierto mas abajo.
      porque: El campo del perfil dice literalmente 'si la clase admite canal HABLADA' y hoy no gobierna el canal HABLADA: gobierna una rama del CLI. `transcribe --text notas.txt` sobre un 1:1 de desempeno escribe `hablada/<meeting>.jsonl`, `cmd_review` congela citas literales adentro de las decisiones, y el contenido sobre terceros queda versionado en git con fecha y autor, sin un aviso. La regla general: una politica escrita en el CLI la esquiva cualquier ruta nueva sin querer, y las cuatro puertas nuevas de los cuatro huecos son exactamente rutas nuevas.
      cierra: 4, 6
  * D7 — Solo un hecho con dueno y fecha justifica una reunion. Ningun default afirma nada: Dos invariantes con test propio.

(a) `Agenda.is_empty` se calcula SOLO sobre hechos con dueno y fecha: compromisos vencidos, supuestos caidos, preguntas abiertas, reaperturas, preguntas expiradas (y, cuando exista, conflictos). Todo diagnostico DERIVADO —solapamientos sin enlazar, sesiones sin captura, alias en disputa— va a `advisories`, que se imprime y no toca `is_empty`. `Agenda.cancelable` sale del perfil: cuando es False el veredicto es 'sin temas: la sesion corre igual por su clase', nunca 'reunion justificada'. Y el encabezado '## Preguntas abiertas que pasan el gate' pasa a '## Preguntas abiertas' con una columna `gate` (paso / suspendido por clase): una fila, un estado escrito al lado, nunca la misma pregunta en dos tablas que se contradicen.

(b) Todo campo nuevo con default tiene que leerse como AUSENCIA DE DATO y jamas como evidencia: `falla_captura=""` es 'no se registro ninguna falla', no 'todo bien' ni 'fallo'; `scope=""` NO CRUZA con nada (ya es cierto en `_scope_proximity` y `cubre_scope`; hay que preservarlo en `unlinked_overlaps`); `canal="SINCRONICO"` y `clase="COMITE"` son verdaderos para todo lo persistido y COMITE es el perfil mas estricto; `origen="REUNION"` es el unico que AFIRMA, y por eso `auditable` le exige ademas `meeting_id` (D2).
      porque: `agenda()` devolviendo vacio es la operacion de mayor retorno de todo el sistema. La degradacion del veredicto que proponia H6 la apagaba sobre TODO el corpus ya persistido por cruzar dos defaults —`scope=""` empareja todas las reuniones entre si y `NO_REGISTRADA` marca como fallidas las 15 ya en disco— sin que nada falle. La regla general es la barata: un diagnostico que el sistema derivo nunca puede convertirse en una razon para juntar a ocho personas.
      cierra: 3

CAMBIOS:
  - src/fdekit/decide/schema.py :: MEETING_CLASS / MEETING_CHANNEL / DECISION_ORIGIN / CAPTURE_FALLA / CAPTURE_DERIVADO
      MEETING_CLASS = ("COMITE", "UNO_A_UNO", "KICKOFF", "TERRENO", "HANDOVER", "INCIDENTE")
MEETING_CHANNEL = ("SINCRONICO", "ASINCRONICO")
DECISION_ORIGIN = ("REUNION", "SIEMBRA", "ACTA_HISTORICA")
CAPTURE_FALLA = ("SIN_AUDIO", "ASR_DEGRADADO", "CONSENTIMIENTO_DENEGADO")
CAPTURE_DERIVADO = ("NO_REGISTRADA", "CAPTURADA", "COLA_NO_REVISADA", "SIN_RITUAL")
      Cinco tuplas congeladas junto a las otras seis (linea 18-26). CAPTURE_FALLA es lo unico que toca disco; CAPTURE_DERIVADO se declara para que un error diga 'es derivado' en vez de 'estado invalido'. Sin enum, un typo cae al default en silencio — el mismo patron del meeting_id mal tipeado que apagaba la validacion de dueno.
  - src/fdekit/decide/schema.py :: MeetingProfile / MEETING_PROFILES / profile_of
      @dataclass(frozen=True)
class MeetingProfile:
    clase: str
    promotion_budget: int      # el perfil solo puede BAJAR el 7 (se verifica al importar store)
    gate_binding: bool
    audio_allowed: bool
    requires_facilitator: bool
    cancelable: bool
    nota: str = ""

MEETING_PROFILES: dict[str, MeetingProfile]

def profile_of(clase: str) -> MeetingProfile:  # KeyError si desconocida
      CINCO campos, no seis: `cuenta_minutos_circulares` se deriva de `promotion_budget > 0` (D2). Tabla: COMITE 7/True/True/True/True (unica cancelable, es el default y el mas estricto); UNO_A_UNO 7/True/False/False/False; KICKOFF 7/True/True/True/False; TERRENO 7/False/True/False/False; HANDOVER 0/False/True/False/False; INCIDENTE 7/False/True/True/False. No es una octava entidad: no se persiste, no tiene id ni validate, no pasa por DecideStore — mismo genero que HEDGES. `profile_of` LEVANTA ante clase desconocida, como `roster_of`; lo atrapa `cli._guarded`.
  - src/fdekit/decide/schema.py :: Meeting.clase / canal / falla_captura / motivo_captura / profile / es_serie_de_decision
          clase: str = "COMITE"
    canal: str = "SINCRONICO"
    falla_captura: str = ""      # "" = no se registro ninguna falla. NO significa "todo bien".
    motivo_captura: str = ""

    @property
    def profile(self) -> MeetingProfile: ...

    @property
    def es_serie_de_decision(self) -> bool:
        """La UNICA definicion de 'reunion' de la fase 4."""
        return self.canal == "SINCRONICO" and self.profile.promotion_budget > 0
      Cuatro campos, todos al final y con default, todos strings planos: `_to_fm` los recorre con el loop generico y no aplica la trampa de las tuplas hardcodeadas de Anchor/Consent, ni hay que tocar `_DATE_FIELDS`. `es_serie_de_decision` deliberadamente NO mira `falla_captura`: la sesion ocurrio; lo que fallo es la captura, y eso lo consume `circular_minutes`, no `volume_gate`.
  - src/fdekit/decide/schema.py :: Meeting.validate
      def validate(self) -> list[str]:  # +4 issues
      Issues nuevos: `clase not in MEETING_CLASS`; `canal not in MEETING_CHANNEL`; `falla_captura` fuera de CAPTURE_FALLA (con mensaje especifico si es uno de CAPTURE_DERIVADO: 'ese estado se deriva, no se escribe'); `falla_captura` puesto sin `motivo_captura` (regla 1: lo no cuantificado va a cola explicita con dueno). Y el chequeo de facilitador pasa a `if self.profile.requires_facilitator and not self.facilitator`. Ningun issue nuevo aplica al corpus persistido: los defaults son todos validos.
  - src/fdekit/decide/schema.py :: Decision.origen / Decision.auditable
          origen: str = "REUNION"

    @property
    def auditable(self) -> bool:
        """Existe una sesion registrada donde esto se decidio. NO dice que haya
        cita de audio (eso es anchor.empty)."""
        return self.origen == "REUNION" and bool(self.meeting_id)
      Campo AL FINAL (despues de `anchor`) para no correr ningun argumento posicional de las ~10 fabricas de tests. `Decision.validate` suma `origen not in DECISION_ORIGIN`. `auditable` es derivado y NUNCA se persiste. El `and bool(meeting_id)` es el critico 14: la decision de pasillo es una ruta legitima y documentada, y sin ese conjunto `why()` publicaria `auditable: true` sobre algo que no tuvo roster ni Consent.
  - src/fdekit/decide/schema.py :: capture_state
      def capture_state(meeting: Meeting, n_decisiones: int, n_en_cola: int,
                  hay_transcripto: bool) -> tuple[str, str]:
    """(estado, motivo). PURA: no toca disco, no lee el reloj, no escribe.

    1. falla declarada -> (meeting.falla_captura, meeting.motivo_captura)
    2. n_en_cola > 0   -> COLA_NO_REVISADA
    3. n_decisiones>0  -> CAPTURADA        (hecho del canal DECIDIDA)
    4. hay_transcripto -> SIN_RITUAL       (se hablo y no salio nada)
    5. si no           -> NO_REGISTRADA    (ausencia de dato, no falla)
    """
      El corazon de D5. La precedencia hace IMPOSIBLE por construccion que una sesion con decisiones registradas salga SIN_RITUAL —hoy `estado_tras_borradores(actual, 0)` lo afirmaba sobre una sesion con 5 decisiones a mano— y hace que CAPTURADA signifique lo que dice. Pura y en schema porque `cli` no puede arrastrar numpy ni pandas al notebook prestado (regla 2).
  - src/fdekit/decide/schema.py :: hablada_permitida
      def hablada_permitida(meeting: Meeting, *, con_audio: bool = False) -> list[str]:
    """Issues que impiden persistir habla verbatim de esta reunion. La consultan
    las DOS puertas que la escriben: TranscriptStore.write y DraftStore.append."""
      Sin audio: rechaza si `profile.audio_allowed is False` (cubre `--text` y `cmd_draft`, que es donde hoy se escapa). Con audio: ademas exige `consent.recording_allowed` y `retention_days is not None`. Como COMITE tiene `audio_allowed=True`, el flujo canonico (registrar reunion sin `--recording`, `transcribe --text`, `draft`, `review`) sigue funcionando identico: cero tests rotos.
  - src/fdekit/decide/store.py :: DecideStore.save
      def save(self, obj, force: bool = False) -> list[str]:
    """Portal unico de reescritura. Valida contra lo que YA HAY EN DISCO: rechaza
    los issues NUEVOS y tolera —devolviendolos— los que el archivo ya tenia.
    Lista vacia = quedo limpio. Levanta ValidationError solo ante una regresion."""
      El corazon de D1. Implementacion: `nuevas = self._issues(obj)`; si vacia o `force`, escribe. Si no, `previas = self._issues_en_disco(obj)` (lista vacia si el archivo no existe, asi que un objeto nuevo se valida completo); `regresion = [i for i in nuevas if i not in previas]`; si hay regresion levanta, si no escribe y devuelve `nuevas`. Cuesta una lectura de archivo por escritura, sobre cientos de archivos.
  - src/fdekit/decide/store.py :: DecideStore._issues / _issues_en_disco
      def _issues(self, obj) -> list[str]: ...        # despacho por TIPO, no por string
def _issues_en_disco(self, obj) -> list[str]: ...
      Reemplaza a `_check_roster(obj, meeting_id, force, kind)`, que despacha con `kind != "Assumption"` y manda un roster a `Assumption.validate()` (que no lo acepta) ante un typo en el string, produciendo TypeError en vez de ValidationError. `_issues` hace `isinstance`: Assumption y Meeting -> `validate()`; el resto -> `validate(self.roster_of(obj.meeting_id))`.
  - src/fdekit/decide/store.py :: DecideStore._load_kind / meetings / ilegibles
      def ilegibles(self) -> dict[str, str]:  # ruta -> motivo, de la ultima lectura
      Lectura degradada POR ARCHIVO: un .md escrito por una version mas nueva levanta `ValidationError('campos desconocidos')` y hoy tumba `store.decisions()` entero, y con el `agenda()`, `tick()`, `volume_gate`, `rebuild_index` y toda la fase 4. Con `origen`, `clase`, `canal` y `falla_captura` llegando a disco, esa forward-incompat pasa de teorica a garantizada. `meetings()` ademas filtra los .md que no parsean como Meeting, cerrando de paso que cualquier .md suelto en `meetings/` cuente para MIN_MEETINGS. Lo ilegible se NOMBRA en `volume_gate` y en `report()`, nunca se saltea callado.
  - src/fdekit/decide/store.py :: promotion_ceiling / DECLARED_BUDGET / _check_budget_ceiling
      MAX_PROMOTIONS_PER_MEETING = 7   # no se mueve, no se parametriza, no se sube
DECLARED_BUDGET = {"SIEMBRA": 30, "ACTA_HISTORICA": 30}

def promotion_ceiling(clase: str, origen: str) -> int: ...
def _check_budget_ceiling() -> None: ...   # corre al importar el modulo
      Un solo techo. REUNION -> `min(profile.promotion_budget, 7)`; declarado -> `DECLARED_BUDGET.get(origen, 7)`. `_check_budget_ceiling()` falla el import si algun perfil declara mas de 7: la regla 7 pasa de comentario a propiedad verificada. `MAX_PROMOTIONS_PER_MEETING` conserva nombre, valor y lugar en `__all__`.
  - src/fdekit/decide/store.py :: DecideStore.add_decision
      def add_decision(self, decision: Decision, force: bool = False) -> Decision:
      El conteo se filtra por `(meeting_id, origen)` y el tope sale de `promotion_ceiling(meeting.clase, decision.origen)`. Efecto: 30 sembradas no consumen los 7 de la sesion de siembra; los 7 de una reunion normal siguen siendo 7; un HANDOVER con techo 0 rechaza. El mensaje de `PromotionBudgetExceeded` nombra la clase, el origen, el techo aplicado y la salida legitima (llevarlo a la recurrente), nunca 'sacale el --meeting'.
  - src/fdekit/decide/store.py :: Corpus / corpus
      @dataclass(frozen=True)
class Corpus:
    meetings: tuple[Meeting, ...]
    decisions: tuple[Decision, ...]
    meetings_fuera: dict[str, tuple[str, ...]]    # motivo -> ids
    decisions_fuera: dict[str, tuple[str, ...]]
    @property
    def meeting_ids(self) -> frozenset[str]: ...
    @property
    def decision_ids(self) -> frozenset[str]: ...
    def nota(self) -> str: ...

def corpus(store: DecideStore) -> Corpus: ...
      La respuesta a la pregunta transversal, calculada una vez. Motivos como constantes de modulo publicables: FUERA_ASINCRONICO, FUERA_SIN_TECHO, FUERA_DECLARADA, FUERA_SIN_REUNION, FUERA_REUNION_NO_SERIE. `nota()` es la linea que se imprime AL LADO del numero. No es una octava entidad: es derivado, no se persiste, no tiene id — mismo genero que `Coverage`.
  - src/fdekit/decide/eventlog.py :: build_event_log
      def build_event_log(store: DecideStore, c: Corpus | None = None) -> EventLog:
      Agrega la columna booleana `en_serie` (= `row.resource in c.meeting_ids`) y NO borra ninguna fila. `EventLog.__init__` solo exige las columnas REQUIRED, asi que una columna extra es segura (verificado en processmining/log.py:19-27). `variants`, `rework_summary`, `bottlenecks` y `to_mermaid` siguen viendo todo: un daily donde el tema volvio a aparecer ocurrio de verdad y es reproceso real.
  - src/fdekit/decide/eventlog.py :: touches_to_decide / touches_excluidas
      def touches_to_decide(store: DecideStore, c: Corpus | None = None) -> pd.DataFrame: ...
def touches_excluidas(store: DecideStore, c: Corpus | None = None) -> dict: ...
      Los dos filtros de D3, del MISMO Corpus: caso (`cid in c.decision_ids`) y toque (`previas["en_serie"]`). `touches_excluidas` devuelve `{'casos': {motivo: n}, 'toques_fuera_de_serie': n}` para que la exclusion no sea otro silencio. `lifecycle_rework` NO filtra: su unidad declarada es la reunion extra, y ahi el daily cuenta.
  - src/fdekit/decide/metrics.py :: volume_gate
      def volume_gate(store: DecideStore, c: Corpus | None = None) -> dict:
      `decisiones = len(c.decisions)`, `reuniones = len(c.meetings)`, mas cuatro lineas nuevas publicadas siempre: `decisiones_declaradas`, `decisiones_sin_reunion`, `ventanas_asincronicas`, `archivos_ilegibles`. El veredicto las nombra cuando hay. Es la unica anualizacion/compuerta y sigue viviendo donde vivia.
  - src/fdekit/decide/metrics.py :: circular_minutes
      def circular_minutes(store: DecideStore, c: Corpus | None = None) -> dict:
      Saltea lo que no esta en `c.meetings` (una ventana de chat no consume minutos-persona) y lo que trae `falla_captura` (una sesion sobre la que el sistema se nego a mirar no es desperdicio medido: 52 min x 8 personas = 416 min-persona presentados como desperdicio que no lo es). Publica el par, con el patron que la funcion ya usa para `sin_timestamps`: 'X min-persona, medidos sobre 9 de 15 sesiones'.
  - src/fdekit/decide/metrics.py :: capture_report
      def capture_report(store: DecideStore, c: Corpus | None = None) -> dict:
    """Arma capture_state() por sesion leyendo store + DraftStore + TranscriptStore."""
      Reemplaza al modulo `capture.py` entero de H6. Devuelve `{'por_estado': {...}, 'sin_captura': [...], 'total': n}` y `report()` imprime la linea 'N de M sesiones sin captura' desagregada por motivo. Cero escrituras.
  - src/fdekit/decide/transcript.py :: TranscriptStore.write / ingest_text / ingest_segments / transcribe_meeting
      def write(self, utterances: list[Utterance], *, meeting: Meeting | None = None,
          con_audio: bool = False, allow_overwrite: bool = False) -> str: ...
def ingest_text(self, text: str, *, meeting: Meeting | None = None) -> list[Utterance]: ...
def ingest_segments(self, segments: list[dict], *, meeting: Meeting | None = None) -> list[Utterance]: ...
def transcribe_meeting(audio_path, root, meeting_id, meeting: Meeting, ...) -> tuple[list[Utterance], str]: ...
      `write()` es el punto de estrangulamiento: consulta `hablada_permitida` y levanta ValidationError. Si `meeting is None` pero `<root>/meetings/<id>.md` existe, lo lee igual — la politica no se esquiva omitiendo un argumento. `allow_overwrite` impide que un canal nuevo pise un transcripto de audio existente y deje todas las anclas con un hash que ya no verifica. `transcribe_meeting` pasa `con_audio=True` y es el unico que lo hace, asi que el chequeo de consentimiento queda exactamente donde estaba semanticamente, un nivel mas abajo.
  - src/fdekit/decide/draft.py :: DraftStore.append / DecisionDraft.origen / to_entity
      def append(self, drafts: list[DecisionDraft], *, meeting: Meeting | None = None) -> int: ...

@dataclass
class DecisionDraft:
    ...
    origen: str = "REUNION"
    expira_en_horas: int = EXPIRA_EN_HORAS

def to_entity(draft: DecisionDraft, meeting_id: str = ""):   # Decision(..., origen=draft.origen)
      `append` consulta el mismo `hablada_permitida`: el `utterance` literal es habla verbatim persistida. `origen` y `expira_en_horas` con default, asi que todo JSONL ya escrito relee; `expired()` pasa a leer el campo de la instancia (la politica viaja con el objeto, no con el llamador). `to_entity` propaga el origen.
  - src/fdekit/decide/query.py :: Agenda.cancelable / verdict / gate_note / _gate
      @dataclass
class Agenda:
    ...
    cancelable: bool = True
    gate_note: dict[str, str] = field(default_factory=dict)   # q.id -> "paso" | "suspendido: <motivo>"
      `is_empty` NO cambia: sigue siendo solo hechos con dueno y fecha. `verdict` devuelve 'proponer cancelar' solo si `cancelable`; si no, 'sin temas: la sesion corre igual por su clase'. Con `gate_binding=False` la pregunta entra a `open_questions` Y su motivo queda en `gate_note`; el encabezado del markdown pasa a '## Preguntas abiertas' con columna `gate`. Una fila, un estado escrito al lado — hoy quedaria duplicada bajo un encabezado que afirma lo contrario de la verdad.
  - src/fdekit/decide/query.py :: why
      def why(store: DecideStore, decision_id: str) -> dict:   # +origen +auditable +nota_origen
      `nota_cita` ('la decision se registro sin canal HABLADA') solo se emite si `d.auditable`; para una sembrada es falsa y el lector concluye que hubo una reunion donde esto se decidio. `nota_origen` dice que se declaro, que rige igual, que no es auditable y que no cuenta para la compuerta ni para el XmR. Es el lector que justifica el campo.
  - src/fdekit/decide/resolve.py :: AliasStore.add / _save_all
      def add(self, alias: Alias, *, symbol=None, force: bool = False) -> Alias:
    """Portal unico. Rechaza un simbolo con `slots` vacio: `mark_disputed` no lo
    puede disputar nunca, asi que el alias resolveria EXTRACTED 1.0 para siempre
    y de forma irrevisable."""
def _save_all(self, aliases: list[Alias]) -> None:   # escritor crudo, privado
      D1 aplicado a AliasStore. `mark_disputed` exige `nueva.slots` y `_jaccard(d.slots or {}, ...) > 0`: un simbolo sin slots no entra a `viejos` ni puede ser `nueva`, y `_l2` tampoco lo propone (jaccard 0 y 0.3*scope < L2_MIN_SCORE=0.35), asi que L1 es su UNICA via y esa via es indisputable. `decide aliases` marca los alias cuyo simbolo no tiene slots.
  - src/fdekit/decide/cli.py :: cmd_transcribe / cmd_meeting / cmd_add / cmd_draft
      # meeting:  --clase {choices=MEETING_CLASS}  --canal {choices=MEETING_CHANNEL}
# add decision: --origen {choices=DECISION_ORIGIN}
# transcribe: try/except -> registra falla_captura y RELANZA la original
      `cmd_transcribe` envuelve la transcripcion: ante excepcion escribe `falla_captura=SIN_AUDIO|ASR_DEGRADADO` con el `repr` de la excepcion como motivo, y **relanza la original** — si el registro de la falla tambien falla, se imprime como aviso y gana la excepcion de Whisper, nunca al reves. Se borra el chequeo de consentimiento de cli.py:248 (cubierto en `transcribe_meeting`). `--origen` en `add decision` es la unica ruta real de escritura del origen: el borrador historico nunca es `ready` (lleva `sigue_vigente` en `missing`), asi que `to_entity` no se ejecuta jamas sobre el y la propagacion sola seria codigo inalcanzable. `choices=` en todos: un string libre es un typo que gobierna la reunion con el perfil equivocado en silencio.
  - src/fdekit/decide/__init__.py :: __all__
      + MEETING_CLASS, MEETING_CHANNEL, DECISION_ORIGIN, MeetingProfile, profile_of,
+ Corpus, corpus, promotion_ceiling
      `tests/test_api_publica.py` exige que todo lo declarado exista. `capture_state`, `hablada_permitida`, `capture_report` y `touches_excluidas` NO se exportan: se importan del submodulo, misma doctrina que `AliasStore`/`volume_gate`/`report`.

MIGRACION DEL CORPUS EXISTENTE:
  - `Decision.origen = "REUNION"` (default): honesto retroactivamente, hoy existe UNA sola ruta de escritura. Ningun numero se mueve por el campo solo. Compat hacia atras OK (`_from_fm` saltea claves ausentes); hacia adelante NO (un .md con `origen` es ilegible para codigo anterior). Unidireccional y asumido — por eso el paso 1 incluye la lectura degradada por archivo.
  - **`auditable` exigiendo `meeting_id` no vacio: ANUNCIO OBLIGATORIO.** Toda decision de pasillo ya persistida sale del numerador de `volume_gate`. Un registro que estaba en 50/50 puede caer a 44/50 y la compuerta se CIERRA. Eso es correcto —no hubo reunion, no hubo roster, no hubo Consent— y tiene que salir impreso: `volume_gate` publica `decisiones_sin_reunion: N` y el veredicto lo nombra. Antes de mergear el paso 3 hay que correr `decide metrics --json` y dejar el numero viejo y el nuevo escritos en el commit.
  - `Meeting.clase = "COMITE"`: es el perfil MAS ESTRICTO (techo 7, gate vinculante, exige facilitador, cancelable, admite audio), y es lo que efectivamente eran todas las reuniones persistidas. Ningun comportamiento cambia. Un default mas laxo relajaria en silencio lo que ya esta en disco.
  - `Meeting.canal = "SINCRONICO"`: verdadero para todo lo persistido (todas fueron de sala). `volume_gate['reuniones']` no se mueve.
  - `Meeting.falla_captura = ""`: ausencia de dato. Ninguna metrica lo consumia antes, asi que ningun numero cambia. **PERO la hoja gana una seccion nueva** y la primera corrida va a mostrar el corpus historico repartido entre CAPTURADA / SIN_RITUAL / NO_REGISTRADA. Eso NO es una regresion: es la primera medicion. Decirlo en el commit y en el pie de la hoja, porque un numero feo que aparece de golpe se lee como algo que se rompio.
  - Filtro de casos de `touches_to_decide`: sobre el corpus de hoy (todo SINCRONICO, COMITE, REUNION, con meeting_id) es un no-op salvo por las decisiones de pasillo, que salen. **Landear esto ANTES de que existan chat y siembra**, recalcular la linea base una sola vez y CONGELARLA con fecha escrita. Recalcularla despues, con datos de chat adentro, es exactamente la regla dura 6 rota: verificado que una rafaga de 7 decisiones de un export mueve center 2,83 -> 1,83 y ucl 9,36 -> 4,73 y convierte 'en control' en 'DEGRADACION' permanente.
  - Columna `en_serie` en el event log: `EventLog.__init__` solo exige las columnas REQUIRED, asi que una columna extra no rompe nada aguas abajo. `variants` y `rework_summary` siguen dando exactamente lo mismo.
  - `save()` que valida: `supersede --apply`, `safe_close --apply`, `tick` y el `st.save(m)` de `cmd_transcribe` pasan a validar. Sobre entidades persistidas con `--force` la regla 'no empeorar' las deja pasar y DEVUELVE los issues heredados. Correr `decide tick --dry-run` justo despues de mergear el paso 1 y publicar la lista de issues heredados: es el inventario de lo que se forzo alguna vez, y hasta hoy era invisible.
  - `TranscriptStore.write` con guardia: los `hablada/*.jsonl` ya escritos no se tocan. Solo se cierran las escrituras nuevas, y solo para clases con `audio_allowed=False` — que hoy no existe ninguna en disco. Cero impacto sobre el corpus, y la puerta queda cerrada antes de que exista el primer UNO_A_UNO.
  - `AliasStore.add` rechazando simbolos sin slots: los alias ya confirmados NO se retiran ni se disputan (seria reescribir la historia). `decide aliases` gana una marca para los que apuntan a un simbolo sin slots: son indisputables hoy, y eso es un riesgo preexistente que se hace visible, no uno que se crea.

ORDEN DE CONSTRUCCION:
  1. 1. **D1 en DecideStore.** `save(obj, force=False) -> list[str]` con 'no empeorar', `_issues` por tipo en lugar de `_check_roster` por string, y lectura degradada por archivo con `ilegibles()`. Nada de esto agrega campos, asi que es refactor puro: la suite queda verde sin tocar un test. Tests nuevos: save rechaza un issue NUEVO; save tolera y DEVUELVE uno heredado; un .md con un campo desconocido no tumba la lectura del directorio.
  2. 2. **D4, techo unico.** `promotion_ceiling(clase, origen)` con firma completa pero sin campos que la alimenten todavia: devuelve 7 para todo. `_check_budget_ceiling()` al importar. `add_decision` la usa. Comportamiento identico por construccion; verde. Test: `_check_budget_ceiling` falla si se inyecta un perfil con techo 8.
  3. 3. **D2, el Corpus.** Entran `MEETING_CLASS`/`MEETING_CHANNEL`/`DECISION_ORIGIN`, `MeetingProfile`/`MEETING_PROFILES`/`profile_of`, los campos `clase`/`canal`/`origen`, los predicados `es_serie_de_decision`/`auditable`, y `store.corpus()`. Se cablea SOLO `volume_gate`. **Aca aterriza la unica regresion anunciada** (decisiones de pasillo fuera del numerador): se actualizan los tests que la fijaban y esa actualizacion ES el anuncio. Tests: una ventana ASINCRONICO no cuenta como reunion; un HANDOVER tampoco; una sembrada no cuenta como decision; `corpus().nota()` nombra a cada excluida.
  4. 4. **D3, el event log.** Columna `en_serie` en `build_event_log`, doble filtro en `touches_to_decide`, `touches_excluidas`. Sobre el corpus de hoy es no-op salvo pasillo. Verde con un ajuste menor. Tests que fijan la propiedad de la regla 6: promover N decisiones contra una Meeting ASINCRONICO no mueve ni un decimal de `touches_xmr()['limites']`; 15 preguntas de daily contra D-017 no le suben ni un toque; `variants` SI las sigue viendo.
  5. 5. **Congelar la linea base.** Correr `decide metrics --json`, escribir en el commit el `n_baseline`, el `center` y el `ucl` con fecha. Desde aca no se recalculan mas. No es codigo: es el paso que hace que los pasos 6-8 y los cuatro huecos no puedan corromper el XmR retroactivamente.
  6. 6. **D6, las dos puertas del habla verbatim.** `hablada_permitida` en schema; `TranscriptStore.write`/`ingest_*`/`transcribe_meeting` y `DraftStore.append` la consultan; se borra el chequeo de cli.py:248. Como todo lo persistido es COMITE (`audio_allowed=True`) y `con_audio=True` solo lo pasa `transcribe_meeting`, ningun test existente cambia de resultado. Test: un UNO_A_UNO rechaza `ingest_text`, no solo `--audio`.
  7. 7. **D5, captura derivada.** `falla_captura`/`motivo_captura` en Meeting, `capture_state` pura en schema, `capture_report` en metrics, seccion nueva en `report()`, `circular_minutes` filtrando por corpus y por falla, `cmd_transcribe` con try/except que relanza la original. Tests: una sesion con decisiones NUNCA sale SIN_RITUAL; una sesion sin nada sale NO_REGISTRADA y no cuenta como falla; una falla de Whisper deja escrito el motivo Y propaga la excepcion original.
  8. 8. **D7 + D1 sobre AliasStore.** `Agenda.cancelable`, `gate_note`, encabezado renombrado, `is_empty` intacto; `AliasStore.add` como portal que rechaza simbolos sin slots y `save_all` privado; `--clase`/`--canal`/`--origen` en el CLI con `choices=`; `__all__`. Tests: ningun diagnostico derivado cambia `is_empty`; un scope vacio no cruza con nada; una decision sin slots no se puede aliasear. **Con esto la fundacion esta cerrada y recien ahi se construyen `seed.py` (H4), `chat.py` (H5), los conflictos (H5) y el resto de los perfiles (H7) — cada uno agrega datos, ya no reglas.**

COBERTURA DE LOS 14:
  #1: D1 + D5. `set_capture` deja de existir: el unico dato que se escribe sobre una Meeting es `falla_captura`, y `save()` con 'no empeorar' lo permite porque 'sin facilitador' y 'sin retencion' son issues HEREDADOS del archivo, no una regresion. No hace falta extraer `Meeting.validate_capture()`: la separacion no es entre grupos de chequeos sino entre lo que la escritura empeora y lo que ya estaba roto. Ademas `cmd_transcribe` relanza la excepcion de Whisper y nunca la del registro.
  #2: D5. Nadie escribe CAPTURADA. `capture_state` la DERIVA de `n_decisiones > 0`, que es exactamente el hecho que `cmd_review` iba a conocer, leido de la fuente de verdad en el momento del reporte. El flujo canonico de fase 2 (meeting -> add/draft -> review, sin audio) sale CAPTURADA sin haber corrido ningun comando extra.
  #3: D7 + D5. La degradacion del veredicto de `agenda()` no se implementa: los diagnosticos derivados van a `advisories`, que se imprimen y no tocan `is_empty`. Los dos defaults dejan de poder cruzarse: `falla_captura=""` es ausencia (no hay ningun NO_REGISTRADA en disco que afirme falla) y `scope=""` no cruza con nada, invariante con test propio que ya cumplen `_scope_proximity` y `cubre_scope` y que hay que preservar en `unlinked_overlaps`.
  #4: D6. `hablada_permitida` se hace cumplir en `TranscriptStore.write()` —por donde pasan `ingest_text`, `ingest_segments` y `transcribe_meeting`— y en `DraftStore.append()`, que persiste el `utterance` literal. El campo se llama `audio_allowed` pero la funcion que lo lee cubre texto y audio; el consentimiento y la retencion solo se exigen con `con_audio=True`, que unicamente pasa `transcribe_meeting`.
  #5: D2 + D3. Un daily es HANDOVER con `promotion_budget=0`, por lo tanto `es_serie_de_decision` es False, por lo tanto sus filas DISCUTIDA salen con `en_serie=False` y no cuentan como toques. `add_question` sigue sin techo (correcto: los compromisos y las preguntas de un handover son el producto), pero sus resources ya no mueven la serie de control. Las filas siguen EN el log para `variants` y `rework_summary`.
  #6: D2. `cuenta_minutos_circulares` no se declara: se deriva. 'aporta minutos circulares', 'aporta toques' y 'cuenta para la compuerta' son LA MISMA pregunta, y la respuesta es `es_serie_de_decision`. El perfil baja de seis campos a cinco y el argumento que valia solo para HANDOVER deja de existir, con lo que no puede borrar los 1215 minutos-persona reales de las otras cuatro clases.
  #7: D1. `save()` valida siempre salvo `force=True`. `declare_conflict` sin `resuelve` levanta ValidationError porque introduce un issue NUEVO sobre un archivo que no lo tenia. Las reglas de `Decision.validate` para CONFLICTO dejan de ser codigo muerto, y de paso se tapa el mismo agujero que ya existe hoy en `supersede`, `safe_close` y `tick`.
  #8: D2 + D3, filtro de CASO. Una decision nacida de una ventana ASINCRONICO sale de `c.decisions` y por lo tanto no aparece en `touches_to_decide` en absoluto — no queda adentro con `toques=1`. Excluir recursos sin excluir casos era peor que no hacer nada, y esa es precisamente la razon de que los dos filtros salgan del mismo Corpus.
  #9: D2 + D3. `touches_excluidas` devuelve `{'casos': {motivo: n}, 'toques_fuera_de_serie': n}` y `touches_xmr` lo publica junto a los limites. Una exclusion silenciosa seria el mismo tipo de mentira que el problema original. Y el paso 5 del orden de construccion congela la linea base ANTES de que exista la primera ventana de chat, con la fecha escrita en el commit.
  #10: D1, mismo cambio que el 7. `DecideStore.save` es el unico portal de reescritura y valida contra el disco; ninguna operacion nueva puede escribir por debajo del validador.
  #11: CLI dentro de D5/D2: `decide add decision --origen` con `choices=DECISION_ORIGIN` es la ruta REAL de escritura, porque es la que el propio `cmd_review` imprime ('Completar con fdekit decide add ...'). `DecisionDraft.origen` + propagacion en `to_entity` cubren el caso en que el borrador SI queda ready. Test obligatorio: promover un borrador ACTA_HISTORICA por el unico camino que el CLI documenta y aseverar `origen=ACTA_HISTORICA` en el .md.
  #12: D1 aplicado a AliasStore: `add()` es el portal y rechaza un simbolo con `slots` vacio, porque `mark_disputed` no lo puede disputar nunca y `_l2` tampoco lo puede proponer — L1 seria su unica via y esa via seria indisputable. Consecuencia directa: `seed_decisions` puebla `slots` con `extract_slots(enunciado + ' ' + criterio)`, y la fila cuyo enunciado no produce ningun slot NO siembra su alias y sale nombrada en el reporte.
  #13: D2. Un borrador historico promovido con `--origen ACTA_HISTORICA` no es `auditable`, por lo tanto sale de `c.decisions`, por lo tanto no cuenta en `volume_gate` (regla 5) y no entra a `touches_to_decide` (regla 6) — que es donde su `date_decided` de hace seis meses seria la linea base entera, porque `touches_xmr` ordena ascendente por `decidida` y toma los primeros 12.
  #14: D2 + D4. `auditable = origen == "REUNION" and bool(meeting_id)`. Las 9 decisiones de pasillo salen del numerador. Y la evasion que el critico deja abierta —borrar `--meeting` para esquivar cualquier techo— se cierra por el lado que corresponde: no con un techo nuevo, sino publicando `decisiones_sin_reunion: N` en `volume_gate` y en la hoja. Lo que se cuenta y se nombra deja de ser un atajo gratis.
---

# Resolución de los 11 críticos contra la fundación

Decididos por mí tras leer los escenarios, varios de ellos verificados por los
refutadores ejecutando scripts. **No corro otra ronda de refutación**: el
rendimiento decrece y las resoluciones ya están determinadas por la evidencia.

| # | qué decía | resolución |
|---|---|---|
| 1, 7, 8 | el XmR: cambiar la definición de "toque" bajo límites congelados corrompe igual que recalcularlos; el `+1` **sí** puede deflacionar un caso al piso (5 de 16 medidos); y la base nunca estuvo congelada | **ACEPTADOS los tres.** El 8 era un bug vivo y ya está arreglado (`8eaf1dd`). Para 1 y 7: `touches_to_decide` devuelve **dos columnas**, `toques` y `toques_en_serie`, y `touches_xmr` declara cuál usa. La serie congelada se queda con la definición con la que se congeló — cambiar de columna exige congelar una base nueva, con fecha, conservando la vieja al lado |
| 2 | `_issues` → `roster_of` → levanta → `tick` muere entero | **ACEPTADO.** `_issues` atrapa y convierte en issue: "no se pudo leer el roster de R-001". Por "no empeorar" es heredado, así que no bloquea |
| 3 | D6 borra el único chequeo de `recording_allowed` y lo reemplaza por uno que no puede dispararse | **ACEPTADO y es el más grave** — es privacidad. `con_audio` va en la firma de `ingest_text`/`ingest_segments`, y **no se borra** `cli.py:248` hasta que el reemplazo esté probado |
| 4 | la lectura degradada alimenta rutas que mutan y rutas que emiten suficiencia | **ACEPTADO.** La degradación vive **sólo** en el eje descriptivo. `tick`, `supersede --apply`, `safe_close --apply`, `add_*`, `agenda` y `volume_gate.ok` leen estricto y fallan |
| 5 | `AliasStore.add` rechazando slots vacíos rompe todas las decisiones existentes | **ACEPTADO.** `add_decision` deriva slots con `extract_slots(statement + " " + criteria)` **antes** de que el rechazo exista |
| 6 | filtrar `circular_minutes` por el Corpus borra 2.400 min-persona de desperdicio real | **ACEPTADO.** `circular_minutes` filtra por `canal == "SINCRONICO"`, no por el Corpus: gente en una sala quema tiempo decida o no. Publica desglose por clase |
| 9 | `COLA_NO_REVISADA` gana a `CAPTURADA` y los drafts dejan residuo por construcción | **ACEPTADO.** No son excluyentes: `capture_state` devuelve `(estado, motivo, cola_pendiente)` |
| 10 | el contador del presupuesto lee del eje degradado → la regla 7 se apaga sin que nada falle | **ACEPTADO.** El presupuesto cuenta por `glob` de archivos, como ya hace `_next_id` — que por eso no tiene el bug |
| 11 | `retention_days` como compuerta sobre una política sin ejecutor: `purge()` tiene **cero llamadores** | **ACEPTADO.** El ejecutor va **antes** que la compuerta. `tick(store, today)` barre `hablada/*.jsonl` contra el `retention_days` de cada Meeting |

## Lo que cambia respecto de la fundación original

- **D3 se corrige**: su afirmación central era aritméticamente falsa. Dos
  columnas, no un filtro.
- **D2 se acota**: el Corpus gobierna `volume_gate` y `touches_xmr`, **no**
  `circular_minutes`.
- **D6 se secuencia**: el ejecutor de retención y el chequeo de audio van antes
  que las compuertas que dependen de ellos.
- **D1 se acota**: lectura degradada sólo en el eje descriptivo.
