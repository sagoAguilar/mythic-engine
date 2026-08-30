# Mythic Engine v1 — Documento de Intención (Bungay)

## Intent

**Contexto (por qué).** Los benchmarks de agentes existentes no cubren interacción multi-agente adversarial/cooperativa con estado compartido verificable. GitHub provee gratis las primitivas de un motor de juego por turnos: estado versionado, identidad, adjudicación determinista vía Actions, replay completo vía historial.

**Propósito (para qué).** Producir un eval multi-agente con trazas reproducibles, presentado como mundo mítico continuo. Artefacto público de Phase 3 del pivot AI engineering. El harness lee el repo post-era sin instrumentación adicional.

**Efecto deseado (qué).** Eras completas jugadas por 3 agentes LLM, con trazas atribuibles por agente, comparables entre runs, y participación humana opcional como baseline.

## Main Effort

El workflow de resolución determinista. Todo lo demás degrada con gracia; si la adjudicación no es reproducible (mismo estado + mismos movimientos + mismo seed = misma resolución), el proyecto no es un eval.

## Decisiones congeladas — núcleo

| Rama | Decisión |
|---|---|
| Propósito | Eval multi-agente disfrazado de juego; humano opcional por la misma interfaz, cero code path especial |
| Victoria | Economía acumulativa + supremacía sostenida K ticks → coronación → cataclismo → nueva era. Cap duro de ticks por era. Una era = un run |
| Árbitro | Híbrido: mecánica determinista paramétrica con seed; LLM solo escribe lore. Regla de oro: ningún token LLM entra en la cadena de adjudicación. Lore write-only |
| Contrapeso | Motor de misiones rubber-band contra el líder. Amortigua, no iguala — intensidad calibrada con datos de eras jugadas |
| Fuerzas | n=3, arquitectura n-agnóstica. Simetría mecánica, asimetría de persona (system prompt). Divergencia de resultados atribuible al agente, no a las reglas |
| Tiempo | Tick global síncrono, compromiso simultáneo (modelo Diplomacy). Un tick = PRs contra el mismo commit de estado + workflow de resolución que los consume, cierra, y produce el commit siguiente. Colisiones resueltas por fórmula con seed |
| Cadencia | Parámetro de era en `era.yml`. Rápida (minutos) para eval intensivo; lenta (horas/día) para trayectorias humanas densas |
| Ausencia/fallo | Un solo code path: sin PR válido en ventana → política NPC determinista con seed. Cubre drop-out humano, agente caído, movimiento malformado. Ticks NPC marcados y excluidos del análisis |
| Unidades | v1: múltiples entes por fuerza, una invocación LLM por tick emite todas las órdenes |
| Estado | Directorio por dominio, YAML, esquema versionado con JSON Schema validado como primer paso del workflow |
| Escritura | Agentes proponen (un archivo nuevo en `/moves/tick-N/`), solo el árbitro escribe `/world/`. CODEOWNERS + check de workflow rechaza PRs que toquen `/world/` |
| Información | Perfecta en v1: `/world/` completo + historial de `/moves/`. Personas rivales ocultas — solo conducta observada (señal de teoría de mente a costo cero) |

## Decisiones congeladas — aventurero

| Rama | Decisión |
|---|---|
| Identidad | Entidad en `/world/` con `controller: github:<username>`. Binding = cuenta GitHub; el árbitro valida `pr.author == entity.controller`. Cero auth propia. Una entidad viva por username |
| Spawn | Movimiento `spawn_adventurer` vía PR — único movimiento sin entidad previa. Gratis en v1. Regiones spawneables: solo neutrales o de la fuerza con menor dominancia (micro-rubber-band). Sin archetype mecánico en v1 |
| Entrada/salida | Re-entrada sin spawn: su PR válido reemplaza la política NPC ese tick. El personaje persiste en `/world/` entre ausencias; historial NPC marcado en `/moves/` |
| Atadura mecánica | Movimientos validados contra su YAML: posición, recursos, unidades. Misma jaula que los agentes. Atadura epistémica: no existe en v1 — infraestructura de niebla, v2 |
| Persistencia trans-era | El personaje vivo sobrevive el cataclismo con reset de recursos a baseline. Continuidad de identidad, no de ventaja |
| Muerte | Puede morir (recursos a cero por combate o misión fallida con stake). Permadeath del personaje, no del jugador: entidad a `/world/graveyard/`, username libre para spawn nuevo. Herencia: expansión candidata única, no v1 |
| Graveyard | Único directorio de `/world/` que sobrevive el reset de era. Memoria del mundo |
| Loot al morir | Fracción fija se quema (`era.yml`); resto depositado en la región de la muerte como botín neutral reclamable por M ticks, luego se disipa. El asesino cobra solo si controla la posición. Muerte sin asesino: mismo mecanismo sin beneficiario |
| Crecimiento | Recursos (reglas comunes), reputación por fuerza (contador determinista; umbrales desbloquean comercio/refugio/encargos), capacidades por logro (desbloqueos discretos, cada uno una acción nueva en el schema). Stats RPG continuos: rechazado. Techo de poder duro: nunca decide eras por sí solo |
| Victoria propia | No compite por dominancia. Quest personal declarada en `era.yml`: acumular X, completar cadena de misiones, sobrevivir la era, o variante de bando: "que X corone" |
| Influencia sobre el desenlace | Canales legítimos: comercio por reputación (acción plana `trade`, costo fijo `adventurer.trade_cost`, no un cap de volumen escalable — F8), ejecución de quests rubber-band menores, obstrucción posicional, botín póstumo. Kingmaking permitido dentro de caps |
| Techo verificable | Replay contrafactual post-era: movimientos humanos sustituidos por política NPC. Si el ganador cambia, el humano decidió la era → caps se aprietan. Métrica: delta de resultado, no impresión |
| Legado | Al coronar una fuerza, si la reputación del aventurero supera umbral: título diegético en chronicle/graveyard, persistente trans-era, valor mecánico cero. Pago en memoria del mundo, no en poder |

## Decisiones congeladas — misiones

| Rama | Decisión |
|---|---|
| Fuentes | (1) Motor rubber-band por umbrales de dominancia; (2) eventos de mundo por triggers de estado (tabla en `era.yml`); (3) fuerzas como emisoras: v2, requiere catálogo cerrado; (4) el Gremio de Aventureros — tablero determinista por capital, `eligibility: adventurer`, escalera de tiers por reputación (Bronce/Plata/Oro/Platino), no confundir con "encargos" (v2): el Gremio autora las misiones, las fuerzas nunca las emiten (F9). El humano nunca crea misiones |
| Elegibilidad | Campo `eligibility`: `forces` / `adventurer` / `any`. Rubber-band menores: `any`; mayores: `forces` — el aventurero como erosión, no demolición. Cupo: `max_claimants: 1` u `open` |
| Toma | Movimiento `accept_quest` validado contra eligibility, estado del tomador, cupo. Colisión de reclamos exclusivos: fórmula con seed. Stake cobrado al aceptar |
| Notificación | Capa 1: sección de quests en `/chronicle/tick-N.md`. Capa 2 (v1): GitHub Issue por quest elegible `adventurer`/`any`, cerrado al resolverse. El Issue es notificación, no interfaz: tomar la quest sigue siendo PR. Capa 3 (v2): bot Telegram |

## Decisiones congeladas — catálogo de movimientos (punto 1)

**Estructura:**
- E1: un movimiento = batch de órdenes. Cap por tick: 3 órdenes fuerzas, 2 aventurero (`era.yml`)
- E2: recurso único — esencia
- E3: unidades fungibles por región (contadores); el aventurero es entidad con `units: 1`
- `gather` eliminado: yield pasivo en fase económica. `recruit` y `claim_loot` añadidos

| Acción | Actor | Parámetros | Precondiciones | Efecto |
|---|---|---|---|---|
| `move_units` | ambos | from, to, count | unidades ≥ count en from; to adyacente; to propia o neutral | transferencia |
| `attack_region` | fuerzas | from, to, count | ídem; to hostil | combate en fase 5 |
| `siege` | fuerzas | from, to, count | unidades ≥ count en from; to adyacente; to hostil con fortificación > 0; to sin asedio activo | unidades comprometidas (fuera de juego, sin combate); crea asedio persistente (F6) |
| `recruit` | fuerzas | region, count | región propia; esencia ≥ count × costo | −esencia, +unidades |
| `fortify` | fuerzas | region | región propia; esencia ≥ costo | +1 fortificación, persistente, cap F |
| `decree` (kind: dismiss) | fuerzas | region, count | región propia; unidades ≥ count en region | −unidades, sin reembolso |
| `decree` (kind: surge_recruit) | fuerzas | region, count | ídem recruit; esencia ≥ count × costo + recargo (F7) | −esencia (costo + recargo), +2×count unidades |
| `accept_quest` | según eligibility | quest_id | eligibility, cupo, stake, posición | reclamo; stake cobrado |
| `spawn_adventurer` | humano | name, origin | sin entidad viva del username; origin spawneable | entidad con baseline |
| `claim_loot` | aventurero | region | presente en región con botín activo | +botín; botín extinguido |
| `trade` | aventurero | region | presente en region; region propiedad de una fuerza; reputación ≥ umbral comercio; esencia ≥ costo | tirada con seed por tier de profundidad (F8); éxito: −esencia aventurero, +esencia fuerza, +reputación; fallo: nada (solo la orden) |
| `swift_march` | aventurero | from, to, count | capacidad `swift_march`; ≤ 2 saltos adyacentes, cada salto con legalidad de `move_units`; esencia ≥ costo | transferencia multi-salto; −esencia (fase 4) |
| `sanctuary` | aventurero | — | capacidad `sanctuary`; esencia ≥ costo | inmunidad a la caza hasta `tick + sanctuary_ticks − 1`; −esencia (fase 4) |
| `insure` | aventurero | quest_id | capacidad `insure`; quest de Gremio activa reclamada por él; esencia ≥ prima | marca la quest asegurada; −esencia (fase 8) |
| `entrench` | aventurero | quest_id | capacidad `entrench`; quest `hold` de Gremio activa reclamada por él; una vez por quest; esencia ≥ costo | −1 tick al objetivo `hold`; −esencia (fase 8) |
| `wager` | aventurero | quest_id | capacidad `wager`; quest de Gremio activa reclamada por él | doble-o-nada al resolver (fase 8) |

`move_units` / `attack_region` separados: intención explícita — el harness lee agresión declarada, no deducida. Las 5 acciones de capacidad son del Gremio (punto 9, F9): sólo invocables si el aventurero ha desbloqueado la capacidad correspondiente.

**Orden de resolución del tick (regla de juego, congelada):**
1. Validación de schema + sustitución NPC
2. `spawn_adventurer`
3. `recruit`, `fortify` (esencia pre-tick)
4. Movimientos y ataques simultáneos — colisiones por fórmula con seed; capacidades `swift_march` (≤ 2 saltos) y `sanctuary` (fija `sanctuary_until = tick + sanctuary_ticks − 1`)
5. Resolución de combates — la caza (`attack_region target:adventurer`) contra un aventurero con `sanctuary_until ≥ tick` se anula (sólo la muerte; las unidades siguen resolviendo como parte normal)
6. `claim_loot`
7. Yield económico sobre propiedad post-combate
8. Resolución de objetivos de quests contra estado post-combate — paso 0: aplica `insure`/`wager`/`entrench`; verifica también `travel`/`hold` del Gremio; recompensa (esencia + reputación, moneda en Bronce), otorga capacidad del tier, registra tier completado; `wager` dobla, `insure` reembolsa el stake
9. Spawn de quests por triggers — venganza, rubber-band y, con aventurero vivo, tablones del Gremio (cap propio)
10. Contador de supremacía / coronación
11. Chronicle + lore

**Filosofía embebida:** yield post-combate — premia iniciativa, más eventos por era, más señal por dólar. Empate en combate favorece al defensor — determinismo estricto; el seed queda reservado a colisiones multi-parte.

## Decisiones congeladas — mapa inicial (punto 3)

- **M1 — 12 regiones:** 3 capitales + 9 neutrales. Coronar (>45%) exige 6 regiones: capital + brazo propio (3) nunca bastan — tomar anillo o invadir brazo ajeno es estructuralmente obligatorio
- **M2 — Topología:** 3 brazos idénticos (capital → 2 neutrales) convergiendo en un anillo central de 3 neutrales (triángulo). Aristas por brazo: C–A, C–B, A–R, B–R; anillo: R0–R1–R2. 15 aristas, grado 2–4. Capital con exactamente 2 rutas de entrada, ambas fortificables. Todo contacto inter-fuerza pasa por el anillo
- **M3 — Valor:** yield uniforme 1; anillo y capitales yield 2. El anillo es premio geográfico no poseído al inicio, simétrico por construcción, anclaje natural de quests de eventos. Spawneables del aventurero al tick 0: las 9 neutrales
- **Generación:** `generate_map.py --seed N --arms k` emite `regions/*.yml` con grafo de adyacencia; test de isomorfismo rotacional. `--arms k` cumple la n-agnosticidad gratis

## Decisiones congeladas — fórmulas de resolución (punto 2)

**F1 — Combate determinista de aniquilación:**
- `poder_atacante = unidades_atacantes`; `poder_defensor = unidades_defensoras + bonus_fort(F)`, donde `bonus_fort(F)` es el bono acumulado declarado para el nivel `F` — escalonado por nivel, no un multiplicador plano (valores en F3)
- Atacante > defensor: toma la región con `atacante − defensor` supervivientes; defensor eliminado
- Atacante ≤ defensor: atacante eliminado; defensor pierde `max(0, atacante − bonus_fort(F))`
- Cada combate es aniquilación del perdedor. Traza auto-explicable; seed no toca combate; eras rápidas = más runs por presupuesto

**F2 — Colisión multi-parte:**
- Orden de resolución por pares derivado de `hash(seed, tick, region)` — nunca por orden de PR ni ID de fuerza
- Cada par resuelve con F1; el superviviente enfrenta al siguiente
- Ataque espejo (A→B y B→A entre las mismas regiones): ambos proceden contra guarniciones reducidas — unidades comprometidas al ataque no defienden. El all-in es apuesta real; señal de gestión de riesgo

**F3 — Valores iniciales (`era.yml`, calibración empírica declarada como knowledge gap):**
- Yield: 1 esencia/región/tick; capitales: 2
- Recruit: 2 esencia/unidad. Fortify (escalonado por nivel, no plano): costo 5/10/20 esencia (niveles 1/2/3), `bonus_fort(F)` acumulado 2/5/10, cap F=3
- Baseline aventurero: 5 esencia. Costo de `trade`: 3 esencia por intento (acción plana, no cap de volumen — F8)
- Rubber-band: >45% regiones. K coronación: 10 ticks. Cap de era: 100 ticks

**F4 — Aventurero en combate:**
- No bloquea captura: coexiste como no-combatiente; la región cambia de dueño sin combatirlo
- Muere solo por declaración explícita: `attack_region` con `target: adventurer` — cuesta una orden del batch
- Matarlo paga reputación negativa con las demás fuerzas (parámetro en `era.yml`). Caza posible, explícita en traza, con precio diplomático

**F5 — Upkeep de esencia:** cada fuerza paga `floor(unidades_totales / upkeep_divisor)` de esencia por tick, neteado contra el rendimiento en la misma fase 7 (propiedad post-combate, mismo momento que el yield). Una fuerza con menos unidades que `upkeep_divisor` no paga nada — el costo solo muerde una vez que el ejército ya creció, no en la apertura. `upkeep_divisor` en `era.yml`, calibración empírica declarada como knowledge gap, igual que F3: valor inicial `5`, razonado (ningún tope de guarnición existe en ninguna región, así que sin este costo la esencia y las unidades acumulan sin límite), no dato jugado.

**F5 (continuación) — Upkeep de fortificación, o erosión:** además del upkeep de unidades, cada región fortificada (nivel > 0) de una fuerza le cuesta `economy.fortify_upkeep.at_level(nivel)` esencia por tick — mismo curva escalonada por nivel que costo/bono (valores iniciales 1/3/6 en niveles 1/2/3, calibración empírica como F3), pagado en la misma fase 7, después del upkeep de unidades y neteado contra el saldo real de la fuerza (esencia acumulada más el flujo neto del tick, no solo el flujo). Si el saldo no alcanza para cubrir todas sus regiones fortificadas, la fuerza paga en orden ascendente (nivel, luego ID léxico de la región) — el compromiso más barato primero — hasta agotar el saldo; cada región que no pudo pagarse pierde exactamente 1 nivel de fortificación ese tick (nunca bajo 0). Sin reembolso ni penalización adicional más allá del nivel perdido — es pura erosión, no una orden ni una acción de la fuerza.

**F6 — Siege (compromiso multi-tick contra la fortificación ajena):** `siege` (fuerzas, from/to/count) compromete `count` unidades desde `from` — mismo cupo simultáneo que `attack_region`/`move_units` en fase 4, sin combate — contra una región hostil `to` con fortificación > 0 y sin asedio activo previo (un asedio por región, sin apilar). Las unidades comprometidas salen de `from` y quedan fuera de juego (sin producir, sin defender, sin poder actuar) mientras el asedio dura; ese es el costo real, no un recurso nuevo. Se declara una sola vez — no consume orden en los ticks siguientes. Estado persistente nuevo en `/world/sieges/<region>.yml`: `attacker`, `defender`, `from`, `units`, `ticks_elapsed`.

Cada tick, en fase 7 (después del upkeep de unidades y de fortificación, mismo saldo real neteado): la fuerza atacante paga `economy.siege_upkeep` (esencia plana, valor inicial 3, calibración empírica como F3/F5) por cada asedio activo que sostiene. Si no alcanza el saldo, ese asedio termina de inmediato ese tick — sin erosión parcial, sin gracia. Si se paga, `ticks_elapsed` incrementa; cuando `ticks_elapsed` es múltiplo de `economy.siege_erosion_interval` (valor inicial 2, calibración empírica), la fortificación de `to` baja 1 nivel (piso 0). Un asedio recién declarado este tick no procesa upkeep ni erosión en su propio tick de declaración — solo a partir de la fase 7 del tick siguiente.

Un asedio termina (sin acción explícita de cancelación en v1) cuando: (a) el upkeep no se puede pagar: fin inmediato; (b) la fortificación de `to` llega a 0 por la erosión: fin, ya no queda nada que erosionar; (c) `to` cambia de dueño por cualquier vía (el propio atacante la toma por `attack_region`, o un tercero la captura): fin, el asedio ya no tiene objeto — sitiar nunca captura por sí mismo, solo ablanda el muro. Al terminar por cualquier causa, las unidades comprometidas regresan a `from` si el atacante todavía la posee; si no, se pierden. Sin reembolso de esencia ya pagada.

Sin aislamiento especial (decisión explícita): un asedio no bloquea nada en `to` — el defensor puede reforzar o fortificar con normalidad, y cualquier otra fuerza o el aventurero puede seguir actuando ahí. El costo del asedio es la exposición estratégica de tener unidades atadas en otro lugar, no un candado artificial.

**F7 — Decree (categoría de acciones infrecuentes de alto impacto, fase 3):** `decree` (fuerzas, kind: `dismiss` | `surge_recruit`) es la válvula de escape que falta una vez que unidades y fortificación cuestan upkeep (F5/F6) — sin ella una fuerza solo puede acumular, nunca deshacerse de lo que no puede sostener.

- `dismiss` (region, count): reduce en `count` las unidades de una región propia, sin reembolso de esencia — unidireccional, igual que todo otro gasto de esta economía (recruit, fortify, stakes).
- `surge_recruit` (region, count): mismas precondiciones que `recruit` (región propia, esencia ≥ count × `recruit_cost`), pero entrega `2 × count` unidades — el costo por unidad y el upkeep de las unidades resultantes no cambian, solo el rendimiento de la acción.

El costo real de `surge_recruit` es un **recargo plano por invocarlo**, encima del costo normal de recruit, que escala con uso consecutivo y resetea a base en cuanto pasa un tick sin usarlo ("castiga el spam, perdona la contención"). Curva de 3 niveles igual de forma que `fortify_cost`/`fortify_bonus` (`economy.decree_surge_surcharge`, valores iniciales 5/10/20, calibración empírica como F3): el streak persiste por fuerza (`surge_streak` en `forces/<id>.yml`, nunca visto por el jugador como recurso — es contador interno). Cada tick que la fuerza invoca `surge_recruit` al menos una vez, el streak sube en 1 (tope 3, no sigue duplicando después del tercer uso consecutivo) y el recargo de ESE tick se cobra según el streak resultante — un mismo streak cubre todas las órdenes `surge_recruit` de la misma fuerza en el mismo tick, no se vuelve a escalar dentro del tick. Cualquier tick en que la fuerza no invoque `surge_recruit` resetea su streak a 0, sin excepción ni gracia adicional.

**F8 — Trade (aventurero ↔ fuerza, fase 6, junto a `claim_loot`):** el flujo que `docs/intent.md` original dejaba sin definir se resuelve como **tributo, no intercambio** — la esencia se transfiere genuinamente a la fuerza (segunda transferencia real de la economía, tras el botín; en todo el resto del juego la esencia se acuña o se destruye, nunca se mueve entre libros), nunca al revés. `trade` (aventurero, region — debe ser la posición actual) exige, en orden: (1) la región es propiedad de una fuerza (no neutral); (2) la reputación del aventurero con esa fuerza ya alcanza `reputation.thresholds.trade` (el umbral que desbloquea comercio, ya congelado — camino de arranque real: quests que dañan a una fuerza rival otorgan `quest_damages_force_rivals` a las demás, alcanzable en una sola quest); (3) esencia (pool pre-tick, compartido con recruit/fortify) ≥ `adventurer.trade_cost` (acción plana, no escalable — mismo patrón que `fortify`). Pasadas las tres, el intento **siempre resuelve — nunca se rechaza por la parte probabilística**, vía tirada seedeada: `sha256(seed:tick:actor:force) % 100` contra el umbral de éxito del tier de profundidad ESTRUCTURAL de la región (por prefijo del id — `capital-`, `arm-`, o ninguno de los dos → `ring` — independiente de quién la posea actualmente): `adventurer.trade_success_pct` (valores iniciales ring 50 / arm 75 / capital 100, calibración empírica como F3). Éxito: −costo esencia aventurero, +costo esencia fuerza, +`reputation.deltas.trade_per_tick` reputación (clamped a la escala de reputación, misma disciplina que las recompensas de quests en fase 8). Fallo: nada se mueve — ni esencia ni reputación — solo se gastó la orden, mismo principio que perder un duelo F1 no es "rechazado".

**F9 — Gremio de Aventureros (`travel` + `hold`; escalera completa Bronce/Plata/Oro/Platino con capacidades; fase 9 spawn, fase 8 resolución).** Cuarta fuente de misiones determinista, junto al motor rubber-band y los eventos de mundo. NO son "encargos" (fuerzas como emisoras → v2): el Gremio autoriza quests por fórmula con seed; las fuerzas nunca las eligen ni emiten. Un tablón en cada capital; `eligibility: adventurer` siempre. La asimetría de recompensas por fuerza es del lado del aventurero (qué gana por aliarse), no del lado de las fuerzas —que siguen mecánicamente simétricas—; no cruza el límite de "asimetría mecánica → v3". El detalle completo vive en su propia sección (**Decisiones congeladas — el Gremio de Aventureros**, abajo); aquí queda su encaje en las fases: spawn en fase 9 (tras venganza y rubber-band, sólo con exactamente un aventurero vivo), resolución en fase 8 (paso 0 de marcadores + verificación `travel`/`hold` + recompensa/capacidad), capacidades ejecutables en fases 4 (`swift_march`/`sanctuary`) y 5 (anulación de la caza por `sanctuary`).

Tipo y objetivo de cada slot `(fuerza, tier)` por `h = int(sha256(seed:tick:guild:force:tier), 16)` (un solo hash por tier decide ambos): `h % 2 == 0` → `travel`, impar → `hold`; objetivo X = `candidatos_ordenados[h % len]`. Candidatos `travel` = todas las regiones salvo la posición actual del aventurero (por id); candidatos `hold` = neutrales (`owner == null`, por id); sin candidatos → el slot se salta ese tick. Cumplimiento de `travel`: la posición ACTUAL del aventurero == la región objetivo, cualquier tick hasta el `deadline` inclusive (`tick_spawn + guild.objectives.travel_deadline[tier]`) — sin verificación de ruta, igual que `blockade`. Cumplimiento de `hold`: mismo mecanismo de racha de ocupación consecutiva que `blockade` (idéntico código, `params.n_ticks` = `guild.objectives.hold_n_ticks[tier]`), deadline = `tick_spawn + quests.window_ticks` (reutilizado) — no toca el estado de la fuerza en absoluto (dueño, combate, yield siguen su curso, mismo principio de coexistencia F4). Las misiones del Gremio no cuentan contra los cupos `max_active_minor`/`max_active_major` del motor rubber-band — flujo independiente aunque compartan el campo `tier` (solo para el bucket de stake).

## Decisiones congeladas — cierres finales (vacíos 1–4)

**Política NPC (determinista, máx 1 orden/tick aunque el cap sea mayor — diferencia de volumen visible en traza):**
- *Fuerza:* (1) región propia atacada el tick anterior y esencia ≥ costo → `recruit` en región propia con menos unidades (desempate: menor ID léxico); (2) esencia ≥ fortify y capital F < cap → `fortify` capital; (3) neutral adyacente → `move_units` con mitad (redondeo abajo) de la región propia adyacente con más unidades (desempates: menor ID destino, menor ID origen); (4) no-op. Nunca ataca hostiles: el NPC es suelo, no jugador. Fuerza en NPC permanente pierde por pasividad — era contaminada debe terminar rápido
- *Aventurero:* (1) botín presente → `claim_loot`; (2) combate en su región el tick anterior → `move_units` a adyacente neutral con menos unidades (desempate: menor ID); (3) no-op. Superviviente pasivo

**Catálogo de objetivos rubber-band (4 tipos, verificación por comparación de estado en fase 8):**
| Tipo | Objetivo | Tier |
|---|---|---|
| `raid` | Región X del líder cambia de dueño antes de tick T | menor (`any`) |
| `blockade` | Ocupar neutral X adyacente al líder N ticks consecutivos | menor (`any`) |
| `attrition` | Unidades del líder ≤ valor al spawn − D | mayor (`forces`) |
| `dethrone` | Streak de supremacía del líder a 0 antes de T | mayor (`forces`) |

X, T, N, D por fórmula con seed (X = región del líder con menor guarnición; T = tick + ventana `era.yml`). Cap de composición: máx 1 mayor + 2 menores activas — sin cap, el rubber-band iguala en vez de amortiguar

**Deltas de reputación (aventurero↔fuerza, −100..+100, inicio 0, sin decaimiento intra-era; cataclismo ×0.5):**
| Evento | Delta | Con |
|---|---|---|
| Comercio con F | +2/tick | F |
| Quest que daña a F cumplida | −15 / +10 | F / rivales de F |
| F mata al aventurero | vía quest de venganza `raid` contra F (trigger en tabla) + reputación del sucesor | — |
| Refugio en territorio de F | +1/tick | F |

Umbrales: comercio ≥ +10, refugio ≥ +25, encargos (v2) ≥ +40; Gremio Plata ≥ +10, Oro ≥ +25, Platino ≥ +70 (punto 9). Reputación fuerza↔fuerza: rechazada en v1 — los agentes se modelan por conducta, sin mecánica adicional. Las recompensas de reputación del Gremio (Bronce +1/0 por moneda, Plata +1, Oro +5, Platino +15) son positivas y sólo con la fuerza del tablón; viven en el bloque `guild` de `era.yml`

**Plantilla de chronicle (contrato del harness, fase 11, tablas crudas sin prosa — un artefacto, tres consumidores: harness/regex, humano/render, LLM de lore/input):** secciones fijas: Órdenes (fuerza, origen agent|human|npc, válidas), Combates, Colisiones (orden por hash), Economía, Quests (spawn/resueltas/expiradas), Supremacía (regiones, %, streak, K restante), Aventurero (posición, esencia, reputaciones, eventos)



```
/world/
  era.yml            # cadencia, cap de ticks, seed, K de coronación,
                     # baseline de recursos, quema de loot, M de disipación,
                     # umbrales de reputación, tabla de triggers, presupuesto tokens,
                     # caps de órdenes por tick, trade_cost y trade_success_pct
                     # (F8), costos recruit/fortify, cap F de fortificación,
                     # upkeep_divisor y fortify_upkeep (F5),
                     # siege_erosion_interval y siege_upkeep (F6),
                     # decree_surge_surcharge (F7),
                     # guild (F9: thresholds, platinum_condition,
                     # objetivos, recompensas, stakes, capacidades/costos/firmas)
  tick.txt           # puntero atómico de tick
  regions/<id>.yml   # dueño, recursos base, unidades presentes, fortificación, botín activo
  forces/<id>.yml    # persona ref, esencia, unidades, surge_streak (F7)
  forces/adventurer-<handle>.yml  # controller, esencia, reputación, capacidades, quest personal,
                                  # guild (tiers completados por fuerza), sanctuary_until (F9)
  graveyard/         # entidades muertas + títulos; sobrevive el reset de era
  quests/active/<id>.yml          # eligibility, objetivo, reward, stake, deadline, cupo,
                                  # params (guild_tier + marcadores insured/wagered/entrenched, F9)
  quests/resolved/
  sieges/<region>.yml             # asedio activo contra esa región (F6): attacker, defender, from, units, ticks_elapsed
/moves/tick-<N>/<force>.yml       # batches consumidos, preservados como traza
/lore/                            # write-only, LLM, jamás leído por adjudicación
/chronicle/tick-<N>.md            # resumen mecánico por tick, generado por árbitro
```

## Decisiones congeladas — el Gremio de Aventureros (punto 9)

**Origen y encaje.** Cuarta fuente de misiones determinista, junto al motor rubber-band y los eventos de mundo. NO son "encargos" (fuerzas como emisoras → v2): el Gremio autoriza quests por fórmula con seed; las fuerzas nunca las eligen ni emiten. Un tablón en cada capital; `eligibility: adventurer` siempre. La asimetría de recompensas por fuerza es del lado del aventurero (qué gana por aliarse), no del lado de las fuerzas —que siguen mecánicamente simétricas—; no cruza el límite de "asimetría mecánica → v3".

**Tipos de objetivo (2):**
| Tipo | Objetivo | Verificación (fase 8) |
|---|---|---|
| `travel` | Aventurero alcanza región X antes de tick T | posición == X en algún tick ≤ deadline; sin restricción de ruta en v1 |
| `hold` | Ocupar región X durante N ticks consecutivos | reutiliza el streak de `blockade` (`quest.progress`) |

**Cuatro tiers, acceso por reputación por fuerza (dos pasos):**
| Tier | Acceso (reputación con esa fuerza) | Stake | Esencia | Reputación | travel T | hold N |
|---|---|---|---|---|---|---|
| Bronze | ≥ 0 | menor (1) | 1 acierto / 2 fallo | +1 acierto / +0 fallo (moneda) | 3 | 1 |
| Silver | ≥ 10 (= `trade`) | menor (1) | 3 | +1 | 5 | 2 |
| Gold | ≥ 25 (= `refuge`) | mayor (2) | 8 | +5 | 7 | 3 |
| Platinum | ≥ 70 (nuevo) **y** esa fuerza reducida a ≤ 1 región | mayor (2) | 25 | +15 | 10 | 5 |

- **Acceso** (reputación ≥ umbral) habilita que el tablón de esa fuerza ofrezca ese tier. **Completar** una quest del tier otorga la capacidad del tier y fija el rango. **Rango con la fuerza = tier más alto completado allí** (derivado, sin contador aparte).
- Bronze: moneda sembrada `int(sha256(f"{seed}:{tick}:{aventurero}:{quest_id}"),16)` (con `aventurero` = id del reclamante) por paridad — **par → acierto** (+1 reputación, +1 esencia); **impar → fallo** (+0 reputación, +2 esencia: consuelo doblado, toda completación neto-positiva). Silver/Gold/Platinum: recompensas planas, deterministas. La reputación de Gremio es siempre positiva y solo con la fuerza del tablón (`params.force`) — sin rivales, sin daño; contrasta con las quests de daño (raid/blockade/attrition/dethrone), que golpean a todas las fuerzas. Recompensas repiten por completación (así se sube de rango); la capacidad se otorga una vez (lista deduplicada).
- Sin penalización por fallo, expiración o abandono más allá del stake (cobrado al aceptar). La reputación nunca baja por una quest de Gremio fallida.
- Platinum: la condición heroica (fuerza a ≤ 1 región) es un trigger de estado de mundo, generado como el rubber-band reacciona a la dominancia (condición opuesta, mismo mecanismo). No es "encargo": la fuerza no pide ayuda.

**Spawn y caps (fase 9, propios — nunca comparten el cap del rubber-band, para no debilitar el contrapeso):**
- Cada tablón (fuerza) ofrece una quest activa por cada tier al que el aventurero tiene acceso ahora (Bronze siempre; el resto por umbral; Platinum solo si además se cumple la condición heroica). Cap = suma de tiers accesibles por tablón; ≤ 3 con reputación 0, crece con la reputación.
- Slot `(fuerza, tier)` con ≤ 1 quest activa. Al resolverse o expirar, el slot queda vacío ese tick y el tablón repone al siguiente (seed nuevo → objetivo nuevo).
- Tipo (`travel`/`hold`) y objetivo por fórmula con seed `sha256(seed:tick:guild:fuerza:tier)`. Un solo hash `h = int(hexdigest,16)` decide ambos (como la paridad de la moneda Bronze y el módulo de `blockade`): `h % 2 == 0` → `travel`, impar → `hold`; el objetivo X = `candidatos_ordenados[h % len]`. Candidatos `travel` = todas las regiones salvo la posición actual del aventurero, ordenadas por id; candidatos `hold` = neutrales (`owner == null`), ordenadas por id. Si no hay candidatos (p. ej. `hold` sin neutrales) el slot se salta ese tick (como `blockade`). `hold` N por tier (`hold_n_ticks`).
- Deadlines: `travel` T = `tick + travel_deadline[tier]`; `hold` T = `tick + quests.window_ticks` (misma ventana que las demás quests; N es el objetivo, no el plazo). Recompensa registrada al spawn: Bronze 0 (la moneda de fase 8 paga acierto/fallo), resto la esencia plana del tier; el `stake` es el valor del bucket (`menor`/`mayor`) del tier.
- Acceso por tier uniforme: `reputación ≥ thresholds[tier]` (con `thresholds.bronze = 0`, Bronze siempre abre); Platinum además exige la condición heroica (`≤ platinum_condition.force_regions_max` regiones). Orden de emisión: fuerzas ordenadas por id, luego tiers Bronze→Platinum; el `seq` del id `<tipo>-<tick>-<seq>` solo avanza en spawns reales (un slot ocupado o saltado no lo consume). Los tablones del Gremio se generan **al final** de la fase 9, tras venganza y rubber-band.
- Solo se generan con **exactamente un** aventurero vivo. v1: un aventurero; con cero (nadie a quien encomendar) o con varios (interacción multi-aventurero diferida) el spawn de Gremio es no-op.

**Capacidades (6 slots = 2 compartidas + 1 firma por fuerza → 5 distintas; `capabilities` lista plana deduplicada, techo acotado por construcción):**
| Capacidad | Acción | Efecto | Costo |
|---|---|---|---|
| fast-travel (compartida) | `swift_march` | mover hasta `swift_march_hops` saltos adyacentes en una orden (cada salto con legalidad de `move_units`) | 1 esencia |
| sanctuary (compartida) | `sanctuary` | `sanctuary_ticks` ticks de inmunidad a la caza (`attack_region target:adventurer`) | 2 esencia |
| warranty — F1 El Registro | `insure` | asegura tu quest de Gremio activa: stake devuelto si falla/expira | 1 esencia (prima) |
| bulwark — F2 La Marea | `entrench` | −1 tick al objetivo `hold` de tu quest actual (equiv. +1 progreso), una vez por quest | 2 esencia |
| all-in — F3 La Apuesta | `wager` | doble-o-nada tu quest de Gremio activa: recompensa ×2 si éxito, pérdida total si falla | se autocobra |

- Todas son acciones invocables con costo en esencia (no modificadores pasivos, no cooldowns). El costo dobla como sumidero de esencia; el cooldown se reserva por si el sandbox muestra que la inmunidad de `sanctuary` es sostenible. `wager` sin prima: el consuelo + stake perdidos son el precio.
- Asignación por tier: **Bronze → swift_march · Silver → sanctuary · Gold → la firma de esa fuerza · Platinum → ninguna capacidad (v1)**. El comodín de Platinum queda **diferido**: completar Platinum paga esencia + reputación y sube el rango, pero no otorga capacidad en esta versión (evita el reparto ambiguo "cualquiera de las que aún no tengas"; se retoma si el sandbox lo pide). Firmas: `force-1 insure`, `force-2 entrench`, `force-3 wager` (mapa persona; ver `personas/force-*.md`). Con n≠3 el mapa de firmas es la única pieza atada a las personas concretas — deliberado (eje de asimetría de persona), no asimetría mecánica de fuerzas.
- `insure`/`wager`/`entrench` marcan la quest (booleanos en `params`), se aplican en fase 8 antes de la verificación. `swift_march`/`sanctuary` resuelven en fase 4; `sanctuary` fija inmunidad hasta `tick + sanctuary_ticks − 1`, respetada por la fase 5 (intención defensiva gana ante caza simultánea).

**Encaje en el orden de resolución (sin renumerar las 11 fases):**
- Fase 4: `swift_march` (movimiento de ≤ `swift_march_hops` saltos por alcanzabilidad BFS, no por ruta declarada; cobra esencia al ejecutar; comparte el presupuesto de un movimiento por tick con `move_units`); `sanctuary` (fija `sanctuary_until = tick + sanctuary_ticks − 1`, cobra esencia, idempotente en el tick).
- Fase 5: la caza contra un aventurero con `sanctuary_until ≥ tick` se anula — **sólo la muerte**; las unidades comprometidas ya salieron en fase 4 y siguen resolviendo como parte normal (fusión con guarnición propia o F1), igual que una caza que no encuentra aventurero.
- Fase 8: paso 0 nuevo — aplica `insure`/`wager`/`entrench` sobre quests reclamadas (marca + cobra esencia); luego verifica objetivos (añade `travel`/`hold`); al éxito de una quest de Gremio paga esencia + reputación (moneda en Bronze), otorga la capacidad del tier (dedup) y registra el tier completado; `wager` dobla la recompensa, `insure` devuelve el stake al fallo. Una moneda Bronze fallida aún **completa** el tier (el hacer, no el acierto, sube de rango).
  - **Congelado (paso 0):** sólo el aventurero invoca; la quest debe ser de Gremio (`guild_tier` presente), activa y reclamada por él; el marcador es idempotente (re-invocar una ya marcada se rechaza, sin cobro). `entrench` exige `type: hold` y suma **+1 progreso una vez** al streak del reclamante ese tick (equiv. −1 tick; el marcador `entrenched` sólo guarda la unicidad, no se re-suma en ticks futuros; un tick sin ocupar resetea el streak y borra el bonus, como cualquier `hold`). `wager` (`type` cualquiera): al éxito **×2 sólo la esencia** (reputación intacta); un fallo de moneda Bronze bajo `wager` paga **0** (consuelo perdido, el "nada" del doble-o-nada); no añade lógica al fallo/expiración de la quest. `insure` reembolsa `quest.stake` al fallo/expiración **antes** del chequeo de muerte por esencia 0 (el reembolso puede evitar la muerte); `insure` y `wager` son marcadores independientes (asegurar protege el stake, apostar sólo afecta la recompensa).
- Fase 9: spawn de quests de Gremio como arriba, tras venganza y rubber-band.
- Fase 11: la crónica emite, en orden de resolución dentro de la celda de eventos del aventurero, `santuario` (tras `move`), `gremio:<tier>@<fuerza>` (por tablón de Gremio resuelto con éxito, tras `botín`), `capacidad:+<nombre>` (por capacidad recién otorgada) y `rango:<fuerza>=<tier>` (sólo cuando una completación eleva el tier más alto poseído con esa fuerza).

**Parámetros nuevos (`era.yml`, bloque `guild`; primer paso, calibrables en sandbox):** `thresholds` `{bronze 0, silver 10, gold 25, platinum 70}`; `platinum_condition.force_regions_max 1`; `objectives.travel_deadline` `{3,5,7,10}` / `objectives.hold_n_ticks` `{1,2,3,5}`; `rewards.essence` `{bronze_hit 1 / bronze_miss 2, silver 3, gold 8, platinum 25}` y `rewards.reputation` `{bronze 1 (moneda), silver 1, gold 5, platinum 15}`; `stakes` por tier (reutilizan `menor`/`mayor`); `capabilities.costs` `{swift_march 1, sanctuary 2, insure 1, entrench 2, wager 0}`, `capabilities.sanctuary_ticks 2`, `capabilities.swift_march_hops 2`; `capabilities.shared` `{bronze swift_march, silver sanctuary}` y `capabilities.signature` `{force-1 insure, force-2 entrench, force-3 wager}`. Watch de calibración: esencia de Gremio es farmeable (Gold repetible; Platinum no, por rareza de la condición heroica) — su impacto queda acotado por el techo verificable del aventurero (replay contrafactual), no por el spawn.

**Esquema nuevo:** `adventurer.guild` (por fuerza: `completed` = tiers completados; rango derivado) y `adventurer.sanctuary_until` (tick); `quest.type` acepta `travel`/`hold` y `quest.params` gana `guild_tier` + marcadores `insured`/`wagered`/`entrenched`. `capabilities` (lista plana) sin cambio de forma.

## Boundaries

**Dentro de v1:**
- 3 agentes + humano-aventurero por interfaz idéntica
- Catálogo de movimientos base + 5 acciones de capacidad del Gremio, orden de resolución de 11 fases
- Motor de misiones determinista con piel generativa; Issues como tablón
- Eras como unidad de eval, cadencia parametrizable
- Replay contrafactual como verificación del techo de poder humano
- Dataset = `/moves/` + `/chronicle/`; `/lore/` excluido por construcción

**Fuera de v1 (explícito):**
- Niebla de guerra → v2, sobre ramas-vista por entidad
- Delegación real de subagentes → v2: spawn como movimiento, upkeep diegético, profundidad máx 1, cap k por fuerza
- Fuerzas como emisoras de encargos → v2, con catálogo cerrado
- Herencia al morir → expansión candidata, solo con datos
- Asimetría mecánica (facciones/archetypes) → v3, solo con datos de balance
- NPCs con agencia → v2, solo deterministas
- Bot Telegram → v2
- Múltiples recursos → extensión de schema cuando haya justificación de señal
- Frontend espectador — el repo es la interfaz en v1

**Restricciones operativas:**
- GitHub Apps declaradas (una app, tres tokens), repo público desde el inicio, marcado sandbox
- Rate limits API (5000/h/token) dimensionan cadencia mínima
- Latencia Actions (~30–60s) es piso del tick, absorbida por la ventana

## Three Gaps

**Knowledge gap:** intensidad correcta del rubber-band; ventana mínima estable; colusión tácita con n=3; si permadeath sin herencia sostiene participación humana; tasa de intercambio de combate que evite estancamiento o bola de nieve.

**Alignment gap:** deriva hacia juego-espectáculo. Control: cada mecánica nueva se justifica como señal medible de capacidad de agente o se rechaza. El techo de poder del aventurero es restricción de calibración permanente, ahora verificable por contrafactual.

**Effects gap:** movimientos malformados en cadena degradando eras a partidas NPC; costos de inferencia sin presupuestar; aventurero cazado a extinción. Control: % ticks NPC por era como health check; presupuesto de tokens en `era.yml`; esperanza de vida del aventurero como métrica de calibración.

## Inventario de construcción

**Diseño cerrado. Ningún vacío de especificación restante — ambigüedad nueva detona pregunta, nunca invención (regla de CLAUDE.md).**

1. ~~Catálogo de movimientos~~ — **congelado**
2. ~~Fórmulas de resolución~~ — **congelado**
3. ~~Mapa inicial~~ — **congelado** (12 regiones, 3 brazos + anillo, generación por script)
4. `era.yml` completo con valores iniciales — mecánico: todos los parámetros ya tienen valor declarado en este documento
5. Workflow de resolución (main effort), testeable localmente con fixtures
6. Cliente de agente (máquina local en v1)
7. Tres personas (media página c/u, solo carácter)
8. Rúbrica del eval, definida antes de la primera era

**Orden:** 2→3→4→5 con movimientos hardcodeados (tracer bullet), agentes al final.

## Apéndice — Plantilla de chronicle (contrato de parsing, fase 11)

Formato congelado de `/chronicle/tick-<N>.md`. Tablas pipe de Markdown con encabezados fijos; las siete secciones se emiten siempre (tabla sin filas si no hay datos); las líneas clave-valor (`Sustituciones`, `Coronación`, `Fin de era`) se emiten siempre, con `-` cuando están vacías. Parámetros como pares `clave=valor` ordenados alfabéticamente, unidos por espacio. Porcentajes con un decimal. El lore NO forma parte de este artefacto: se genera fuera del motor y jamás se lee.

```markdown
# Crónica — era <E> — tick <N>

## Órdenes

| actor | origen | # | acción | parámetros | estado |
|---|---|---|---|---|---|
| <actor> | agent|human|npc | <índice> | <acción> | <k=v ...> | válida / rechazada: <razón> |

Sustituciones: <actor> (<razón>)[; ...] | -

## Combates

| región | atacante | unidades_atq | defensor | unidades_def | poder_def | ganador | sup_atq | sup_def |
|---|---|---|---|---|---|---|---|---|

## Colisiones

| región | orden_por_hash |
|---|---|
| <región> | <actor>, <actor>, ... |

## Economía

| fuerza | rendimiento | esencia |
|---|---|---|

## Quests

| id | evento | tipo | tier | detalle |
|---|---|---|---|---|
| <id> | spawn / resuelta / expirada | <tipo> | <tier> | deadline=<T> <k=v ...> / - |

## Supremacía

| fuerza | regiones | pct | streak | k_restante |
|---|---|---|---|---|

Coronación: <fuerza> | -
Fin de era: coronation | tick_cap | -

## Aventurero

| id | posición | esencia | reputaciones | eventos |
|---|---|---|---|---|
| <id> | <región> / † <región> | <esencia> / - | force-1:<n> force-2:<n> ... / - | spawn / move:<región> / botín:+<n> / muerte:<fuerza|-> [; ...] / - |
```

Filas de Órdenes ordenadas por actor y luego índice; batch sin órdenes emite una fila `no-op`. Combates: una fila por ronda F1 en orden de escalera. Colisiones: participantes en el orden del hash sembrado (fase 4). Quests: primero spawns, luego resueltas/expiradas, cada grupo ordenado por id. Supremacía y Economía: una fila por fuerza, orden léxico. Aventurero: vivos primero (orden léxico), luego muertos del tick.
