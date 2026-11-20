# M2 — Protocolo de calidad contractual N4/N12 (FG-1)

**Versión textual para agentes** · Transcripción extraída del PDF original de cuatro páginas · 2026-11-20. Los anexos YAML del mismo directorio contienen el esquema editable.

---
M2 · Protocolo de calidad contractual N4 / N12
AI-GEN · C2Pro · FG-1 | Edición de diseño | 20/11/2026
Alcance: metodología y plantillas; sin ejecución facturable, despliegue ni acceso a contratos privados.
## 1. Supuestos y separación de capacidades
- Base fijada: código UAT 799ce531; dictamen d7c63ce2; corrección CORE #1259/7022543946. El prompt N4 v1 solo
  produce riesgos y referencias pendientes; no exigirle todavía recall de obligaciones/hechos.
- N12 real: primera revisión con proyección N2 completa cuando esté disponible; segunda revisión focal, incapaz de
  certificar recall global; los hallazgos citados quedan UNASSESSED hasta revisión humana. Distinguir respuesta cruda,
  estado funcional y juicio experto.
- Unidad de análisis: elemento jurídico-operativo atómico, no número de líneas ni candidatos. Un hallazgo puede
  enlazar varias cláusulas/anexos; dos efectos contractuales independientes requieren dos registros.
## 2. Oráculo humano independiente y a ciegas
Preparación. El propietario elige y autoriza contrato principal, anexos y segundo contrato held-out; no se designan
aquí. Registrar SHA-256 de cada PDF, revisión, índice de páginas PDF (1-based) y página impresa (si difiere), anexos
presentes/ausentes, idioma y legibilidad. Sellar prompt/modelo/configuración/commit y reglas de adjudicación antes
de revelar resultados.
Dos anotaciones ciegas. A y B, ajenos a la implementación, leen independientemente el original completo + anexos,
sin salidas de N4/N12 ni notas entre sí. Anotan cada riesgo, obligación, hito, garantía, penalización, pago, exclusión y
responsabilidad; titular, sujeto obligado/beneficiario, modalidad o condición, cláusula y página exacta, cita literal,
materialidad y razón EPC. Añaden evidencia negativa/indeterminada y dependencias entre cláusulas.
Conciliación. Comparar ID semántico, polaridad, alcance, partes, excepción y vigencia. Desacuerdos de inclusión, cita
o materialidad se deciden por relectura del PDF; un tercer adjudicador independiente resuelve empates, sin conocer
la predicción. Guardar las tres versiones y motivo. Reportar acuerdo previo (inclusión y kappa ponderado de
materialidad); si solo hay un anotador, acuerdo interanotador = NOT_VERIFIED.
Cotejo posterior. Congelar oráculo; revelar candidatos y hacer matching 1:1 auditable. TP solo con contenido
sustantivo y condiciones equivalentes. Hallazgo sin soporte = FP; elemento ausente = FN; duplicado redundante =
FP adicional. No aceptar el acierto de un porcentaje agregado como sustituto del expediente de cada FN crítico.
---
Diseño de muestra y métricas
## 3. Estratificación predefinida
Construir un censo de elementos materiales del documento (sin forzar cuotas artificiales), y etiquetar las ocho
familias. Registrar subgrupos cruzados: crítico / alto / otro, documento principal / anexo, fuente directa / referencia
cruzada, texto accesible / escaneado, fecha absoluta / plazo relativo, cifra inequívoca / formatos ambiguos, norma
general / excepción, y cláusulas de terminación. Mostrar denominadores reales, incluidos estratos vacíos.
  Caso adversarial mínimo                  Condición que debe acertarse para un TP
  Excepción / carve-out                    Aplicabilidad, excepciones a excepción, alcance y prioridad documental
  Anexo referido / ausente                 Número y versión de anexo; relación precisa; ausencia ≠ inexistencia
  Plazo relativo                           Hito detonante, días naturales/hábiles, suspensión y límites
  Importe heterogéneo                      Separadores decimales, monedas, porcentajes, topes, bases e impuestos
  Terminación                              Causa, preaviso, subsanación, efectos y responsabilidades subsistentes
## 4. Métricas obligatorias · informe por tipo × materialidad
Recall = TP / (TP + FN), denominador = elementos del oráculo adjudicado. Precisión = TP / (TP + FP), denominador =
salidas N4 válidas o no válidas cotejadas; informar duplicados y salidas NO VERIFICADAS por separado. Match 1:1.
Fidelidad al PDF original = citas literalmente verificadas en la página original indicada, revisión correcta / total de
citas expuestas en ese estrato (también contar las que faltan o no pueden localizarse). Reportar ORIGINAL_VERIFIED /
N2_ONLY / ORIGINAL_UNVERIFIED / INVALID. N2_ONLY no cuenta en el numerador. Para citas críticas utilizadas en
decisiones: 100 % verificadas o rotuladas inequívocamente como no verificadas (regla de seguridad, no tasa de
fidelidad).
Acuerdo en severidad (solo riesgos): aciertos de categoría exacta / riesgos con severidad de oráculo y N4
comparables; además acuerdo ±1 nivel y kappa cuadrático ponderado cuando sea estimable. UNKNOWN no equivale
a LOW; las obligaciones y hechos no tienen severidad automática.
Incertidumbre: incluir IC del 95 % Wilson (k,n, LI, LS) en cada celda no vacía, también proporciones de N12. Con n=20
independientes, 20/20 da IC ~83,9–100 %; 18/20 da ~69,9–97,2 %. No acredita 95 % de rendimiento poblacional ni
heterogeneidad EPC. Elementos de un mismo contrato están correlacionados: el IC por elemento es descriptivo, no
generalizable a contratos. Sin datos suficientes, N/A (n=0), nunca 0 %.
Cobertura: páginas y ventanas realmente examinadas / elegibles; motivo y procedencia por hueco; anexos ausentes
y páginas no extraíbles. La cobertura técnica declarada no es recall semántico.
---
N12, reutilización y control de sesgos
## 5. N12: oráculo adversarial y controles negativos
Definir seis familias de defectos × diez variantes cada una (60 diseños): omisiones; falsificación/desplazamiento de
cita; interpretación de excepciones y terminación; partes/alcance/responsabilidad; fechas/importes/cálculos;
materialidad y atribución de impacto. Cada variante se instancia solo con un pasaje real que lo permita, sin inventar
texto contractual. Añadir ≥2 controles limpios por familia; mantener clases y materialidades balanceadas. La plantilla
YAML contiene las 60 variantes y su ficha de instancia.
Procedimiento: sobre una copia de evaluación de N4, sembrar una sola alteración por ensayo, más algunos pares
predefinidos; registrar el elemento original y el delta exacto. Cegar N12 respecto de la etiqueta, dejar acceso a
fuente atestada y controlar si fue completa/focal/ausente. No alterar datos productivos. Variar orden con semilla
congelada; cada caso lleva su control negativo equivalente.
Medidas: sensibilidad de detección = defectos correctamente identificados con cita y explicación / defectos
sembrados evaluables; FP = acusaciones no respaldadas / controles limpios revisados; abstención justificada =
abstenciones con código de causa verificable / todas las abstenciones; abstención total = abstenciones / ensayos.
Separar defecto no visto, falsa denuncia, abstención válida y abstención vaga, por familia y materialidad, con IC 95
%. Una abstención fundada es segura pero no es detección.
Regla crítica provisional CORE: 100 % de falsificaciones críticas detectadas para PASS de N12; toda abstención crítica
impide PASS pleno y exige revisión; falso positivo crítico con cita inventada = FAIL. Si el primer pase no dispone de
fuente original atestada, N12 es NOT_VERIFIED / UNASSESSED, no OK semántico. Separar FG-1 (N4), FG-1b (N12).
## 6. Qué reutilizar de verdad (sobre 799ce531)
 Activos localizados                        Reutilización / hueco verificable
  n4_n12_real_ai_eval.py                     Scoring base y EXPECTED_OMISSIONS EPC-04/EPC-07; hoy 2 omisiones + 1 interpretación,
                                            fixture sintético y coincidencia de marcadores, no un oráculo de PDF real
  n4_n12_representative_eval.py              Preparación N2, trazas, presupuestos y pruebas adversariales; tiene llamadas facturables:
                                            NO ejecutar en diseño
  n4_n12_representative_gate.py              Reevaluación independiente y ledger; asume 9 cláusulas, 3 llamadas, modelo fijo y fuente
                                            sintética; parametrizar antes de FG-1, sin cambiar guardas
  src/golden/                                Patrón casos/baseline/regresión; actual orientado a Coherence y trayectorias, no a páginas
                                            originales ni matching contractual ciego
  N4 parser; N12 critique                    N4 verifica cita en proyección N2, no PDF original; N12 estado UNASSESSED protege HITL,
                                            pero exigir captura cruda + causa por hallazgo
Brecha mínima del evaluador (no código ahora): adaptador de importación YAML, localizadores PDF firmados,
mapping manual de oro↔predicción, deduplicación, agregador de IC, reporte FN crítico individual y prueba de
abstenciones; conservar fixture y ledger inmutables.
---
Límites, dictamen y decisión
## 7. Tabla de límites probatorios
 Evidencia                                   Conclusión permitida / no permitida
  SEC EX-99.1: 73 páginas, 24 ventanas,       Diagnóstico exploratorio de salida v1 y cobertura; no representatividad contractual EPC ni
 142 candidatos                              recall de hechos no pedidos
  50 citas exactas en N2; 92 sin literal      Solo 50 coincidencias de proyección declaradas y 92 no verificadas; NO inferir 92
 N2                                          invenciones, precisión, citas PDF o recall
  Sin JSON crudo ni referencias               No auditoría forense completa ni puntuar citas originales; motivo = evidencia ausente, no
 originales SEC                              fabricar un resultado
  Primer contrato + anexos                    FG-1 da prueba puntual de utilidad, no eficacia generalizable; independencia humana y
                                             auditoría de página imprescindibles
  Segundo contrato held-out                   FG-1c verifica transferencia fuera del corpus de desarrollo; dos contratos siguen siendo
                                             prueba piloto, no validación estadística sectorial
  N4 v1 / N12                                 N4: riesgos actuales; obligaciones/hitos etc. NOT_IN_SCOPE_V1. N12 requiere gate separado
                                             y revisión semántica humana
## 8. Riesgos de invalidez y mitigación
- Fuga / sobreajuste: segundo contrato y anexo sellados; anotadores separados; prohibir exposición a
  implementadores, elegir thresholds y prompt antes del resultado; publicar resultados por contrato, nunca solo media.
- Sesgo de anotación y prevalencia: desacuerdos antes de cotejo, adjudicación trazable, control negativo; estratos
  pequeños se marcan sin inferencia, no se rellenan por artificio.
- Procedencia: texto N2, PDF original, anexos, cambios y paginación no son intercambiables; SHA de cada fuente y
  estado ORIGINAL_UNVERIFIED explícito.
- Interferencia entre productos: no contar dos veces riesgos y hechos; no convertir obligación en RiskItem, Score o
   aprobación. Un PASS de código o presupuesto no prueba utilidad contractual.
## 9. Matriz de dictamen funcional FG-1 (fijar antes del ensayo)
 Veredicto                   Regla operativa
  PASS                        Oráculo válido; riesgo v1 evaluable; sin FN críticos; cada cita crítica verificable o correctamente rotulada no
                             verificada; sin severidad UNKNOWN→LOW; incidencias y cobertura expuestas; N12 por separado
  PASS_LIMITED                Hay omisión crítica identificada pero expuesta, mitigada por bloqueo/no decisión humana y sin falsa
                             seguridad; o estratos/held-out pendientes. Nunca equivaler a producto EPC certificado
  FAIL                        Omisión crítica oculta o no declarada; cita crítica falsa presentada como original; contaminación de fuente,
                             exposición aprobable indebida, falso éxito de cobertura o daño de control
  NOT_VERIFIED                No hay contrato autorizado, oráculo/adjudicación, ejecución real controlada, trazas, referencia verificable o
                             saldo/permiso necesarios
Dictamen de este entregable: GO para USAR EL PROTOCOLO en el diseño de FG-1; STOP para ejecutar FG-1, N12
facturable, merge o despliegue sin GO de CORE. La persona experta externa debe firmar cada FN crítico (ID, cláusula,
página, materialidad, consecuencia, mitigación, estado); QA técnico y usuaria/o final firman por separado.
Fuentes verificadas: docs/audits/C2PRO_FUNCTIONAL_CRITICAL_PATH_DICTAMEN_2026-11-19.md @ d7c63ce2; issue #1259
comentario 7022543946; prompt y arneses @ 799ce531; src/analysis/domain/ai_extraction.py y critique_extraction_use_case.py @
799ce531. Repositorio AI-Gen-AI/C2Pro.
