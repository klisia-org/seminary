# Presença

Os seminários se preocupam com a presença — muitos programas exigem que os alunos sejam realmente
na sala, e a acreditação geralmente depende disso. O módulo
de **comparecimento** cobre o arco inteiro: **gravação** quem foi apresentado, Dardy, ou ausente em cada reunião
classe (pelo instrutor, ou por conta de alunos com um código
no check-in, transformando-o em uma **posição** contra um limite de ausência por curso,
**aviso** todos antes que um aluno esteja em problemas, e — quando a política
de um seminário requer isso — deixando o registrador **falhar um estudante por ausências** até
quando as suas pontuações passariam. Like the rest of the system, nothing
fails a student automatically: the limit raises flags and sends warnings, and a
human makes the call.

## Visão geral

Presença tem **quatro camadas**, cada um deles tem um prédio anterior:

```
1. Capture — marque Presentes / Tardia /
2 ausência por reunião (instrutor ou auto check-in) Política — Quantas ausências são permitidas (Programa % → limite por curso)
3. Permanente — cada aluno está executando o tempo vs. seu limite, com avisos
4. Consequência — o "Falhar para a Absa" (FA), um passo humano deliberado
```

- **Captura** acontece na página de frequência do curso, em uma folha impressa, ou
  através de **self-check-in** dos alunos com um código de reunião rotativo.
- A **Política** é definida uma vez no nível do Programa como porcentagem e resolve para um número
  concreto de ausências permitidas em cada Agenda de Curso.
- **Standing** is computed for every student and shown to them (on their course
  status), to instructors (on the attendance page), and to the registrar (in a
  cross-course report), with notifications when a student nears or crosses the
  limit.
- **Consequência** — falhando para ausências — nunca é automático. É uma ação de registrar
  que sela uma nota especial **FA**.

## Capturando comparecimento

O instrutor abre **Participação** de um curso e vê a turma com
um controle de três vias para cada aluno: **Presente**, **Tarde**, ou **Absão**.
Escolha uma data de reunião à esquerda, marque todos e salve. Uma coluna que corre
**Absences (usada / permitida)** mostra os olhos de cada aluno
âmbar colorida quando estão em risco e vermelha quando estão acima do limite (esta coluna
só aparece uma vez que um limite de ausência está em vigor — veja
[Policy](#the-absence-policy)).

> **Tardia é um estado de primeira classe.** Não é apenas uma nota — os tardias podem contar
> para o limite de ausência a uma taxa configurável (e. . 3 tardes = 1 ausência),
> então marcar alguém mais de Tardia do que ausência é significativo.

### A folha imprimível

Para salas de aula onde participar em uma tela não é prático, um botão de **impressão
folha em branco** produz uma lista limpa — nomes dos alunos com
Presente / Tardy / Caixas ausentes e uma linha de assinatura. Imprima-a, marque a mão
durante a classe, e coloque-a mais tarde. A folha é gerada a partir da lista ao vivo,
para que seja sempre atual.

## Autocheck-in do aluno

Instead of (or alongside) the instructor marking everyone, students can record
their own attendance. O instrutor projeta um pequeno **código de check-in** (e/ou
um código QR), Os alunos entram em um telefone e um registro de Presente (ou Tarde)
foi criado para eles.

### Mostrando o código

On the attendance page, **Show check-in code** generates a short, human-readable
code for the selected meeting (e.g. `9WBH5`) and displays it large on screen,
together with a **QR code**. O QR Deep-links para a página do check-in
com o curso, data e código já preenchido — então digitalizá-lo é o caminho
mais rápido; digitar o código é a solução. O código é gerado sob demanda
e permanece estável para aquela reunião.

### Check-in

Os alunos fazem check-in por **Marca minha presença** no cartão de curso, ou por
escaneando o QR (que abre a página de check-in). O que eles veem depende da configuração de **janela horária** do
seminário (abaixo):

- **Janela de tempo aplicada (recomendada):** o sistema seleciona automaticamente a reunião
  acontecendo _neste momento_ e registros de presença em um toque ou pergunta o código
  . Um aluno que verifica após o período de invencibilidade está marcado como **Tarde**
  automaticamente.
- **Janela de horário não aplicada (modo de captação):** o aluno escolhe qualquer reunião anterior
  à qual ele não tem presença. No clock, no code — useful when you can't
  rely on the server clock matching local class times.

> **The clock matters.** Time-window check-in compares "now" against the
> meeting's scheduled time **in the site's time zone** (System Settings → Time
> Zone). If your site time zone doesn't match where classes actually happen, a
> live class can read as "closed." Em caso de dúvida, defina o fuso horário
> do site corretamente, ou desligue a janela e use o modo de captação.

### Configurações de check-in automático

Tudo em \*\*Configurações seminárias → Verificação do Curso de Comparecimento \*\*:

| Configuração                                           | O que ele faz                                                                                                                                                                                                                                     |
| ------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Impor janela de tempo da reunião**                   | Ligado = seleção automática baseada no tempo (janela + código + Tardy se aplica). Desligado = Modo de captação (escolha qualquer reunião passada; sem relógio, sem código). |
| **Requer código de check-in**                          | Os alunos devem digitar o código da reunião para check-in.                                                                                                                                                                        |
| **O Check-in abre Antes de (mins)** | Quão cedo a janela abre antes do início da reunião.                                                                                                                                                                               |
| **Check-in Fecha Após (mins)**      | Quão tarde a janela fica aberta após o fim da reunião.                                                                                                                                                                            |
| **Tardia Após (mins)**              | Período após o início; um check-in depois disso é registrado **Tarde**. `0` = nunca auto-tardy.                                                                                                                   |

As verificações automáticas sempre marcam apenas **Apresentar** ou **Tarde** — o instrutor ainda está
analisa a grelha e finaliza qualquer ausência.

## A política de ausência

Um seminário expressa sua regra como um **percentual de reuniões que um aluno pode errar**,
e o sistema transforma isso em um número concreto para cada curso.

### Três lugares, um número

1. **Padrões para todo o seminário — Configurações seminárias → Política de comparecimento:**
   - **Tardies per Absence** (default **3**) — how many tardies equal one
     absence toward the limit. `0` desativa a conversão.
   - **Avise Dentro (ausências do limite)** (padrão **1**) - quão próximo do limite
     um aluno deve estar antes de ser sinalizado "com risco".
2. **Program → Attendance Policy → Default Max Absence %** — the policy itself,
   e.g. **20%**. "0\` significa "nenhum limite de presença por padrão para este programa".
3. **Programação do curso → Política de presença** — onde a porcentagem se torna um número
   . Editável **apenas pelo registrador/Cadeira do programa** (os instrutores vejam
   somente leitura):
   - **Automático (do programa)** — limite = round( o programa do aluno % ×
     reuniões agendadas).
   - **Custom** — a fixed number of absences that applies to everyone in the
     course.
   - **Desativado** — Nenhum limite de frequência para este curso.

> \*\*O limite é por aluno, de propósito. \* Um curso não pertence a um único programa
> — diferentes alunos da mesma classe podem estar em diferentes programas
> com diferentes porcentagens. Portanto, sob **Auto**, o número permitido de cada aluno é
> calculado a partir da porcentagem do programa _próprio_. Um curso de 14 reuniões com uma regra de 20%
> dá a esses alunos um limite de **3** (20% × 14 = 2. → 3); um estudante
> de um programa 10% na mesma classe recebe **2**. **Personalizado** e
> **Desativado** se aplicam uniformemente a todos.

> \*\*Cursos virtuais estão isentos por padrão. \* Quando a **Modalidade** de um curso é
> _Virtual_ e a política é _Automática_, o limite é automaticamente desabilitado —
> cursos on-line muitas vezes têm apenas uma ou duas reuniões listadas, o que tornaria uma percentagem
> sem significado. Cursos _Presenciais_ e _Híbridos_ mantêm o limite.

### O que conta como uma ausência

- **Ausências efetivas** = registros **Ausentes** registrados **+** (tardia,
  _Tardias por Ausência_, arredondados para baixo). Com o padrão 3, um aluno com 4
  ausências reais e 6 tardias tem um total efetivo de **4 + 2 = 6**.
- **A licença aprovada é excluída.** Um registro ausente vinculado a um
  aprovado (submetido) Aplicativo de Saída dos Alunos **não** conta para o limite.
- **Os auditores estão isentos.** Os alunos que auditam um curso (não avaliado) nunca são
  sinalizados.
- O denominador é as **reuniões agendadas do curso**, então o número permitido
  é estável a partir do primeiro dia — mesmo antes de toda a presença ser tomada. (O limite
  recomece automaticamente quando você adiciona datas de reunião mais tarde.)

## Próximo, avisos e notificações

Uma vez que um limite estiver em vigor, todos os alunos recebem uma **posição** que atualizam com a classe
de participação:

- **Com risco** — dentro da banda de aviso (por exemplo, com um limite de 3 e um buffer de
  1, um aluno atinge "de risco" a 2 ausências efetivas).
- **Acima do limite** — mais do que o número permitido.

Onde fica a parada:

- **Alunos** vê um painel de **presença** em sua página de status de curso —
  "_X de Y ausências usadas_" — mais um banner de âmbar quando em risco e um painel vermelho quando
  acima do limite.
- **Instructors** see the per-student **Absences (X / Y)** column on the
  attendance page, coloured by standing.
- **Registrar / Program Chair** get the **Students At Attendance Risk** report
  (Desk) — every at-risk and over-limit student across all courses, with their
  count, limit, and status.

**Notifications fire once per crossing.** When a student first enters the warning
band, and again when they first cross the limit, a notification goes to the
**instructor(s)**, the **registrar / Program Chair**, and the **student**. Cada
dispara uma vez — corrigir o número de presenças de volta não vai fazer spam para ninguém, e o alerta
não vai repetir na próxima recomposição noturna.

## Falhar para Ausências (FA)

Some programs fail a student who misses too many classes **regardless of their
grades**. Este é um passo deliberado e orientado para o registro — o limite de ausência apenas
_bandeiras_; falhar é uma decisão humana.

### Configurando o código FA da nota

Na **Escala de Classificação** (mesa → Escala de Classificação) dois campos, ao lado da escala
de retirada-passe / falha de retirada:

- **Código de Falha para Absas** (padrão **FA**) - a nota é estampada em
  a transcrição quando um aluno falhou para ausências.
- **Considere FA no GPA** — se a linha de FA conta para o GPA.

A _Escala Numérica_ padrão já vem com `FA` definido, então a ação funciona
da caixa.

### Falhando em um estudante

A ação **Falhou por Aba** está disponível para o **registo/Cadeiras do Programa**
em dois lugares:

- Na **Lista de Cursos Agendada** (Desk), ao lado de **Avaliar Aluno**.
- No relatório de **Risco de Comparecimento** — marque a(s) linha(s) e escolha
  **Falha na Aba**.

Aplicando isso:

- Força a nota final do aluno ao código **FA** com um resultado **Falhou** —
  **independente de suas pontuações** — e é _pegada_, então rodando as notas (ou
  do instrutor **Enviar Grades**) mantém a FA ao invés de recalcular uma nota de passagem de
  .
- Updates the **transcript** (Program Enrollment Course → status _Fail_, grade
  _FA_) and removes the course's credits from the student's total if they had
  been counted as passed.
- É totalmente **reversível** — **Desfazer Falha para Absão** limpa e restaura a
  verdadeira nota computada.

> **Passing scores, failing grade.** That's the whole point of FA: a student can
> have a B average and still receive an FA on the transcript because they missed
> too many classes. A pontuação numérica é preservada para o registro; o grau
> código e senha/falha são substituídos.

### Reportar um incidente disciplinar (ou também)

Problemas de presença muitas vezes também pertencem ao módulo [Discipline](discipline.md).
Quando **Configurações de Seminário → Instrutores criam Incidente Disciplinário** está ativado e
um \*\* motivo de Disciplinária de categoria \*\* existe, um botão **Relatório de Disciplinário
Incidente** aparece:

- Na **página de participação do instrutor**, ao lado de qualquer aluno que está em risco ou
  acima do limite (somente por razões marcadas _Portal do Instrutor_).
- No relatório **Risco de Comparecimento** para o registro — abre um
  novo incidente pré-preenchido com o aluno e uma razão de comparecimento.

Caso não esteja presente e não tenha ocorrido um incidente disciplinar é independente: use um,
o outro, ou ambos.

## Exemplos práticos

### Exemplo 1 - Uma regra padrão de 20% com o check-in próprio

**Objetivo:** Cursos presenciais permitem que os alunos percam 20% das aulas; Os alunos
consultem um código para estudar.

1. **Programa → Política de presença → Abscrição máxima padrão %** = `20`.
2. **Configurações do seminário → Política de comparecimento:** Tardes por Absence `3`, Avise
   Dentro de `1`.
3. **Configurações Seminárias → Verificação de Comparecimento de Curso:** Reforçar o tempo de reunião
   janela ✓, Exigir código de verificação ✓, Tardy após `10`.
4. A Presential course with **14 meetings** (Auto policy) gives each 20%-program
   student a limit of **3** absences.
5. Na classe, o instrutor clica em **Exibir código de verificação**, projeta o código +
   QR. Students scan/enter it; anyone checking in more than 10 minutes after the
   start is marked **Tardy**.
6. Quando um aluno atinge **2** ausências efetivas são sinalizadas _com risco_
   (todos são notificados uma vez); ao **4** eles estão _acima do limite_ (notificados de novo).

### Exemplo 2 - Falhando um aluno para ausências

**Objetivo:** um aluno com média passageira perdeu muitas classes e o programa
não as acertou.

1. O aluno mostra **acima do limite** do relatório de **Risco de Comparecimento**.
2. The registrar ticks the row and clicks **Fail for Absence** (or opens the
   Scheduled Course Roster and uses the button next to _Grade Student_).
3. A nota do aluno se torna **FA / Fail**; seus registros transcritos de FA e os créditos do curso
   não são contabilizados. Se o instrutor executar mais tarde **Send Grades**,
   os gravetos.
4. Se foi um erro, os cliques para registrar **Desfazer Falha na Absão** e a nota
   realmente retorna.

### Exemplo 3 - Um curso online sem limite de presenças

**Objetivo:** um curso virtual com duas reuniões listadas não deve estar sujeito à regra
de porcentagem percentual.

Nada a fazer. Com **Modalidade = Virtual** e política **automática**, o limite é
automaticamente desativado — os alunos não vêem nenhum painel de participação, o instrutor não vê
coluna de ausências, e ninguém é marcado. If a particular online course _does_
need a limit, the registrar sets its policy to **Custom** with an explicit
number.

## Dia-dia

- **Assuma a participação.** Abra um curso → Comparecimento → escolha a data → marcar
  Presente/Tardy / Com ausência → salvar. Ou imprima uma folha em branco e insira mais tarde.
- **Execute a check-in.** Clique em **Mostrar código de verificação**, projetá-lo (e QR),
  e fazer com que os alunos verifiquem **Mark my attendance**.
- **Veja quem está em risco.** Registrar: gerencie **Alunos em risco de comparecimento** (mesa).
  Instrutores: a coluna Absences na página de presenças. Alunos:
  painel de presença no status do curso.
- **Falha (ou não-falha) por ausências.** Registrar / Cadear do Programa: \*\*Falhar paraAusência\*\* na lista ou no relatório em risco; **Desfazer** para inverter.
- **Defina a política.** Programa → Max Absence %; substitua por curso no
  Curso Agenda (apenas para registros).

## Referência rápida

| Se você quiser... | Faça isto                                                                                                                    |
| ----------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| Registrar presença                                                | Curso → Presente → Marca Presente/Tardy / Sem Envios                                                                         |
| Imprima uma folha para marcar manualmente                         | Attendance page → **Print blank sheet**                                                                                      |
| Permita que os alunos verifiquem                                  | **Mostre o código de verificação** (código do projeto + QR); os alunos usam **Mark a minha participação** |
| Exigir um código / configurar janela                              | Configurações de seminário → Confirmação de frequência de curso                                                              |
| Fazer lágrimas contar para as ausências                           | Configurações de Seminário → **Tardes por Abraço** (0 desabilita)                                         |
| Defina a regra de ausência para um programa                       | Programa → **Absência Máxima padrão %**                                                                                      |
| Sobrescrever o limite de um curso                                 | Agenda do curso → Política de presença → **Personalizada** (apenas registrador)                           |
| Desativar o limite para um curso                                  | Agenda de curso → Política de presença → **Desativado** (Virtual auto-desabilites)                        |
| Excluir ausência (licença aprovada)            | Vincular o registro de ausência a um aplicativo de licença de aluno aprovado                                                 |
| Ver alunos em risco nos cursos                                    | Desk → **Relatório de alunos de risco de comparecimento**                                                                    |
| Falhar um aluno para ausências                                    | **Falha na Absão** na lista de participantes ou no relatório de risco (registrar / Cadeia do Programa)    |
| Reverter um Falhou por Ausência                                   | **Desfazer falha para Absence**                                                                                              |
| Escolha o código FA transcrição                                   | Escala de avaliação → **Código de falha para a absorção**                                                                    |
| Registre uma presença disciplinar incidente                       | **Relatório de incidente Disciplinário** na página de presenças ou no relatório de risco                                     |

## Relacionados

- [Discipline](discipline.md) — incidentes relacionados a participação de arquivos;
  sanções progressivas por ausência repetida.
- [Grading](grading.md) — como funcionam as notas finais e as notas de envio; FA substitui a nota
  computada.
- [Retirada & Separação](withdrawal.md) — licença aprovada que desculpa
  ausências.
- [Funções de usuário](../administration/user-roles.md) — quem pode definir política, falhar para
  ausências e adjudicar.
