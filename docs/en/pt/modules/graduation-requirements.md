# Requisitos de Graduação

O Program Audit sempre respondeu à pergunta _"este estudante obteve
créditos suficientes e foi aprovado nas disciplinas obrigatórias?"_ Mas muitos seminários formam
estudantes com base em uma lista mais longa: presenças na capela, entrevistas de ordenação,
cartas de recomendação, declarações doutrinárias, horas de estágio, uma tese ou
trabalho de conclusão. O módulo **Requisitos de Graduação** captura tudo o que _não_ é disciplina, permite que a secretaria acadêmica o crie no Desk, sem código, e envia o resultado para a mesma página Program Audit que estudantes e orientadores já usam.

## Visão geral

Pense na graduação como tendo **duas trilhas paralelas**:

| Trilha                                                    | Onde é configurado                                              | O que responde                                                                                                                                   |
| --------------------------------------------------------- | --------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Acadêmicos** — horas-crédito e disciplinas obrigatórias | Program → tabela Courses                                        | O estudante foi aprovado nas disciplinas certas e acumulou créditos suficientes?                                                                 |
| **Requisitos de Graduação** — todo o restante             | Program Graduation Requirement (este módulo) | O estudante também cumpriu as evidências não relacionadas a disciplinas (cartas, presenças, projetos, declarações assinadas)? |

Ambas as trilhas se consolidam na página Program Audit. Um estudante fica `graduation_eligible` apenas quando **todos os itens obrigatórios atualmente ativos** em **ambas** as trilhas estão verdes. As duas trilhas são avaliadas independentemente — um estudante com uma presença de capela faltando não é impedido de se registrar em disciplinas, e um estudante que ainda não concluiu sua última disciplina não é impedido de enviar suas cartas de recomendação.

## As três camadas

O módulo é construído em três camadas. Você passará a maior parte do tempo nas duas primeiras.

```
1. Biblioteca         — Graduation Requirement Item        (defina uma vez, reutilize em qualquer lugar)
                    │
2. Política          — Program Graduation Requirement     (vincule a um programa, com datas)
                    │
3. Instância        — Student Graduation Requirement     (uma linha por estudante, congelada na matrícula)
```

### Camada 1 — A Biblioteca

Um **Graduation Requirement Item** declara _que tipo de coisa existe no seminário_. Você o define uma vez, com instruções aos estudantes, e o reutiliza em quantos programas desejar.

Every library item picks **one** of four types:

- **Participação em Evento** — cumprido quando um estudante participa de um [Evento](../modules/academic-calendar.md) específico. Exemplo: _"Retiro de Formação Espiritual
  2027"_. Choose **Event per Student** if every student must show up
  individually; leave it unchecked if a single occurrence (a one-time event
  everyone attends together) satisfies the cohort.
- **Chapel Attendance** — _count-based_ attendance at recurring chapel
  services, fulfilled automatically as students **check themselves in** from
  the portal. You set how many services are required (e.g. 30); the
  requirement turns green the moment a student's check-in count reaches that
  number. Unlike Event Attendance you do **not** create one record per
  service — the chaplain schedules each chapel once, students self check-in,
  and the system keeps the running tally. See
  [Worked example 1](#example-1-chapel-attendance-self-check-in) for the full
  setup.
- **Verificação Manual** — cumprido quando a equipe confirma que o estudante realizou a tarefa, opcionalmente com arquivo de evidência do estudante, da equipe ou de ambos. Example: _"Doctrinal Statement Signed"_, _"Ordination Interview"_.
- **Documento Vinculado** — cumprido quando outro documento no sistema atinge um status específico. Exemplo: uma _Recommendation Letter_ passa para `Approved`, ou um _Culminating Project_ passa para `Completed`.

Duas sinalizadores controlam as evidências em itens de Verificação Manual:

- **Evidence Submitted by Student** — dá ao estudante um botão de upload na sua página Program Audit. Use isto para itens como um formulário de ciência assinado que o próprio estudante anexa.
- **Evidence Required by Staff** — a equipe deve anexar um arquivo ao marcar o item como Fulfilled. Use isto para itens que você precisa manter em arquivo (uma declaração doutrinária assinada, atas digitalizadas do conselho de ordenação).

Esses dois sinalizadores são independentes. Uma declaração doutrinária pode exigir _ambos_ (o estudante envia o PDF assinado, a equipe envia sua nota de verificação de identidade). A new-student orientation typically requires _neither_ — the staff
just ticks Fulfilled.

> **Why two flags?** Some items, like a new-student orientation, are simple —
> staff ticks a box. Others, like a doctrinal statement, need a written
> document from the student _and_ a staff verification of identity. One pair of
> fields can model both.

#### Blocks Graduation Request

Se o seu seminário usar o fluxo de [Graduation Request](graduation-request.md), cada item da biblioteca tem mais um sinalizador — **Blocks Graduation Request** (visível apenas quando `Mandatory` está marcado). Quando ativado, o estudante não pode nem mesmo abrir um Graduation Request até que esse requisito esteja `Fulfilled` ou `Waived`. Use isto para pré-requisitos rígidos que a secretaria acadêmica deseja verificar antecipadamente: cartas de recomendação, teses, declarações doutrinárias.
Itens sem esse sinalizador ainda contam para a elegibilidade de graduação, mas o estudante pode enviar a solicitação e a etapa de revisão acadêmica detectará quaisquer pendências.

### Camada 2 — A Política

Um **Program Graduation Requirement** vincula itens da biblioteca a um Program com datas de vigência. Esta é a principal área de configuração da secretaria acadêmica.

Campos no cabeçalho da política:

- **Program** — a qual programa esta política se aplica.
- **Active from / Active until** — a janela do ano de catálogo. Um estudante que se matricular em 2026-09-01 adota a política cuja janela contenha essa data.
- **Is Active** — chave para marcar rascunho (ou substituída) vs. política publicada.

Dentro da política você lista **Program Requirement Items** (as linhas da política).
Cada linha escolhe um item da biblioteca e adiciona metadados de vinculação específicos do programa:

- **Activation Mode** — _quando_ o requisito passa a "vencer" para um
  estudante matriculado. Veja abaixo.
- **Is Mandatory** — falhar nesta linha bloqueia a graduação, ou é opcional/informativo?
- **Quantity Required** — the count the student must reach. For **Chapel
  Attendance** it is the number of services to check in to (e.g. 30); for
  **Manual Verification** it is the number of instances (e.g. 8 service-hour
  logs). Event Attendance and Linked Document always count as 1.

#### Modos de ativação

Um requisito pode vencer _no dia em que o estudante se matricula_ — ou apenas após algum gatilho. Os quatro modos:

- **Always Active** — exigível desde o primeiro dia. Use isto para qualquer coisa que o estudante possa iniciar a qualquer momento (presença na capela, declaração doutrinária).
- **After Requirement** — só vence depois que um ou mais outros requisitos nesta mesma política tiverem sido `Fulfilled` ou `Waived`. Use isto para cadeias de pré-requisitos:
  _"Ordination Interview"_ só vence após _"Pastoral
  Recommendation Letter"_ e _"Doctrinal Statement"_ estarem ambas Fulfilled.
- **On Document Status** — só vence depois que um documento relacionado atingir um status determinado. O `link_doctype` do item da biblioteca e o `linked_doc_status` escolhido juntos definem o gatilho.
- **Time Offset** — vence em relação a um marco de data. Escolha um marco (Expected Graduation Date, Last Term Starts, Program Starts), um valor de deslocamento e uma unidade (Dias ou Período Acadêmico). _"Recital de Formatura — vence 60 dias
  antes de Expected Graduation Date"_ é offset = -60, unit = Days, anchor =
  Expected Graduation Date.

Uma linha cuja ativação ainda não foi disparada aparece no Program Audit como
_Not Yet Active_ e, mesmo que seja obrigatória, **não** bloqueia a
eligibilidade para graduação — é "ainda não é seu problema." Uma vez ativa, uma linha obrigatória não cumprida bloqueia a graduação.

### Camada 3 — A Instância (snapshot)

Quando um Program Enrollment é enviado, o sistema **faz um snapshot** da política ativa em linhas por estudante chamadas **Student Graduation Requirements** (SGRs). Uma linha de SGR por linha da política, multiplicada pela quantidade para itens de Verificação Manual. **Chapel Attendance** is the exception — it stays a
_single_ row carrying the required count and a live "attended" tally (e.g.
_22 / 30_) rather than splitting into one slot per service.

Esse snapshot fica **congelado para aquele estudante.** Um secretário acadêmico publicando uma nova política em 2027 **não** altera retroativamente os requisitos de um estudante que se matriculou em 2025. Este é o contrato do ano de catálogo — é a regra que os seminários tradicionalmente honram e é aplicada por design.

O **Program Enrollment** também armazena a política que selecionou (`graduation_policy`) para que qualquer pessoa revisando o arquivo possa rastrear exatamente em qual ano de catálogo o estudante está.

Se a secretaria acadêmica realmente precisar migrar um estudante para a política atual (por exemplo, o estudante solicitou, ou um órgão regulador exigiu), há uma ação autorizada **Resnapshot** no Program Enrollment. Por padrão, ela preserva quaisquer linhas que já estavam `Waived`; a ação é registrada em log.

## Exemplos práticos

### Example 1 — Chapel attendance (self check-in)

**Goal:** every student must attend 30 chapel services across the program,
recorded by students checking themselves in.

1. **Crie o item de biblioteca.** Desk → Graduation Requirement Item → New.
   - Requisito: `Chapel Attendance`
   - Type: `Chapel Attendance`
   - Default Quantity: `30`
   - Obrigatório: ✓
   - Instructions: _"Attend at least 30 chapel services. Open the Program
     Audit page during the service and tap **Check in**."_

2. **Adicione à política do programa.** Desk → Program Graduation Requirement → abrir _MDiv 2026 Catalog_ → adicionar uma linha apontando para `Chapel Attendance`.
   - Activation Mode: `Always Active`
   - Quantity Required: `30` (or override per program — e.g. 15 for a
     part-time MA)

3. **At enrollment**, the system materializes a **single** SGR row per
   student that starts at _0 / 30_.

4. **Day to day**, there is nothing for staff to tick. As each student checks
   in to a chapel service, their tally climbs (_1 / 30_, _2 / 30_, …) and the
   row turns green automatically the moment it reaches 30. The Program Audit
   page reflects it immediately.

#### Scheduling chapels and how check-in works

Chapel services live in their own **Chapel** record (Desk → Chapel → New). A
chapel is a public event — all students and instructors are invited, and it is
open to the public.

- **Topic, date/time, room** — what students see, and when check-in is
  allowed.
- **Chapel Team** — the table where the chaplain assigns the preacher,
  worship leader, host, etc., and tracks each person's invitation status.
- **Confirmed** — students can only check in to a chapel once it is
  **Confirmed**. Leave it unchecked while you are still planning the service.

**The check-in window** is governed by two settings under _Seminary Settings →
Chapel & Official Events_: how many minutes **before** the start and **after**
the end check-in stays open. Set **both to 0** to remove the time limit
entirely (students may check in any time the chapel is Confirmed).

**Optional check-in code.** If _Require check-in code_ is enabled in Seminary
Settings, each chapel gets a short human-readable code (shown on the Chapel
record). Display it on screen during the service; students must type it to
check in, which keeps people from checking in while away.

**Optional Google Calendar sync.** If _Sync chapels with Google Calendar_ is
enabled and an _Official Google Calendar_ is selected in Seminary Settings,
each confirmed chapel is published to that shared calendar (with the chapel
team added), so students and the public can see the schedule. The toggle is
off by default — seminaries that don't use Google Calendar can ignore it, and
individual chapels can still opt out via their own _Sync with Google Calendar_
checkbox.

### Exemplo 2 — Três cartas de recomendação (com slots nomeados)

**Objetivo:** todo candidato à graduação envia três cartas de recomendação — _Pastoral_, _Acadêmica_, _Caráter_ — cada uma de um tipo diferente de recomendador, cada uma com suas próprias instruções.

O instinto é usar um único item de biblioteca com `quantity_required = 3`.
**Não faça isso.** Cada carta tem um público diferente e instruções diferentes.
Crie **três itens de biblioteca separados** em vez disso:

- _Pastoral Reference Letter_ — Documento Vinculado, alvo `Recommendation Letter`. Instruções: _"Solicite ao pastor da sua igreja de origem."_
- _Academic Reference Letter_ — igual. Instruções: _"Solicite a um
  professor da sua área de formação."_
- _Character Reference Letter_ — igual. Instruções: _"Solicite a alguém que o conheça há pelo menos 5 anos e que não seja parente."_

O estudante vê três entradas distintas no Program Audit, cada uma com sua própria orientação. O doctype Recommendation Letter cuida do restante: um link tokenizado do portal de convidados enviado ao recomendador, envio multicanal (portal / e-mail / upload manual) e um fluxo de trabalho que termina em `Approved`.
Quando a carta é aprovada, a linha de SGR muda para `Fulfilled` automaticamente.

### Exemplo 3 — Entrevista de Ordenação (após as cartas)

**Objetivo:** uma entrevista de ordenação só pode ser agendada depois que ambas as cartas de recomendação estiverem recebidas.

1. Crie um item de biblioteca de Manual Verification _Ordination Interview_
   (Mandatory, Staff Evidence Required = ✓ com rótulo _"Ata da entrevista"_).
2. Na política, adicione uma linha para isso com **Activation Mode = After Requirement** e selecione as linhas de política para _Pastoral Reference_ e _Academic Reference_ como pré-requisitos.
3. Até que ambas as cartas estejam Fulfilled, o Program Audit mostra _"Ordination Interview
   — Not Yet Active"_ e não bloqueia a graduação. No momento em que a segunda carta é aprovada, a linha é ativada e passa a contar para a elegibilidade.

### Exemplo 4 — Projeto de Conclusão (um doctype vinculado complexo)

**Objetivo:** todo estudante de MDiv escreve um Projeto de Conclusão, defendido em até três rodadas com avaliadores.

Este é o doctype **Culminating Project**. You don't need to model the
project yourself — it ships with the system, including reviewer roles, a
staged milestone plan, and its own workflow. The configurable pieces (project
types, milestones, defenses) are described in
[Culminating Projects: types, milestones, and defenses](#culminating-projects-types-milestones-and-defenses)
below.

Para integrá-lo a um programa:

1. Crie um item de biblioteca _Senior Project_.
   - Type: `Linked Document`
   - Linked Document: `Culminating Project`
   - **Culminating Project Types Allowed**: list the project type(s) a student
     may pick (e.g. _Thesis_, _Summative Paper_).
2. Adicione-o à política com **Activation Mode = Time Offset**, anchor `Last Term Starts`, value `0`, unit `Days` — isto é, vence quando o período final começa.
3. Na matrícula, a linha de SGR aparece no snapshot. The student initiates
   the project from the audit page (a _Start Project_ button, choosing a type
   if more than one is allowed); when the project reaches `Completed`, the SGR
   row flips to Fulfilled automatically.

### Exemplo 5 — Declaração Doutrinária (assinada por ambas as partes)

**Objetivo:** o estudante assina uma declaração doutrinária; a secretaria acadêmica verifica a assinatura e arquiva uma cópia.

1. Crie um item de biblioteca _Doctrinal Statement_.
   - Tipo: `Manual Verification`
   - Obrigatório: ✓
   - Evidence Submitted by Student: ✓, rótulo _"Declaração assinada (PDF)"_
   - Evidence Required by Staff: ✓, rótulo _"Anotação de verificação de identidade"_
2. O estudante faz o upload do PDF assinado no portal. Seu slot muda para `Submitted`.
3. A secretaria acadêmica abre a linha de SGR, anexa a nota de verificação e clica em `Fulfilled`.

## Culminating Projects: types, milestones, and defenses

A _Senior Project_ / _Thesis_ / _Capstone_ is wired in as a **Linked Document**
requirement pointing at the **Culminating Project** doctype (Example 4). Behind
that one requirement sits a small framework you configure once.

### Project Types

A **Culminating Project Type** (Desk → Culminating Project Type) is a reusable
template for one _kind_ of project — e.g. _Thesis_, _Capstone_, _Summative
Paper_. Each type defines:

- **Course** — a culminating project is also a real course enrollment, so it
  earns credit and a grade like any other course. The type names which Course
  backs it.
- **Milestones** — the staged plan every project of this type follows (below).

On the requirement's library item you list the **Culminating Project Types
Allowed**. If you allow exactly one, the student is auto-assigned it; if you
allow several (e.g. Thesis _or_ Summative Paper), the student chooses one on the
Program Audit page when they start.

### Milestones

Each Project Type carries a **milestone template** — an ordered list of steps.
For each step you set:

- **Kind** — _Standard_, _Proposal_, _Defense_, or _Final Submission_.
- **Due date** — computed from an **anchor** (Project Start, Enrollment Date,
  Expected Graduation, Term Start, or the Previous Milestone) plus an **offset**
  in days or academic terms. So "Proposal — 30 days after project start" or
  "Defense — one term before expected graduation" are just anchor + offset.
- **Requires Submission** — whether the student must upload work for this step.
- **Sign-offs** — which roles must approve: **Advisor**, **Second Reader**,
  **Third Reader**, **Committee**. A milestone reaches _Approved_ only once
  every required role has signed, and the project can be marked _Completed_ only
  when all mandatory milestones are approved.

When a student starts a project, the template milestones are **snapshotted**
onto their project — the same frozen-at-start contract as graduation
requirements. Each snapshot row tracks its own status, due date, sign-offs, and
submission round, and overdue milestones are flagged automatically.

### Defenses (and their calendar event)

A milestone of kind **Defense** can carry a calendar event. On the milestone
template, tick **Creates Event** and pick an **Event Category** (see the next
section). Then, from the project workbench, the **advisor** clicks **Schedule
Defense**, picks a date/time and optional location, and the system creates a
calendar Event with the student, readers, and committee as participants.

The defense event is _calendar-only_ — it exists so everyone shows up at the
right time. It does **not** auto-fulfil anything; the defense is recorded by the
readers signing off the Defense milestone, exactly like any other milestone.

Students, advisors, and readers do all of this from the **Culminating Project
workbench** (a portal page) where they see milestones and due dates, upload
submissions, and record sign-offs.

## How attendance events are handled

The **Event Attendance** requirement type is backed by two pieces: a reusable
_category_ and the dated _events_ created from it.

### Event Categories (the type)

An **Event Custom Category** (Desk → Event Custom Category) describes a _kind_ of
event students attend — e.g. _Convocation_, _Spiritual Formation Retreat_, _Exit
Interview_. It carries:

- **Per Student** — if ticked, every student needs their _own_ occurrence (a
  one-on-one such as an exit interview); if unticked, a _single_ occurrence
  satisfies the whole cohort (a convocation everyone attends together).
- **Visibility** — Public (appears on the shared calendar) or Private.
- **Instructions** — copied into each event's description (dress code, what to
  bring, location notes).

Your Event Attendance library item points at the **category**, not at a specific
date — because the same category is reused every year.

### Creating the actual events

There are two ways staff turn a category into a dated event students get credit
for:

- **Cohort event** (_Per Student_ off) — from the **Event Custom Category** list,
  click **Create Event** on the category's row, pick a date (and optional
  location). The system creates one Event covering every enrolled student who
  still owes this requirement; marking that Event **Completed** flips all of
  their requirement rows to Fulfilled at once.
- **Per-student event** (_Per Student_ on) — from a student's **Program
  Enrollment**, click **Schedule Required Event**, pick the requirement and a
  date. This creates one Event for that student, fulfilled when they are marked
  as attending.

Either way the event is a normal calendar Event — it can be synced to Google
Calendar like any other — and the matching graduation requirement updates
automatically, with no separate "tick Fulfilled" step.

> **Chapel is different.** Chapel attendance is recurring and count-based, so it
> uses its own **Chapel Attendance** type with student self check-in
> ([Example 1](#example-1-chapel-attendance-self-check-in)), not the Event
> Attendance flow described here.

## No dia a dia da equipe

### Onde procurar

- **Status por estudante** — abra o Program Enrollment do estudante e role até a tabela Student Graduation Requirements, ou abra a página Program Audit a partir do portal do estudante (a equipe também pode acessá-la pelo Backoffice).
- **Política por programa** — Desk → Program Graduation Requirement → selecione a política ativa do programa.
- **Visão geral da coorte** — uma listagem de Student Graduation Requirement filtrada por `status = Not Started` e agrupada por `requirement_name` mostra quem ainda deve o quê.

### Marcando algo como Fulfilled

Abra a linha de SGR (do Program Enrollment pai ou diretamente).
Defina `status` como `Fulfilled`, anexe a evidência da equipe se o requisito solicitar e salve. O sistema preenche `verified_by` e `verified_on` automaticamente.

For Linked Document and Chapel Attendance requirements, you usually do **not**
mark the SGR row manually — the linked document's workflow (or the student's
own check-ins) flips it for you. You can still waive them, or tick Fulfilled
as an override.

### Dispensando um requisito

Às vezes, um requisito realmente não deve se aplicar a um determinado estudante (por exemplo, o requisito foi adicionado para novos estudantes e um estudante em andamento solicitou formalmente uma exceção). Na linha de SGR:

1. Marque `Waived`.
2. Insira uma **Waiver Reason** (um parágrafo curto — este é o seu rastro de auditoria).
3. Salvar. O sistema registra `waived_by` ( você) e `waived_on` (agora).

Uma linha marcada como `Waived` conta como satisfeita para a elegibilidade de graduação, mas é claramente distinguida de `Fulfilled` nos relatórios.

### Publicando um novo ano de catálogo

Quando o seminário altera seus requisitos, você publica uma nova política **ao lado** da antiga — você **não** edita a antiga no lugar.

1. Duplique o Program Graduation Requirement existente (ou crie um novo).
2. Defina `Active from` para a data em que o novo catálogo entra em vigor (por exemplo, `2027-09-01`).
3. Defina `Active until` da política anterior para o dia anterior (por exemplo, `2027-08-31`).
4. Marque `Is Active` na nova.
5. Ajuste as linhas.

Estudantes que se matricularem **após** o novo `Active from` farão snapshot com base na nova política. Estudantes já matriculados mantêm a antiga. Se um estudante pedir explicitamente para ser movido para o novo catálogo, use **Resnapshot** no seu Program Enrollment.

### Adicionando um novo tipo de documento vinculado sem código

Se o seu seminário quiser mais tarde um novo tipo de documento vinculado (por exemplo, _Internship Report_ — um doctype que sua equipe de TI cria com seu próprio fluxo de trabalho), você **não** precisa editar nenhum código. Assim que o doctype existir com um campo `workflow_state`:

1. Crie um item de biblioteca com `Type = Linked Document` e escolha _Internship Report_ em `Linked Document`.
2. Adicione-o às políticas de programa relevantes com o modo de ativação desejado.
3. Em cada item de biblioteca com **Activation Mode = On Document Status**, especifique o status que sinaliza a conclusão (por exemplo, `Approved`, `Completed`).

O sistema reflete automaticamente as mudanças de status nas linhas de SGR.

> **Atenção — doctypes personalizados.** Dois tipos de requisito são fornecidos com seus
> próprios doctypes completos porque o caminho genérico de "Linked Document" é muito
> limitado para eles: **Recommendation Letter** (com o portal externo do recomendador)
> e **Culminating Project** (com rodadas de avaliação). Para estes, use os doctypes dedicados; o sistema já os integra ao Program Audit.

## Como isso se conecta de volta ao Program Audit

A **página Program Audit** (`/program-audit/<enrollment>`) apresenta uma visão única e consolidada:

- A seção **Acadêmicos**, alimentada pela tabela Program → Courses, mostra o progresso de créditos e o status das disciplinas obrigatórias. _(inalterado)_
- A seção **Requisitos de Graduação**, alimentada pelo snapshot de SGR, mostra todos os requisitos ativos, agrupados por status, com instruções por linha e quaisquer evidências já arquivadas. Chapel Attendance rows show a live count
  (_22 / 30_) and a **Check in** button whenever a confirmed chapel is open.

Um estudante é mostrado como `Eligible to graduate` apenas quando ambas as seções estão livres de itens obrigatórios não cumpridos.

## Referência rápida

| Se você quiser... | Faça isto                                                                                                                                  |
| ----------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| Adicionar uma nova categoria de requisito para todo o seminário   | Criar um Graduation Requirement Item (biblioteca)                                                                       |
| Aplicar um requisito a um programa específico                     | Adicionar uma linha ao Program Graduation Requirement (política) desse programa                                         |
| Require students to attend N chapel services                      | Library item Type = Chapel Attendance, set Default Quantity; schedule Chapel records and mark them Confirmed                               |
| Require a thesis / capstone                                       | Library item Type = Linked Document → Culminating Project; list the allowed project type(s)                             |
| Define a project's stages and defense                             | Add milestones to the Culminating Project Type (anchor + offset, sign-off roles, Creates Event for the defense)         |
| Require attendance at a one-off event                             | Create an Event Custom Category, then Create Event (cohort) or Schedule Required Event (per student) |
| Fazer um requisito vencer somente após outro                      | Activation Mode = After Requirement, selecione os pré-requisitos                                                                           |
| Fazer um requisito vencer X dias antes da graduação               | Activation Mode = Time Offset, anchor = Expected Graduation Date                                                                           |
| Confirmar que um estudante cumpriu algo                           | Abrir a linha de SGR, definir `status = Fulfilled`                                                                                         |
| Dispensar um estudante de um requisito                            | Abrir a linha de SGR, marcar `Waived`, informar um motivo                                                                                  |
| Atualizar o catálogo do seminário                                 | Publicar um novo Program Graduation Requirement com uma nova data `Active from` — não edite o antigo                                       |
| Mover um estudante para o novo catálogo                           | Ação **Resnapshot** no seu Program Enrollment                                                                                              |

## Relacionados

- [Enrollment](enrollment.md) — o Program Enrollment é onde o snapshot fica.
- [Academic Calendar](academic-calendar.md) — Eventos usados por requisitos de Participação em Evento.
- [User Roles](../administration/user-roles.md) — quais papéis podem criar políticas, marcar requisitos como `Fulfilled` e dispensar.
