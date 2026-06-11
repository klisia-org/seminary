# Calendário Acadêmico

O calendário acadêmico gerencia períodos letivos, datas importantes e regras de prazos. Todos os aspectos são controlados pelo Desk.

## Visão geral

O calendário acadêmico tem uma estrutura em camadas:

### Ano Letivo:

Contém períodos letivos. Pode ser usado para disparar taxas específicas. On the Academic Term, you can see if and when Invoices for "New Academic Year" (NAY) were generated.

### Período Letivo:

Os períodos letivos não podem se sobrepor. Each term must be wholly contained in an Academic Year, with start and end dates within the Academic Year. Academic Terms may be used to trigger specific fees, and you can see if and when Invoices for "New Academic Term" (NAT) were generated.
Each academic term defines the structure of a teaching period: start and end dates and withdrawal deadlines (dates for each [Withdrawal Rule](withdrawal.md#withdrawal-rules)). Additionally, Academic Terms are used throughout the system as "anchors" to calculate other events, such as enrollment and grading periods (under Seminary Settings).

### Regras da Janela de Inscrição

Course enrollment windows control **when a Course Schedule opens and closes for
student enrollment** (plus a third, informational _grade close_ deadline). They
are defined once, seminary-wide, under **Seminary Settings → Enrollment Window
Rules**, and applied to every Course Schedule automatically.

Each of the three windows is set with an **anchor** plus an **offset in days**:

- **Anchor** — the reference date the offset counts from:
  - `term_start` / `term_end` — the [Academic Term](#academic-term)'s start / end date.
  - `classes_start` / `classes_end` — _this_ Course Schedule's own start / end date.
- **Offset (days)** — how many days from the anchor. **Negative = before** the
  anchor, positive = after, `0` = on the anchor itself.

The three windows:

| Window               | What it controls                                                                                                                                                        |
| -------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Enrollment Open**  | When the Course Schedule moves from _Draft_ to _Open for Enrollment_ — students can enroll.                                                             |
| **Enrollment Close** | When it moves from _Open for Enrollment_ to _Enrollment Closed_ — enrollment stops.                                                                     |
| **Grade Close**      | Informational deadline for submitting final grades. After it passes, instructors of courses still being graded receive reminder emails. |

> **Leave an anchor blank to opt out** of that window. With no Enrollment Open
> rule (and no override), a new Course Schedule opens for enrollment
> _immediately_ on creation instead of waiting in Draft.

**Auto-advance.** When **Auto-advance Course Schedule states** is enabled in
Seminary Settings, a daily job promotes each Course Schedule as its dates arrive
(Draft → Open for Enrollment → Enrollment Closed). With it off, the dates are
still computed and shown, but staff move courses through the states by hand.

**Per-course overrides.** The seminary-wide rule is only the default. Any
individual Course Schedule can override a date in its **Enrollment Dates**
section (_Enrollment Open Date Override_, _Enrollment Close Date Override_,
_Grade Close Date Override_) — the override always wins for that course. Use it
for a late-added course or a one-off exception.

#### Exemplos práticos

Each example lists the values to enter under **Seminary Settings → Enrollment
Window Rules**.

##### Example 1 — All courses in a term open and close together

Everyone enrolls during a single term-wide window, no matter when each class
actually meets.

| Setting                                 | Value                                                                                                        |
| --------------------------------------- | ------------------------------------------------------------------------------------------------------------ |
| Âncora de Matrícula Aberta              | `term_start`                                                                                                 |
| Dias da Âncora para Abrir Inscrições    | `-14` &nbsp;_(two weeks before the term starts)_                      |
| Âncora para Fechar Inscrições           | `term_start`                                                                                                 |
| Dias da Âncora para Encerrar Inscrições | `7` &nbsp;_(one week after the term starts — a short add/drop grace)_ |

##### Example 2 — Each course opens relative to its own start date

Useful when classes within a term begin on different dates (e.g. intensives or
modular courses).

| Setting                                 | Value                                                                                                    |
| --------------------------------------- | -------------------------------------------------------------------------------------------------------- |
| Âncora de Matrícula Aberta              | `classes_start`                                                                                          |
| Dias da Âncora para Abrir Inscrições    | `-30` &nbsp;_(enrollment opens a month before each class begins)_ |
| Âncora para Fechar Inscrições           | `classes_start`                                                                                          |
| Dias da Âncora para Encerrar Inscrições | `0` &nbsp;_(closes the day the class starts)_                     |

##### Example 3 — Close enrollment before the term ends

| Setting                                 | Value                                                                                                |
| --------------------------------------- | ---------------------------------------------------------------------------------------------------- |
| Âncora de Matrícula Aberta              | `term_start`                                                                                         |
| Dias da Âncora para Abrir Inscrições    | `0`                                                                                                  |
| Âncora para Fechar Inscrições           | `term_end`                                                                                           |
| Dias da Âncora para Encerrar Inscrições | `-10` &nbsp;_(no new enrollments in the term's last 10 days)_ |

##### Example 4 — A grading deadline after classes end

Pair any of the windows above with a grade deadline:

| Setting                              | Value                                                                                                 |
| ------------------------------------ | ----------------------------------------------------------------------------------------------------- |
| Âncora de fechar notas               | `classes_end`                                                                                         |
| Dias da Âncora de Fechamento de Nota | `14` &nbsp;_(final grades due two weeks after the class ends)_ |

Instructors of any course still in _Enrollment Closed_ or _Grading_ past this
date receive automatic reminder emails.

##### Example 5 — No automatic windows (open immediately)

Leave **all anchors blank**. Every new Course Schedule lands directly in _Open
for Enrollment_ and stays there until staff close it manually. Choose this if
your seminary manages enrollment timing by hand or course-by-course.

##### Example 6 — One course needs an exception

Keep the seminary-wide rule, but for a single late-added Course Schedule, open
its **Enrollment Dates** section and set **Enrollment Open Date Override** to the
date you want. That course ignores the seminary rule; all others are unaffected.

## Conceitos-chave

- **Período Letivo** — a unidade de tempo fundamental (semestre, trimestre, semestre)
- **Resolvedor de Regras de Datas** — lógica configurável para calcular prazos acadêmicos em relação às datas do período letivo
- **Enrollment Windows** — seminary-wide anchor + offset rules that open and close Course Schedules for enrollment (overridable per course)
- **Regras do período letivo** — a configuração de prazos e políticas fica no nível do período, permitindo regras diferentes por período
