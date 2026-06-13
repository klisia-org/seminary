# Disciplina

Os seminários mantêm os estudantes de acordo com um padrão de conduta e integridade acadêmica, e
eles se preocupam profundamente com o _devido processo_ - uma sanção deve ser proporcionada,
consistente, e no registro. O módulo **Disciplina** lhe dá um catálogo de
razões e sanções, uma **matriz de disciplina progressista consultiva** que
sugere a ação certa por quantas vezes algo aconteceu, e um caminho
limpo de "instrutor notou alguma coisa" até "o aluno foi descartado e
não pode se inscrever novamente." Nada é imposto automaticamente, exceto uma única e explícita bandeira
de demissão — qualquer outra decisão fica em mãos humanas.

## Visão geral

O módulo tem **três blocos de construção**, mais um opcional: instrutor-portal
reportando o fluxo:

```
Motivo Disciplinário — o catálogo do "o que aconteceu" (plagiarismo, ausência, …)
        possibilita uma matriz de ações recomendadas pela ocorrência número
Ação Disciplinar — o catálogo "que fazemos a respeito dele" (aviso … dismissal)
        ├
Incidente Disciplinário — um registro de um evento, com as ações aplicadas
```

- Um **Reason** é _o porquê_ — uma categoria reutilizável como _Plagiarismo_ ou _Sem desculpa
  Absence_. Cada motivo carrega uma **matriz consultiva**: "1a vez → Verbal
  Aviso, 2nd → Aviso escrito, 3° e além → Dispensamento."
- Uma **Ação** é _o que você faz_ — uma sanção como _Aviso Verbal_ ou
  _Descartar_, definida uma vez e reutilizada.
- Um **incidente** vincula uma razão para um aluno em uma data, registra as evidências,
  e lista as ações realmente aplicadas. A matriz **pré-preenchimentos** sugestões
  por ocorrência; o adjudicador confirma ou substitui.

A única consequência automática em todo o módulo é uma ação Disciplinária
sinalizada **Disputa do Programa de Dispensamentos**: gravar tal ação em um incidente
separa o aluno do programa (através do mesmo
[corte de separação](withdrawal.md) usado em retiradas) e coloca em espera que
blocos de re-matrícula. Tudo o resto é consultivo.

## Configurações

Disciplinary reporting from the instructor portal is gated by **two** switches —
both must be on for an instructor to file an incident from a course:

1. **Configurações de seminário → `Instrutores criam Incidente Disciplinário`** — a mudança global. Quando
   selecionado, cada curso mostra ações para reportar incidentes disciplinares no curso
   e níveis de avaliação.
2. **Motivo Disciplinário → `Portal do Instrutor`** — a mudança por motivo. Apenas as razões
   marcadas disponíveis para os instrutores aparecem na caixa de diálogo de relatório do portal.

Se o interruptor global estiver desligado, o portal mostra nenhum botão de relatório, e
todos os incidentes são arquivados pela equipe no Desk. O design biinterruptor permite ativar
relatório do portal em geral, mantendo motivos sensíveis (digamos, qualquer coisa
que possa levar a despedir) fora da lista direcionada ao instrutor.

## O catálogo

### Motivos Disciplinários

Uma **Motivo Disciplinário** (Desk → Motivo Disciplinário) é uma categoria reutilizável de
violação. Campos:

- **Razão** — O nome dos alunos e funcionários vê (_Plagiarismo_, _Conduta Disruptiva
  conduct_, _Absenção Desabilitada_).
- **Categoria** — _Academic Integrity_, _Conduct_, _Participação_, _Financial_, ou
  _Other_. Usado para filtragem e relatório.
- **Descrição** — uma descrição do catálogo do que este motivo aborda.
- **Portal do instrutor** — quando marcado, instrutores podem escolher esta razão quando
  reportar a partir do portal (a segunda porta descrita sob
  [Settings](#settings)).
- **Requer Avaliação** — quando marcada, este motivo está no nível \*\*avaliação
  \*\*: preenchê-la requer a matrícula do curso _e_ a avaliação
  específica envolvida. Use-o para coisas ligadas a um trabalho (plagiarismo em
  uma redação, trapaceando em um exame). Deixe-o desmarcado para conduta de nível de curso
  (disrupção, latência repetida).
- **Ações recomendadas** — a matriz consultiva (próxima seção).

#### A matriz progressiva-disciplina

Dentro de cada razão que você lista **Ações Recomendadas** — linhas que mapeiam um número
de ocorrência para a sanção que você sugere:

| Coluna               | Significado                                                                                                                               |
| -------------------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| **Ocorrência de**    | Primeira ocorrência que esta linha se aplica a (1 = primeira ofensiva).                                |
| **Ocorrência a**     | Última ocorrência a qual esta linha se aplica. **0 significa "e acima"** (open-ended). |
| **Ação Recomendada** | A ação Disciplinar a sugerir.                                                                                             |
| **Nota**             | Orientação opcional copiada para o incidente como uma nota de resultado.                                                  |

Uma linha se aplica quando o número de ocorrência do aluno cai entre _de_ e _até_
(inclusive), tratando _até = 0_ como "e acima". Então, uma escada clássica de três etapas
para _Plagiarismo_ (com um verbal e dois avisos escritos) é:

| De | Até | Ação Recomendada |
| -- | --- | ---------------- |
| 1  | 1º  | Aviso Verbal     |
| 2  | 3   | Aviso escrito    |
| 4º | 0   | Descartar        |

O **número de ocorrência** é calculado automaticamente — é uma contagem de incidentes de
deste aluno _pelo mesmo motivo_. O terceiro incidente de plagiarismo
para um aluno terras na fila "3 e acima" e sugere despedimento. Este é o coração
do módulo: repetidas pequenas ofensivas escalam por conta própria, sem
ninguém tendo que se lembrar "não foi a terceira vez?"

> **Advisory, not automatic.** The matrix only **pre-fills** an incident's
> applied actions. O adjudicador pode confirmá-los, adicionar outros ou removê-los
> completamente. A matriz é um motor de recomendação, não um motor de aplicação.

### Ações Disciplinárias

A **Disciplinary Action** (Desk → Disciplinary Action) is a sanction you can
apply. O sistema separa um conjunto inicial que você pode editar ou estender: _Alerta Verbal_,
_Aviso escrito_, _Probação Disciplinária_, _Suspensão_, _Dismissal_. Campos:

- **Nome da ação** — o nome da sanção (única).
- **Gravidade** — _Informação_, _Formal_, _Probação_, _Suspension_, ou
  _Dismissal_. Informação/denúncia.
- **Desencadeia a Dispensação do Programa** — \*\*único efeito automático no módulo. \*
  Quando uma ação aplicada deste tipo é gravada em um incidente, o estudante é
  dispensado do programa por meio do
  compartilhado [separação da espinha](withdrawal.md) e uma reserva de inscrição é colocada. Por padrão
  apenas _Descartar_ carrega esta bandeira.
- **Ação do Instrutor** — quando selecionada, os instrutores podem **gravar** esta ação
  eles mesmos no portal. Use-o para baixa participação sancionar um instrutor é
  autorizado a entregar no local — principalmente **verbais e avisos escritos**
  que não precisam de escalada. Deixe de fora para qualquer coisa que deva ir para um adjudicador
  (provação, suspensão, dispensar).
- **Está ativo** — desmarque para se aposentar de uma sanção sem excluir o histórico.
- **Descrição** — o que a sanção significa.

> **Duas bandeiras diferentes, dois trabalhos diferentes.** _Desencadeia o Programa de Dispensação_
> decide se a aplicação da ação termina o programa do aluno. _Ação do Instrutor
> A_ decide se um instrutor de sala de aula (em vez de um adjudicador)
> pode gravá-lo. Um Aviso Verbal é uma _Ação do Instrutor_ e **não** dispensa
> dismissão; um Dismissor aciona o despedimento e **não** é uma ação do Instrutor
> .

### Incidentes Disciplinares

Um **Incidente Disciplinário** (Desk → Incidente Disciplinar) registra um evento.
Campos chave:

- **Inscreva-se no programa** / **Aluno** — quem diz respeito ao incidente (o aluno
  é derivado da matrícula).
- **Inscrição no curso** / **Avaliação** — o curso (e, por razões
  _Requer Avaliação_, a avaliação específica envolvida.
- **Data de incidente**, **Motivo**, **Número de ocorrência** (auto computado).
- **Evidência** e **Anexo** — descreva o que aconteceu e anexe provas.
- **Ações aplicadas** — as sanções realmente aplicadas. Linhas pré-preenchidas da matriz
  estão sinalizadas _foram sugeridas_; cada selo de linha que a aplicou e quando.
- **Status** — o ciclo de vida do incidente:
  - **Relatado** — arquivado, aguardando ação.
  - **Ação feita** - uma sanção autorizada pelo instrutor foi gravada.
  - **Escalado** — precisa de um adjudicador (por exemplo, a recomendação é uma suspensão
    ou demitir um instrutor não pode se registrar).
  - **Descartado** — Uma ação aplicada acionada pela separação do programa.
- **Reportado por** — quem o arquivou (definido automaticamente quando reportado do portal
  format@@1).
- **Descrição da Resolução** — uma narrativa das ações feitas.

Quando você escolher um motivo e o número de ocorrência é conhecido, a matriz
pré-preenche automaticamente as **Ações aplicadas** com as sanções recomendadas,
marcado como sugestões, com uma _"confirmação ou substituição"_. Você fica em
controle: mantenha-os, altere-os, ou adicione seu próprio.

## Relatório do portal do instrutor

Quando [os dois interruptores](#settings) estão ligados, instrutores podem registrar incidentes
sem tocar na mesa. Há dois pontos de referência.

### Relatório de nível de curso

Em um cartão de curso (para instrutores e moderadores) botão **Denunciar Disciplinário
Incidento** abre uma caixa de diálogo onde o instrutor:

1. Escolhe o **aluno** (a lista lista dos estudantes matriculados pelo nome
   do curso).
2. Escolhe um **motivo** — apenas as razões que são o _Portal do Instrutor_ **e** não
   _Requer Avaliação_ aparecem aqui (conduta de nível do curso).
3. Opcionalmente, adiciona **provas** e um **anexo**.

Assim que o aluno e o motivo forem escolhidos, as pré-visualizações de diálogo _"Esta será
ocorrência #N"_ e a ação recomendada. O que acontece a seguir depende da recomendação
(veja [Gravação agora vs. depois](#recording-now-vs-later)).

### Relatório de avaliação

Ao avaliar uma única submissão (prova, tarefa, teste ou discussão) em
**Relatório de Incidente Disciplinário para esta Submissão** abre o mesmo diálogo
, mas com o **aluno e avaliação corrigida** do envio que você
está avaliando — o instrutor só precisa escolher um motivo (aqui apenas
_Portal do Instrutor_ **e** _Requer Avaliação_ razões para aparecer, e. .
plagiarismo) e opcionalmente adicione provas. This is the natural place to flag
academic-integrity issues the moment you spot them.

### Gravação agora vs. mais tarde

Após a visualização, a caixa de diálogo se adapta à ação recomendada:

- If the recommendation is an **Instructor Action** (e.g. Verbal Warning), the
  instructor sees **two buttons**:
  - **Reporte e registe a ação** — registre o incidente _e_ registre a sanção
    agora (status → _Ação Tomada_). Utilize quando você manusear no local ("Eu
    conversei com o aluno").
  - **Apenas o relatório** — registre o incidente agora e deixe a ação para mais tarde
    (status → _Relatorado_). Use quando você deseja relatar e continuar avaliando, ou
    quando alguém deve decidir.
- Se a recomendação **não** for uma ação do instrutor — ou ativaria a demissão
  — o instrutor vê um botão **Relatório**. O incidente é
  arquivado e **Ampliado** para que um adjudicador lide na mesa. (A mensagem de sucesso
  confirma que foi reportada)

### Ações pendentes (relatório agora, agir mais tarde)

Incidentes "Reportar somente" não se sobrepõem às rachadas. Each course's **To-Do
card** shows a **Disciplinary — Pending Actions** list for instructors, with one
row per pending incident (student, reason, occurrence, recommended action) and a
**Record Action** button. **Qualquer instrutor naquele curso** pode gravar a ação
— para que um avaliador possa relatar um incidente após horas e o professor de
possa registrar a sanção na manhã seguinte, ou vice-versa. A gravação da ação
move o incidente para _Ação Recebida_ e o remove da lista.

## Descartar: único efeito automático

Se uma ação aplicada for sinalizada **Dismissal** (por padrão,
_Dismissal_), salvando o incidente:

1. Inicia uma **separação completa do programa** para o aluno através do
   compartilhado [coluna de separação](withdrawal.md), com o status de separação _dispensado_ e a categoria
   _Disciplinar_, eficaz na data de incidente.
2. Coloca um **agendamento de inscrição** no aluno, para que ele não possa simplesmente
   registrar-se novamente, com o incidente registrado como origem.
3. Define o status do incidente para **Dispensado**.

This is deliberately the _only_ enforced outcome — and it requires a human to
record a dismissal action on the incident. Disciplinary exits never use the
student-facing [Withdrawal Reasons](withdrawal.md) taxonomy; the separation
carries the Disciplinary Reason in its history and uses a dedicated
_Disciplinary Dismissal_ reason only to satisfy the separation record.

## Exemplos práticos

### Exemplo 1 — Plagiarismo, ascendendo à demissão

**Objetivo:** plagiarismo é um Aviso Verbal na primeira vez, um Aviso Escrito do
segundo e dispensar o terceiro.

1. **Crie o motivo.** Desk → Disciplinário Reason → Novo.
   - Razão: `Plagiarismo`; Categoria: `Academic Integrity`
   - Requer Avaliação: ✓ (ela está vinculada a uma peça de trabalho)
   - Portal do Instrutor: ✓ (para que os instrutores possam sinalizar ao avaliar)
   - Ações recomendadas:
     - 1 → 1 — Aviso Verbal
     - 2 → 2 — Aviso de Escrito
     - 3 → 0 — Descartar
2. **Confirm the actions exist.** _Verbal Warning_ and _Written Warning_ should
   be **Instructor Action = ✓**; _Dismissal_ should be **Triggers Program
   Dismissal = ✓** (these come seeded).
3. \*\*Primeira ofensiva. \* Ao avaliar a redação, o instrutor clica em _Reportar
   Disciplinar Incidente para esta Submissão_, Escolhe `Plagiarism`, vê
   _"Ocorrência #1 — Aviso Verbal, "_ e clique em **Ação de Relatório & Registro**.
4. **Terceira ofensiva.** O mesmo fluxo agora pré-visualiza \*"Ocorrência #3 — Descartar. \*
   Porque descartar não é uma ação do instrutor, o instrutor recebe somente
   **Relatório** e o incidente **escalonado**. Um adjudicador abre em
   Desk, confirma a ação de Dispensamento, e o aluno está separado por um
   re-matrícula.

### Exemplo 2 — Faltas repetidas (nível do curso, relatório agora / agir mais tarde)

**Objetivo:** monitorar ausências sem desculpas para que um padrão esteja visível, com avisos para que o instrutor
possa passar a mão.

1. Crie a razão `Absenção sem desculpas` (Categoria `Participação`, Portal do Instrutor
   ✓, Requer Avaliação ™️) com uma matriz: 1–2 → Aviso Verbal, 3 → Aviso escrito
   Aviso.
2. Um assistente de ensino nota uma terceira ausência e, a partir do cartão do curso,
   clica _Reportar Incidente Disciplinário_, escolhe o aluno e o motivo, e usa
   **Reportar somente** (eles preferem que o professor decida).
3. O incidente aparece sob **Disciplinara—Ações pendentes** no curso
   To-Do. O professor de registro abre, clica em **Ação de Registro**, e o
   Aviso de Escrito está no arquivo.

### Exemplo 3 - Uma sanção que um instrutor não pode dar

**Objetivo:** uma violação de conduta cuja ação recomendada é _Disciplinar
Probação_.

A divulgação **não** é uma ação do instrutor. Quando um instrutor relata isso, ele
só vê **relatório**; o incidente é **escalado**. O dean abre no Desk,
revisa as evidências e registra a Probação (ou substitui com uma ação
diferente). O instrutor fez o relatório; o adjudicador tomou a decisão.

## No dia a dia da equipe

- **Coloque um incidente em Desk.** Mesa → Incidente Disciplinário → Novo. Escolha o motivo e a inscrição
  programa; o número de ocorrência e as ações recomendadas
  preenchem. Confirme ou substitua as **Ações aplicadas**, adicione evidências e salve.
- **Find what needs attention.** A list view of _Disciplinary Incident_ filtered
  by `status = Reported` or `status = Escalated` shows the open queue;
  instructors see their courses' pending items on each course To-Do card.
- **Grave ou altere uma ação.** Abra o incidente, edite as _Ações aplicadas_
  da tabela, e salve. Gravando uma ação de _Dispensar Programa de Ativação_ separará
  o aluno — faça isso deliberadamente.
- **Construa o histórico de um aluno.** Filtre _Incidente Disciplinário_ pelo aluno para ver
  todas as razões, ocorrência, ação e status no registro.

## Referência rápida

| Se você quiser... | Faça isto                                                                                                                                     |
| ----------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------- |
| Adicionar um novo tipo de violação                                | Criar um motivo Disciplinário (definir categoria; selecionar o Portal do Instrutor / Requer Avaliação conforme necessário) |
| Fazer o aumento automático de advertências                        | Adicionar linhas de ações recomendadas para o motivo (use _to = 0_ para "e acima")                                         |
| Adicionar uma nova sanção                                         | Criar uma ação de Disciplinar (definir severidade)                                                                         |
| Deixe os instrutores distribuírem uma sanção                      | Marque a **Ação do Instrutor** naquela Ação Disciplinar                                                                                       |
| Faça uma sanção terminar o programa do aluno                      | Marque **Disputa a Dispensação do Programa** naquela Ação Disciplinar                                                                         |
| Permitir que os instrutores reportem de cursos                    | Ative as Configurações do Seminário → **Disciplina do Portal** _e_ o **Portal do Instrutor** do motivo.                       |
| Sinalizar plagiarismo ao avaliar                                  | Usar _Relatório de Incidente Disciplinário para esta Submissão_ na apresentação                                                               |
| Relatar agora e decidir mais tarde                                | Usar **Apenas Relatório**; gravar mais tarde a partir do curso ParaDo                                                                         |
| Registrar uma ação pendente                                       | Abra o curso a fazer → Disciplinar — Ações pendentes → **Ação de Registro**                                                                   |
| Dispensar um aluno por causa                                      | Registre uma ação de _Dismissal_ (Triggers Program Dismissal) no incidente                                                 |
| Revisar o registro de um aluno                                    | Filtrar Incidente Disciplinário por aluno                                                                                                     |

## Relacionados

- [Retirada e Separação](withdrawal.md) — o fluxo disciplinar de coluna
  está a decorrer; como o bloco se inscreve novamente.
- [Grading](grading.md) — onde o nível de avaliação relata vidas.
- [Funções de usuário](../administration/user-roles.md) — quem pode arquivar incidentes, gravar
  ações e adjudica.
