# Obras de salida. Informe fuente del reel

Nicolás Silva Andújar · Tarea 3 · Data Science con Python

Este informe es el texto fuente del reel. Reúne los hallazgos del proyecto [obras-de-salida](https://github.com/nicosil02/obras-de-salida). Las cifras salen de `docs/datos.json` y `docs/mapa.json`, que el dashboard calcula a partir de los datos abiertos del MEF, la ONPE y el JNE. Los datos de gasto llegan hasta septiembre de 2026 y cubren los pagos de obras de 1,891 municipalidades entre 2007 y 2026 (2007-2026).

## 1. Una obra en Lurigancho

En Lurigancho (Lima), el proyecto de mejoramiento y ampliación de la red de alcantarillado de la margen izquierda del río Rímac tiene un costo de S/ 8.55 millones (ocho millones y medio). Sigue registrada como activa en el banco de inversiones del MEF. Recibió su primer pago en marzo de 2022, año de elecciones municipales, y el último en diciembre de 2022. Para entonces se habían pagado S/ 3.80 millones, el 44% de su costo. En enero de 2023 entró el nuevo alcalde, y hasta septiembre de 2026 la obra no recibió ningún otro pago.

Los datos muestran que dejó de recibir pagos. No dicen por qué, ni que el nuevo alcalde la haya abandonado a propósito.

## 2. Gastan más cuando ya se van

Todo el gasto está en soles de 2022 (corregido por inflación con el IPC de Lima del BCRP). Las elecciones municipales son a inicios de octubre y el nuevo alcalde entra el 1 de enero.

Desde 2015 los alcaldes no pueden reelegirse. Desde entonces, frente a los mismos meses de otros años de la misma municipalidad, el gasto en obras sube 18% en los meses de campaña (junio a setiembre) y 37% entre la elección y la salida del alcalde (octubre a diciembre). En los primeros tres meses del nuevo alcalde cae 15%. Antes de 2015, cuando podían reelegirse, la campaña subía 8% y no había un salto claro después de la elección. Comparando octubre a diciembre con los mismos meses del año anterior, el gasto cambió +2% en 2010 y -9% en 2014, cuando el alcalde podía reelegirse, y +25% en 2018 y +38% en 2022, cuando ya no.

De junio a diciembre de 2022 las municipalidades pagaron S/ 14,971 millones en obras, 30% más que en los mismos meses de 2021. El 63% de los distritos gastó más.

## 3. Crecen más las obras que se ven

De junio a diciembre de 2022 el gasto en cultura y deporte (estadios, losas) fue 2.5 veces el de los mismos meses de 2021. En 2018 fue 1.9 veces. El gasto en agua y desagüe subió apenas 7% en 2022 y bajó 17% en 2018. Cultura y deporte es la función del clasificador del MEF que incluye estadios y losas deportivas.

## 4. Cuando cambia el alcalde, más obras se quedan a medias

Una obra a medias es una obra con pagos en los seis meses previos al 1 de enero y con menos del 80% de su costo pagado. Se considera abandonada si no recibe ningún pago en los 24 meses siguientes.

En enero de 2023, cuando entraron los nuevos alcaldes, el 28% de las obras a medias (3,511 obras) quedó sin pagos, es decir 3 de cada 10. En enero de 2021, sin cambio de alcalde, fue el 18%, menos de 2 de cada 10. La diferencia se repite en los cambios de 2011, 2015 y 2019.

## 5. Importa quién entra

Con el DNI de los alcaldes y regidores electos que publica el JNE se puede ver la relación del nuevo alcalde con la gestión que sale. En los cambios de 2019 y 2023:

| Quién entra | Obras a medias abandonadas |
|---|---|
| Otro partido, pero fue regidor de la gestión que sale | 21% |
| Del mismo partido que el que sale | 24% |
| Otro partido y sin cargo previo | 28% |
| Vuelve un exalcalde rival | 32% |

## 6. Conclusión

Los alcaldes aceleran el gasto en obras cuando ya se van, y muchas de esas obras quedan a medias. Cada distrito puede verse en el dashboard: https://nicosil02.github.io/obras-de-salida/

## Fuentes

- MEF, Datos Abiertos: gasto devengado mensual 2007-2026 y banco de inversiones.
- BCRP: IPC de Lima Metropolitana (serie PN38705PM).
- ONPE: resultados de las elecciones municipales 2006-2022.
- JNE: autoridades electas 2014-2022.

## Limitaciones

- Una obra puede dejar de recibir pagos porque terminó sin registrar su cierre o por problemas técnicos, no solo por decisión del nuevo alcalde.
- Es una asociación, no una prueba de causalidad.
- La gestión 2023-2026 sigue en curso.
- La comparación por meses es más justa que comparar el último año con el primero, porque el primer año de cada alcalde se gasta poco por el arranque.
