# Crónica — era 1 — tick 1

## Órdenes

| actor | origen | # | acción | parámetros | estado |
|---|---|---|---|---|---|
| adventurer-sago | human | 0 | move_units | count=1 from=arm-2-b to=capital-2 | válida |
| force-1 | agent | 0 | attack_region | count=3 from=arm-1-a to=ring-1 | válida |
| force-2 | agent | 0 | attack_region | count=2 from=ring-1 to=arm-1-b | válida |
| force-2 | agent | 1 | move_units | count=9 from=capital-2 to=ring-2 | rechazada: move_units: 9 units exceed the 3 available in capital-2 |
| force-3 | npc | 0 | fortify | region=capital-3 | válida |

Sustituciones: force-3 (no batch submitted)

## Combates

| región | atacante | unidades_atq | defensor | unidades_def | poder_def | ganador | sup_atq | sup_def |
|---|---|---|---|---|---|---|---|---|
| arm-1-b | force-2 | 2 | force-1 | 1 | 3 | force-1 | 0 | 1 |
| ring-1 | force-1 | 3 | force-2 | 1 | 1 | force-1 | 2 | 0 |

## Colisiones

| región | orden_por_hash |
|---|---|
| arm-1-b | force-2 |
| ring-1 | force-1 |

## Economía

| fuerza | rendimiento | esencia |
|---|---|---|
| force-1 | 6 | 9 |
| force-2 | 8 | 12 |
| force-3 | 4 | 8 |

## Quests

| id | evento | tipo | tier | detalle |
|---|---|---|---|---|
| raid-1-1 | spawn | raid | minor | deadline=9 force=force-2 region=arm-2-a |
| blockade-0-2 | expirada | blockade | minor | - |
| raid-0-1 | resuelta | raid | minor | - |

## Supremacía

| fuerza | regiones | pct | streak | k_restante |
|---|---|---|---|---|
| force-1 | 4 | 33.3% | 0 | 10 |
| force-2 | 5 | 41.7% | 0 | 10 |
| force-3 | 3 | 25.0% | 0 | 10 |

Coronación: -
Fin de era: -

## Aventurero

| id | posición | esencia | reputaciones | eventos |
|---|---|---|---|---|
| adventurer-sago | capital-2 | 5 | force-1:0 force-2:0 force-3:0 | move:capital-2 |
