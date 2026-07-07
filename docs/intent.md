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
| Influencia sobre el desenlace | Canales legítimos: comercio por reputación (con cap de volumen por tick en `era.yml`), ejecución de quests rubber-band menores, obstrucción posicional, botín póstumo. Kingmaking permitido dentro de caps |
| Techo verificable | Replay contrafactual post-era: movimientos humanos sustituidos por política NPC. Si el ganador cambia, el humano decidió la era → caps se aprietan. Métrica: delta de resultado, no impresión |
| Legado | Al coronar una fuerza, si la reputación del aventurero supera umbral: título diegético en chronicle/graveyard, persistente trans-era, valor mecánico cero. Pago en memoria del mundo, no en poder |

## Decisiones congeladas — misiones

| Rama | Decisión |
|---|---|
| Fuentes | (1) Motor rubber-band por umbrales de dominancia; (2) eventos de mundo por triggers de estado (tabla en `era.yml`); (3) fuerzas como emisoras: v2, requiere catálogo cerrado. El humano nunca crea misiones |
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
| `recruit` | fuerzas | region, count | región propia; esencia ≥ count × costo | −esencia, +unidades |
| `fortify` | fuerzas | region | región propia; esencia ≥ costo | +1 fortificación, persistente, cap F |
| `accept_quest` | según eligibility | quest_id | eligibility, cupo, stake, posición | reclamo; stake cobrado |
| `spawn_adventurer` | humano | name, origin | sin entidad viva del username; origin spawneable | entidad con baseline |
| `claim_loot` | aventurero | region | presente en región con botín activo | +botín; botín extinguido |

`move_units` / `attack_region` separados: intención explícita — el harness lee agresión declarada, no deducida.

**Orden de resolución del tick (regla de juego, congelada):**
1. Validación de schema + sustitución NPC
2. `spawn_adventurer`
3. `recruit`, `fortify` (esencia pre-tick)
4. Movimientos y ataques simultáneos — colisiones por fórmula con seed
5. Resolución de combates
6. `claim_loot`
7. Yield económico sobre propiedad post-combate
8. Resolución de objetivos de quests contra estado post-combate
9. Spawn de quests por triggers
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
- `poder_atacante = unidades_atacantes`; `poder_defensor = unidades_defensoras + F × bonus_fort`
- Atacante > defensor: toma la región con `atacante − defensor` supervivientes; defensor eliminado
- Atacante ≤ defensor: atacante eliminado; defensor pierde `max(0, atacante − F × bonus_fort)`
- Cada combate es aniquilación del perdedor. Traza auto-explicable; seed no toca combate; eras rápidas = más runs por presupuesto

**F2 — Colisión multi-parte:**
- Orden de resolución por pares derivado de `hash(seed, tick, region)` — nunca por orden de PR ni ID de fuerza
- Cada par resuelve con F1; el superviviente enfrenta al siguiente
- Ataque espejo (A→B y B→A entre las mismas regiones): ambos proceden contra guarniciones reducidas — unidades comprometidas al ataque no defienden. El all-in es apuesta real; señal de gestión de riesgo

**F3 — Valores iniciales (`era.yml`, calibración empírica declarada como knowledge gap):**
- Yield: 1 esencia/región/tick; capitales: 2
- Recruit: 2 esencia/unidad. Fortify: 5 esencia, bonus_fort 2, cap F=3
- Baseline aventurero: 5 esencia. Cap comercio: 3 esencia/tick
- Rubber-band: >45% regiones. K coronación: 10 ticks. Cap de era: 100 ticks

**F4 — Aventurero en combate:**
- No bloquea captura: coexiste como no-combatiente; la región cambia de dueño sin combatirlo
- Muere solo por declaración explícita: `attack_region` con `target: adventurer` — cuesta una orden del batch
- Matarlo paga reputación negativa con las demás fuerzas (parámetro en `era.yml`). Caza posible, explícita en traza, con precio diplomático

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

Umbrales: comercio ≥ +10, refugio ≥ +25, encargos (v2) ≥ +40. Reputación fuerza↔fuerza: rechazada en v1 — los agentes se modelan por conducta, sin mecánica adicional

**Plantilla de chronicle (contrato del harness, fase 11, tablas crudas sin prosa — un artefacto, tres consumidores: harness/regex, humano/render, LLM de lore/input):** secciones fijas: Órdenes (fuerza, origen agent|human|npc, válidas), Combates, Colisiones (orden por hash), Economía, Quests (spawn/resueltas/expiradas), Supremacía (regiones, %, streak, K restante), Aventurero (posición, esencia, reputaciones, eventos)



```
/world/
  era.yml            # cadencia, cap de ticks, seed, K de coronación,
                     # baseline de recursos, quema de loot, M de disipación,
                     # umbrales de reputación, tabla de triggers, presupuesto tokens,
                     # caps de órdenes por tick, cap de comercio aventurero/tick,
                     # costos recruit/fortify, cap F de fortificación
  tick.txt           # puntero atómico de tick
  regions/<id>.yml   # dueño, recursos base, unidades presentes, fortificación, botín activo
  forces/<id>.yml    # persona ref, esencia, unidades
  forces/adventurer-<handle>.yml  # controller, esencia, reputación, capacidades, quest personal
  graveyard/         # entidades muertas + títulos; sobrevive el reset de era
  quests/active/<id>.yml          # eligibility, objetivo, reward, stake, deadline, cupo
  quests/resolved/
/moves/tick-<N>/<force>.yml       # batches consumidos, preservados como traza
/lore/                            # write-only, LLM, jamás leído por adjudicación
/chronicle/tick-<N>.md            # resumen mecánico por tick, generado por árbitro
```

## Boundaries

**Dentro de v1:**
- 3 agentes + humano-aventurero por interfaz idéntica
- Catálogo de 7 movimientos, orden de resolución de 11 fases
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
