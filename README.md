# Obras de salida

**¿Los alcaldes del Perú dejan la plata de obras para el final de su gestión? ¿Y qué pasa con esas obras cuando entra el siguiente?**

Desde que no pueden reelegirse, los alcaldes gastan 37% más en obras entre la elección y su salida que en los mismos meses de otros años. Cuando se van, 3 de cada 10 obras a medias se quedan sin pagar.

- Dashboard: https://nicosil02.github.io/obras-de-salida/
- Reel: (enlace pendiente)
- Publicación en LinkedIn: (enlace pendiente)

## Descripción

El proyecto sigue mes a mes los pagos de cada obra de las casi 1,900 municipalidades del Perú entre 2007 y 2026. Compara los meses de campaña y de salida del alcalde con los mismos meses de otros años, en soles de 2022, y mide cuántas obras que estaban a medias dejan de recibir pagos cuando cambia el alcalde.

El dashboard permite buscar un distrito y elegir departamento, provincia, tamaño de la municipalidad, gestión y qué medir (gasto, número de obras o gasto por tipo de obra). Tiene un mapa por distrito, el gasto año por año, el abandono de obras en cada cambio de alcalde y el abandono según quién entra.

## Fuentes

| Datos | Fuente | Uso |
|---|---|---|
| Gasto público 2007-2026, devengado mensual | MEF, [Datos Abiertos](https://datosabiertos.mef.gob.pe/), archivos `{año}-Gasto` | Pagos de cada obra de cada municipalidad |
| Inversiones públicas | MEF, `DETALLE_INVERSIONES` y `CIERRE_INVERSIONES` | Nombre, costo, ubicación y tipo de cada obra |
| Transferencias a municipalidades | MEF, `{año}-Transferencias` | Control en la regresión (canon, FONCOMUN) |
| Elecciones municipales 2006-2022 | ONPE, resultados por mesa en la [Plataforma Nacional de Datos Abiertos](https://www.datosabiertos.gob.pe/) | Ganador y partido en cada distrito |
| Alcaldes y regidores electos 2014-2022 | JNE, [autoridades electas](https://www.datosabiertos.gob.pe/dataset/autoridades-electas-en-procesos-electorales-jurado-nacional-de-elecciones) | Relación del nuevo alcalde con la gestión que sale (por DNI) |
| Obras paralizadas | Contraloría, [informe a junio de 2026](https://www.gob.pe/institucion/contraloria/informes-publicaciones/8489152-informe-de-obras-paralizadas-en-el-territorio-nacional-a-junio-de-2026) | Contexto |
| IPC de Lima Metropolitana | BCRP, [serie PN38705PM](https://estadisticas.bcrp.gob.pe/estadisticas/series/mensuales/resultados/PN38705PM/html), en `datos/originales/ipc_lima.csv` | Pasar el gasto a soles de 2022 |
| Límites distritales | INEI, versión de GeoGPS Perú en [nicosil02/Dashboard](https://github.com/nicosil02/Dashboard/tree/main/Distrital) | Mapa |

## Metodología

- **Gasto en obras.** Devengado mensual de los proyectos de inversión de cada municipalidad. Las municipalidades provinciales se asignan al distrito capital.
- **Soles de 2022.** Todo el gasto se corrige por inflación con el IPC de Lima del BCRP.
- **Campaña y salida.** Se compara junio a diciembre del año de elecciones (2010, 2014, 2018, 2022) con los mismos meses del año anterior. No se compara con el primer año del alcalde, porque ese año se gasta poco por el arranque de la gestión y eso inflaría la diferencia.
- **Número de obras.** Obras distintas que recibieron al menos un pago en el año.
- **Tipo de obra.** Gasto de inversión (adquisición de activos no financieros) según la función del clasificador presupuestal, desde 2009.
- **Obra a medias abandonada.** Obra con pagos en los 6 meses previos al 1 de enero, con menos de 80% de su costo pagado, que no recibe ningún pago en los 24 meses siguientes. Se compara enero de los años de cambio de alcalde (2011, 2015, 2019, 2023) con enero de años sin cambio (2009, 2013, 2017, 2021).
- **Quién entra.** Con el DNI de los alcaldes y regidores electos del JNE se marca si el nuevo alcalde es del mismo partido que el que sale, si fue regidor de la gestión que sale o si es un exalcalde que vuelve.
- **Regresión.** Panel municipalidad por mes, 2007-2026, con el gasto en soles de 2022 como índice (100 = promedio de cada municipalidad), efectos fijos de municipalidad, año y mes calendario, y errores agrupados por municipalidad. Así cada mes se compara con el mismo mes de otros años y no pesa el gasto de diciembre por el cierre del año fiscal. Desde 2015, cuando se prohibió la reelección inmediata, el gasto sube 18% en la campaña (junio a setiembre, IC 95% ±3.3), 37% entre la elección y la salida (octubre a diciembre, ±7.1) y cae 15% en los primeros 3 meses del nuevo alcalde (±3.4). En 2007-2014 la campaña sube 8% (±4.1) y la salida no tiene un efecto claro (+4%, ±7.7).

## Hallazgos

1. **Gastan más cuando ya se van.** Desde 2015 el gasto en obras sube 18% en la campaña y 37% entre la elección y la salida del alcalde, frente a los mismos meses de otros años. Antes de 2015, cuando el alcalde podía reelegirse, casi no había ese salto final. De junio a diciembre de 2022 las municipalidades pagaron S/ 14,971 millones en obras, 30% más que en los mismos meses de 2021 (soles de 2022), y 63% de los distritos gastó más.
2. **Cuando cambia el alcalde, más obras se quedan a medias.** En enero de 2023, 28% de las obras a medias (3,511) no volvió a recibir pagos en dos años. En enero de 2021, sin cambio de alcalde, fue 18%. La diferencia se repite en 2011, 2015 y 2019.
3. **Importa quién entra.** Si el nuevo alcalde es del mismo partido o fue regidor de la gestión que sale, se abandona entre 21% y 24% de las obras a medias. Si no tiene relación, 28%. Si vuelve un exalcalde rival, 32% (cambios de 2019 y 2023).

Además, crecen más las obras que se ven. De junio a diciembre de 2022 el gasto en cultura y deporte (estadios, losas) fue 2.5 veces el de los mismos meses de 2021 (1.9 veces en 2018), mientras que el de agua y desagüe subió 7% (y bajó 17% en 2018).

## Limitaciones

- Es una asociación, no una prueba de causalidad. Una obra puede dejar de recibir pagos porque terminó sin registrar su cierre o por problemas técnicos, no solo por decisión del nuevo alcalde.
- El primer año de cada alcalde se gasta poco, así que comparar el último año con el primero exagera el efecto. Por eso se compara con el año anterior y con los mismos meses de otros años.
- La gestión 2023-2026 sigue en curso (datos hasta septiembre de 2026).
- En 2007 muchas municipalidades entraron al SIAF a mitad de año; por eso esa gestión usa solo las que reportaban desde enero.
- Elecciones y autoridades se cruzan con los distritos por nombre y entre 1% y 3% no calzan. Se usa la elección original, no las nuevas elecciones ni las complementarias. Un partido que cambia de nombre cuenta como otro partido.
- El JNE publica autoridades con DNI solo desde 2014, así que la relación entre alcaldes cubre solo los cambios de 2019 y 2023. Dos de los grupos son chicos (31 y 83 municipalidades).
- 17 distritos creados entre 2020 y 2022 no tienen polígono en el mapa del INEI. Su gasto entra en los totales pero no se dibujan.
- El gasto por tipo de obra no se puede contar en número de obras, porque el catálogo de inversiones del MEF solo cubre a la mitad de las obras antiguas.

## Cómo reproducir

Requiere Python 3.12 o más reciente.

```bash
pip install -r requirements.txt
```

Los datos procesados del MEF (`datos/procesados/gasto` y `datos/procesados/transferencias`) ya están en el repositorio, porque los archivos originales pesan entre 3 y 10 GB por año. Para regenerar el dashboard basta con descargar los archivos chicos:

```bash
python scripts/obtener_datos.py inversiones   # DETALLE y CIERRE_INVERSIONES
python scripts/obtener_datos.py elecciones    # ONPE 2006-2022 y JNE
python scripts/obtener_datos.py limites       # mapa distrital del INEI
```

El Excel del informe de obras paralizadas de la Contraloría se descarga a mano desde el enlace de fuentes y se guarda como `datos/originales/obras_paralizadas_jun2026.xlsx`.

Luego:

```bash
python scripts/procesar_datos.py    # elecciones, relaciones entre alcaldes y panel de obras
python scripts/analizar_datos.py    # regresiones -> datos/procesados/resultados_ejecucion.json
python scripts/datos_dashboard.py   # docs/datos.json, docs/mapa.json y docs/distritos.geojson
```

Para ver el dashboard en local:

```bash
python -m http.server 8765 -d docs
```

Para rehacer el gasto desde cero (lento, descarga cientos de GB):

```bash
python scripts/obtener_datos.py gasto <carpeta_temporal> 2007 2008 ... 2026
python scripts/obtener_datos.py transferencias <carpeta_temporal> 2004 2005 ... 2026
```

## Estructura

```
scripts/obtener_datos.py    descarga y reducción de los datos abiertos
scripts/procesar_datos.py   cruce de elecciones, autoridades y obras
scripts/analizar_datos.py   abandono de obras y regresiones
scripts/datos_dashboard.py  archivos que lee el dashboard
docs/                       dashboard (GitHub Pages)
reel/                       escenas del reel
```

## Uso de inteligencia artificial

Usé Claude Code (Anthropic) como asistente de programación para escribir y depurar los scripts de descarga y procesamiento, el código del dashboard (D3.js) y para revisar la redacción. Las preguntas, la definición de los indicadores, la verificación de las cifras contra las fuentes oficiales y las conclusiones son mías. La voz del reel es mi propia voz clonada con un modelo de texto a voz a partir de una grabación mía, y el reel lo indica.
