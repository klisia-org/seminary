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

Cada item da biblioteca escolhe **um** de quatro tipos:

- **Participação em Evento** — cumprido quando um estudante participa de um [Evento](../modules/academic-calendar.md) específico. Exemplo: _"Retiro de Formação Espiritual
  2027"_. Escolha **Evento por Aluno** se cada aluno deve aparecer
  individualmente; deixe não marcado se uma única ocorrência (um evento único
  todos participam juntos) satisfaz o grupo.
- **Chapel Attendance** — _count-based_ attendance at recurring chapel
  services, fulfilled automatically as students **check themselves in** from
  the portal. Você define quantos serviços são necessários (por exemplo, 30); o requisito
  fica verde no momento em que a contagem de check-in do aluno atinge o número
  . Diferente da Presença de Eventos que você **não** cria um registro por serviço
  — o capelão agenda cada capela uma vez, alunos fazem auto check-in,
  e o sistema mantém a execução das contagens. Veja
  [Exemplo feito 1](#example-1-chapel-attendance-self-check-in) para a configuração completa do
  .
- **Verificação Manual** — cumprido quando a equipe confirma que o estudante realizou a tarefa, opcionalmente com arquivo de evidência do estudante, da equipe ou de ambos. Exemplo: _"Declaração Doutrinal Assinada"_, _"Entrevista de Ordenação"_.
- **Documento Vinculado** — cumprido quando outro documento no sistema atinge um status específico. Exemplo: uma _Recommendation Letter_ passa para `Approved`, ou um _Culminating Project_ passa para `Completed`.

Duas sinalizadores controlam as evidências em itens de Verificação Manual:

- **Evidence Submitted by Student** — dá ao estudante um botão de upload na sua página Program Audit. Use isto para itens como um formulário de ciência assinado que o próprio estudante anexa.
- **Evidence Required by Staff** — a equipe deve anexar um arquivo ao marcar o item como Fulfilled. Use isto para itens que você precisa manter em arquivo (uma declaração doutrinária assinada, atas digitalizadas do conselho de ordenação).

Esses dois sinalizadores são independentes. Uma declaração doutrinária pode exigir _ambos_ (o estudante envia o PDF assinado, a equipe envia sua nota de verificação de identidade). Uma nova orientação do aluno normalmente requer _nenhum_ — a equipe
apenas marca preenchido.

> **Why two flags?** Some items, like a new-student orientation, are simple —
> staff ticks a box. Outros, como uma declaração doutrinal, precisam de um documento
> escrito do aluno _e_ uma verificação da identidade pela equipe Um par de campos
> pode modelar ambos.

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
- **Quantidade necessária** — A contagem que o aluno deve alcançar. Para **Presença na Capela** é o número de serviços a serem enviados (por exemplo, 30); para
  **Verificação manual** é o número de instâncias (por exemplo, logs de 8 horas de serviço
  ). Participação de eventos e Documento Vinculado sempre contam como 1.

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

Quando um Program Enrollment é enviado, o sistema **faz um snapshot** da política ativa em linhas por estudante chamadas **Student Graduation Requirements** (SGRs). Uma linha de SGR por linha da política, multiplicada pela quantidade para itens de Verificação Manual. **Presença na Capela** é a exceção — ela permanece uma linha
_única_ carregando a contagem necessária e uma contagem ao vivo "participante" (e. .
_22 / 30_) ao invés de dividir em um slot por serviço.

Esse snapshot fica **congelado para aquele estudante.** Um secretário acadêmico publicando uma nova política em 2027 **não** altera retroativamente os requisitos de um estudante que se matriculou em 2025. Este é o contrato do ano de catálogo — é a regra que os seminários tradicionalmente honram e é aplicada por design.

O **Program Enrollment** também armazena a política que selecionou (`graduation_policy`) para que qualquer pessoa revisando o arquivo possa rastrear exatamente em qual ano de catálogo o estudante está.

Se a secretaria acadêmica realmente precisar migrar um estudante para a política atual (por exemplo, o estudante solicitou, ou um órgão regulador exigiu), há uma ação autorizada **Resnapshot** no Program Enrollment. Por padrão, ela preserva quaisquer linhas que já estavam `Waived`; a ação é registrada em log.

## Exemplos práticos

### Exemplo 1 - Presença da Capela (check-in)

**Objetivo:** todos os alunos devem participar dos serviços de 30 capelas através do programa,
registrados pelos alunos.

1. **Crie o item de biblioteca.** Desk → Graduation Requirement Item → New.
   - Requisito: `Chapel Attendance`
   - Tipo: `Presença na Capela`
   - Quantidade Padrão: `30`
   - Obrigatório: ✓
   - Instruções: _"Participe de pelo menos 30 serviços da capela. Open the Program
     Audit page during the service and tap **Check in**."_

2. **Adicione à política do programa.** Desk → Program Graduation Requirement → abrir _MDiv 2026 Catalog_ → adicionar uma linha apontando para `Chapel Attendance`.
   - Activation Mode: `Always Active`
   - Quantity Required: `30` (ou sobrescreva por programa — p.ex., 15 para um MA parcial)

3. **Na matrícula**, o sistema materializa uma linha de SGR por
   aluno que começa em _0 / 30_.

4. **Dia após dia**, não há nada para o pessoal atrapalhar. À medida que cada aluno verifica
   a um serviço da capela, sua contagem muda (_1 / 30_, _2 / 30_, …) e a linha
   fica verde automaticamente no momento em que atinge 30. A página de Auditoria
   do Programa reflete ela imediatamente.

#### Agendando capelas e como funciona o check-in

Serviços de Capela vivem em seu próprio registro **Capela** (Desk → Capela → Nova). A
capela é um evento público — todos os alunos e instrutores são convidados e é
aberta ao público.

- **Tópico, data e hora, quarto** — o que os alunos veem e quando o check-in é
  permitido.
- **Equipe de Capela** — a mesa onde o capelão atribui o pregador,
  o líder de adoração, anfitrião, etc., e rastreia o status de convite de cada pessoa.
- **Confirmado** — Os alunos só podem check-in em uma capela quando for
  **Confirmado**. Deixe-o desmarcado enquanto você ainda está planejando o serviço.

**A janela de check-in** é governada por duas configurações em _Configurações do Seminário →
Capela e Eventos Oficiais_: quantos minutos **antes** \*\* do início e **depois**
o check-in final permanece aberto. Defina **ambos como 0** para remover o tempo limite
inteiramente (os alunos podem verificar a qualquer momento que a capela for confirmada).

\*\*Código de verificação opcional. \* Se _Exigir código de verificação_ estiver habilitado nas Configurações
do Seminário, cada capela recebe um pequeno código legível para ser humano (mostrado no registro da Capela
). Exiba na tela durante o serviço; os alunos devem digitá-lo para
fazer o check-in, o que impede que as pessoas façam o check-in enquanto estiverem fora.

\*\*Sincronização opcional do Google Calendar. \* Se _Sincronizar chapels com o Google Calendar_ for
ativado e um _Calendário Oficial do Google_ for selecionado nas Configurações do Seminário,
cada capela confirmada é publicada no calendário compartilhado (com a equipe da capela
adicionada), para que os alunos e o público possam ver o cronograma. O alternador está
desativado por padrão - seminários que não usam o Google Calendar podem ignorá-lo, e
capelas individuais ainda podem sair através de suas próprias _Sincronizar com o Google Calendar_
.

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

Este é o doctype **Culminating Project**. Você não precisa modelar o projeto
você mesmo — ele é fornecido com o sistema, incluindo as funções do revisor, um plano de marco
e seu próprio fluxo de trabalho. As peças configuráveis (projeto
tipos, marcos, defesas) são descritas em
[Projetos Culminantes: tipos, marcos e defesas](#culminating-projects-types-milestones-and-defenses)
abaixo.

Para integrá-lo a um programa:

1. Crie um item de biblioteca _Senior Project_.
   - Type: `Linked Document`
   - Linked Document: `Culminating Project`
   - **Tipos de projetos finais Permitidos**: liste o(s) tipo(s) de projeto que um aluno
     pode escolher (por exemplo, _Tese_, _Dissertação_).
2. Adicione-o à política com **Activation Mode = Time Offset**, anchor `Last Term Starts`, value `0`, unit `Days` — isto é, vence quando o período final começa.
3. Na matrícula, a linha de SGR aparece no snapshot. O aluno inicia
   o projeto a partir da página de auditoria (um botão _Iniciar Projeto_, escolhendo um tipo
   se mais de um for permitido); quando o projeto chegar a 'Concluído', a linha SGR
   transforma para 'Completado' automaticamente.

### Exemplo 5 — Declaração Doutrinária (assinada por ambas as partes)

**Objetivo:** o estudante assina uma declaração doutrinária; a secretaria acadêmica verifica a assinatura e arquiva uma cópia.

1. Crie um item de biblioteca _Doctrinal Statement_.
   - Tipo: `Manual Verification`
   - Obrigatório: ✓
   - Evidence Submitted by Student: ✓, rótulo _"Declaração assinada (PDF)"_
   - Evidence Required by Staff: ✓, rótulo _"Anotação de verificação de identidade"_
2. O estudante faz o upload do PDF assinado no portal. Seu slot muda para `Submitted`.
3. A secretaria acadêmica abre a linha de SGR, anexa a nota de verificação e clica em `Fulfilled`.

## Projetos para cultura: tipos, marcos e defesas

Um _Projeto Sênior_ / _Tese_ / _Dissertação_ está ligado como um **Documento Vinculado**
requisito apontando para o doctype **Projeto Culminante** (Exemplo 4). Behind
that one requirement sits a small framework you configure once.

### Tipos de Projeto

Um **Tipo de Projeto Culminante** (Desk → Tipo de Projeto Culmining) é um modelo
reutilizável para um _tipo_ de projeto — e. . _Tese_, _Capstone_, _Summative
Papel_. Cada tipo definido:

- **Curso** — um projeto culminante é também uma verdadeira matrícula de cursos, então ele
  ganha crédito e uma nota como qualquer outro curso. O nome do tipo que o Curso
  apoia.
- **Marcos** — o plano staged todos os projetos deste tipo segue (abaixo).

Na biblioteca do requerimento, você lista os **Tipos de Projeto Culminante
Permitidos**. If you allow exactly one, the student is auto-assigned it; if you
allow several (e.g. Thesis _or_ Summative Paper), the student chooses one on the
Program Audit page when they start.

### Etapas

Cada tipo de projeto transporta um **modelo de marco** - uma lista ordenada de etapas.
Para cada passo que você define:

- **Kind** — _Padrão_, _Proposta_, _Defesa_, ou _Submissão final_.
- **Data de vencimento** — calculado a partir de um **anchor** (Início do projeto, data de inscrição,
  Esperado Graduação, O termo começa ou o marco anterior) mais um **offset**
  em termos de dias ou acadêmicos. Então "Proposta — 30 dias após o início do projeto" ou
  "Defesa — um termo antes da graduação esperada" são apenas âncora + deslocamento.
- **Requer Submissão** — se o aluno deve fazer o upload do trabalho para esta etapa.
- **Sign-offs** — quais cargos devem aprovar: **Advisor**, **Segundo Reader**,
  **Terceiro Reader**, **Comité**. A milestone reaches _Approved_ only once
  every required role has signed, and the project can be marked _Completed_ only
  when all mandatory milestones are approved.

Quando um aluno inicia um projeto, os marcos de modelo são **snapshotted**
em seu projeto - o mesmo contrato congelado no início conforme os requisitos de graduação
. Each snapshot row tracks its own status, due date, sign-offs, and
submission round, and overdue milestones are flagged automatically.

### Defesas (e o evento do calendário)

Um marco do tipo **defesa** pode carregar um evento do calendário. No modelo de marco
, marque **Cria evento** e selecione uma **categoria de eventos** (veja a próxima seção
). Em seguida, na bancada do projeto, o **conselheiro** clica **Agenda
Defes**, escolhe uma data/hora e um local opcional, e o sistema cria um evento
do calendário com os alunos, leitores e comitê como participantes.

O evento de defesa é _somente calendário_ — existe para que todos apareçam no horário
certo. It does **not** auto-fulfil anything; the defense is recorded by the
readers signing off the Defense milestone, exactly like any other milestone.

Alunos, consultores e leitores fazem tudo isso da \*\*bancada de trabalho do projeto Culminante
(uma página do portal) onde eles veem marcos e datas de vencimento, fazer upload
envios e registrar logoffs.

## Como os eventos de participação são tratados

O tipo de requisito de **presença de eventos** é coberto por duas partes: um
reutilizável _categoria_ e o _eventos_ datado criado a partir dele.

### Categorias de eventos (o tipo)

Uma **Categoria Personalizada do Evento** (Mesa → Categoria Personalizada do Evento) descreve uma _tipo_ de
dos estudantes do evento que participam — e. . _Convocação_, _Retirada de Formação Espiritual_, _Saia
Interview_. Isso transporta:

- **Per Student** — if ticked, every student needs their _own_ occurrence (a
  one-on-one such as an exit interview); if unticked, a _single_ occurrence
  satisfies the whole cohort (a convocation everyone attends together).
- **Visibilidade** — Público (aparece no calendário compartilhado) ou privado.
- **Instructions** — copied into each event's description (dress code, what to
  bring, location notes).

Sua biblioteca de itens de quantidade de presença de eventos aponta para a **categoria**, não em uma data
específica — porque a mesma categoria é reutilizada todo ano.

### Criando os eventos reais

There are two ways staff turn a category into a dated event students get credit
for:

- **Evento de agrupamento** (_por Aluno_ desligado) — da lista **Categoria Personalizada do Evento**,
  clique em **Criar evento** na linha da categoria, escolha uma data (e local opcional de
  ). The system creates one Event covering every enrolled student who
  still owes this requirement; marking that Event **Completed** flips all of
  their requirement rows to Fulfilled at once.
- **Evento por aluno** (_Por Aluno_) — de um aluno **Programa
  Matrícula**, clique em **agendar Evento obrigatório**, selecione a exigência e uma data
  . Isso cria um evento para aquele aluno, cumprido quando ele é marcado como
  como participante.

De qualquer forma que o evento é um evento normal - ele pode ser sincronizado com o Google
Calendário como qualquer outro — e as atualizações dos requisitos de graduação correspondentes
automaticamente, sem etapa separada de "marcação finalizada".

> \*\*Chapel é diferente. \* Participação pela Capel é recorrente e baseada em contas, então ela
> usa seu próprio tipo **Participação pela Chapel** com o check-in por cada aluno
> ([Exemplo 1](#example-1-chapel-attendance-self-check-in)), não é o evento
> fluxo de presença descrito aqui.

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
- A seção **Requisitos de Graduação**, alimentada pelo snapshot de SGR, mostra todos os requisitos ativos, agrupados por status, com instruções por linha e quaisquer evidências já arquivadas. Laços de Presença de Capela mostram uma contagem ao vivo
  (_22 / 30_) e um botão **Checkin** sempre que um capel confirmado estiver aberto.

Um estudante é mostrado como `Eligible to graduate` apenas quando ambas as seções estão livres de itens obrigatórios não cumpridos.

## Referência rápida

| Se você quiser... | Faça isto                                                                                                                                                                  |
| ----------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Adicionar uma nova categoria de requisito para todo o seminário   | Criar um Graduation Requirement Item (biblioteca)                                                                                                       |
| Aplicar um requisito a um programa específico                     | Adicionar uma linha ao Program Graduation Requirement (política) desse programa                                                                         |
| Exige que os alunos participem dos serviços do Choro N            | Tipo de item da Biblioteca = Presença da Capela, definir Quantidade Padrão; Agende registros da Capela e marque-os Confirmados                                             |
| Exigir uma tese / lápis                                           | Tipo de item da Biblioteca = Documento vinculado → Projeto Culminante; lista o(s) tipo(s) de projeto permitido(s) |
| Definir as fases e a defesa de um projeto                         | Adicionar marcos ao tipo de Projeto Culminating (âncora + offset, papéis de sinal, Cria evento para a defesa)                                           |
| Exigir participação em um evento único                            | Criar uma categoria personalizada de evento, então criar um evento (cohort) ou agendar eventos obrigatórios (por aluno)              |
| Fazer um requisito vencer somente após outro                      | Activation Mode = After Requirement, selecione os pré-requisitos                                                                                                           |
| Fazer um requisito vencer X dias antes da graduação               | Activation Mode = Time Offset, anchor = Expected Graduation Date                                                                                                           |
| Confirmar que um estudante cumpriu algo                           | Abrir a linha de SGR, definir `status = Fulfilled`                                                                                                                         |
| Dispensar um estudante de um requisito                            | Abrir a linha de SGR, marcar `Waived`, informar um motivo                                                                                                                  |
| Atualizar o catálogo do seminário                                 | Publicar um novo Program Graduation Requirement com uma nova data `Active from` — não edite o antigo                                                                       |
| Mover um estudante para o novo catálogo                           | Ação **Resnapshot** no seu Program Enrollment                                                                                                                              |

## Relacionados

- [Enrollment](enrollment.md) — o Program Enrollment é onde o snapshot fica.
- [Academic Calendar](academic-calendar.md) — Eventos usados por requisitos de Participação em Evento.
- [User Roles](../administration/user-roles.md) — quais papéis podem criar políticas, marcar requisitos como `Fulfilled` e dispensar.
