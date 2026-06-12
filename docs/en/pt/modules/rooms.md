# Quartos e Instalações

Agendar um termo é realmente um problema correspondente: o curso certo, em uma sala
que é grande o suficiente, tem o que o curso precisa e já não está feito. A ferramenta
**Quartos e Instituições** transforma isso do trabalho de adivinhação em algo que você pode ver
e confiar. You describe your spaces once — what each room _has_ and how many it
_seats_ — describe what each kind of course _needs_, and from then on the system
helps you place sections, keeps a room from being double-booked, manages a
**waitlist** when a section fills, and shows you at a glance which rooms are busy,
which are free, and where demand outran the seats you have.

Tudo aqui é **opcional e progressivo**. Um seminário de duas salas pode ignorar
quase tudo e nada muda. A multi-campus school can model every
building, match features to requirements, and track the equipment in each room
as Assets. Você só liga o que te ajuda.

## Visão geral

Há alguns blocos de construção. A maioria dos seminários usa um subconjunto. Observe que uma sala
**tem** características e um tipo de curso **requer** características da mesma lista
— esse vocabulário compartilhado é o que permite que o sistema corresponda.

```mermaid
flchart TD
    Campus["Campus"] --> Construção["Construção"] --> Sala["Quarto"]
    Sala -->→"tem"├RF["Recursos da Sala"]
    CourseType["Tipo de Curso"] -->£"requer, por modality"├RF
    Curso["Curso"] -->➜ "is a"├CourseType
    Sala --> CS["Agendamento do curso (seção + seat cap)"]
    Curso --> CS
    CS -->★ "preenche"├Waitlist["Waitlist"]
    CS --> Relatórios["Relatórios: Utilização, Aguardando, Demanda Não Encontrada"]
```

- A **Sala** é a sua unidade principal — um espaço com um nome, um número, um **lugar de
  capacidade** e uma lista de **características**.
- **Campus** e **Building** são contêineres opcionais acima da sala, para
  escolas multilocais e para filtragem flexível ("salas na Biblioteca").
- **Recursos do quarto** são um vocabulário compartilhado do que um quarto oferece. The same
  vocabulary describes what a **Course Type** requires, so the two can be matched.
- Uma **agenda de curso** (uma turma) é colocada em um quarto e traz um **lugar
  cap**; quando está cheia, os alunos entram em uma **lista de espera**.

## A hierarquia das instalações (Campus → Construção → Sala)

Você não precisa modelar edifícios ou campus. Um quarto fica por conta própria. Mas
se você tiver mais de um site — ou apenas quiser que "quartos no Salão da Chapel" sejam um
coisa — construa a hierarquia de cima para baixo.

### Campus

**Desk → Campus → Novo.** Um campus é um local físico do seminário.

- **Nome do Campus** — como as pessoas chamam (_Main Campus_, _Downtown Extension_).
- **Abreviação** — tag curta opcional.
- **Fuso horário** — informativo por enquanto. Ele registra o fuso horário do campus, mas
  **não** muda as janelas de participação/chapel de check-in, que ainda segue o fuso horário
  do site (ver [Attendance](attendance.md)). Chegou aí, então o recorde é
  pronto para o futuro.
- **Ativo** — desmarque para se aposentar de um campus sem excluir seu histórico.

### Prédio

**Mesa → Construção → Novo.** Um edifício pertence a um campus.

- **Nome da compilação** — _Biblioteca_, _Sala da Capel_. O mesmo nome pode se repetir através de
  campuses.
- **Campus** — Em que campus se senta.
- **Acessível** — uma bandeira rápida para acesso sem passos.

### Sala

\*\*Desk → Sala → Novo. \* Além do básico (nome, número, **capacidade de assentamento**,
acessível), uma sala pode nomear seu **Edifício** — seu **Campus** e então preencher
automaticamente — e listar suas **Características de Sala**. Capacity is the number that drives
seat caps and the "is this room big enough?" checks, so it's worth keeping
accurate.

## Que quarto tem, o que um curso precisa

This is the pairing that makes smart scheduling possible: describe rooms and
courses in the _same words_, and the system can tell you when a room is a poor
fit.

### Recursos de Sala — o que uma sala tem

Um **recurso da sala** (mesa → Funcionalidade da sala) é uma capacidade que um quarto pode oferecer:
_Projeto_, _Sistema de som_, _Piano_, _Quadro branco_, _Acessível a cadeirantes_, e
assim por diante. Cada um transporta uma **Categoria** (AV Equipamento, Musical, Configuração de Sala,
Especializada) para agrupamento de organizações. Um conjunto inicial é fornecido; adicione seu próprio livremente.

Em cada **quarto**, liste os recursos que ele realmente possui na tabela **Recursos da Sala**
da tabela. Este é o perfil da sala.

> \*\*Acessibilidade é um recurso também. \* Marcar uma sala _Acessível a cadeirante_ como um recurso
> (não apenas a bandeira antiga) permite um curso _necessário_ — veja abaixo.

### Tipo de Curso — o que um curso precisa

A **Course Type** (Desk → Course Type) groups courses by what they require of a
room. Dentro dela, as **Requisitos** listas de tabelas, por **modalidade**, o
**Recursos do Quarto** que a modalidade precisa:

| Modalidade | Recurso de quarto necessário |
| ---------- | ---------------------------- |
| Todos      | Projetor                     |
| Presencial | Quadro branco                |
| Híbrido    | Sistema de som               |

_Todos_ se aplica a cada modalidade; as linhas específicas adicionam a ele. Então, uma seção
Presencial deste tipo de curso precisa de um projetor **e** um quadro branco.

Em cada **curso**, defina seu **Tipo de Curso**. From then on, every section of that
course knows what it needs — and the room picker uses it.

If a course has no Course Type, or a Course Type has no requirements, nothing is
lost — the matching simply stays quiet. Você só adiciona requisitos quando eles ajudam.

## Colocando uma turma em uma sala

When you set the **Room** on a Course Schedule, the system works for you in three
ways.

### Um seletor de quarto de melhor ajuste

The Room dropdown is **ordered to put the best fit first** and annotates each
choice, so you're not picking blind. Uma linha lê algo como:

```
Chapel Hall 101 · cap 60 · ✓ fits · free
Room 204       · cap 30 · ✗ missing 1 · busy
```

- **cap** — a capacidade do lugar da sala.
- **✓ se encaixa em / "N faltante** — se a sala tem recursos que o tipo
  deste curso requer para esta modalidade.
- **grátis / ocupado** — se a sala já está reservada durante os tempos
  desta seção.

Quartos que são livres, adequados e maiores flutuam para o topo. Nada está oculto — você
ainda pode escolher qualquer cômodo — mas as boas escolhas são óbvias.

### Avisos e paradas difíceis

Ao salvar, o sistema distingue "você pode querer saber" de "isso não pode ser":

- **Falta um recurso necessário → um aviso.** Você disse que a sala carece de
  algo que o tipo de curso solicitado (e. . "Projeto faltando"), mas o save
  passa. Às vezes um substituto fica bem, e você está no comando.
- \*\*Reserva dupla → bloqueada. \* Se a sala já está reservada por outra seção
  em um horário sobreposto em uma data compartilhada. a gravação foi interrompida, nomeando o conflito
  . As classes back-to-back (uma termina quando o próximo começo) estão bem.
- **Quarto muito pequeno → bloqueado.** Você não pode mover uma seção para uma sala que tenha um número
  a menos do que já está inscrito.

### Alterar quartos, no registro

Use o botão **Alterar Sala** em um cronograma de cursos para mover uma seção. Ele pergunta para
pela nova sala **e um motivo**, e registra tanto no **quarto
O Log de alterações** da seção com quem mudou e quando — então um embaralhamento intercalar ("projetor
quebrou em 204") deixa um raio. Mover uma seção para um espaço **grande** também permite que
a lista de espera seja promovida para os novos assentos automaticamente.

## Capacidade e lista de espera

É aqui que os quartos deixam de ser decorados e começam a protegê-lo contra
excesso de matrícula.

### O limite de assento

Toda programação de cursos possui uma **inscrição máxima**. Quando você escolhe uma sala, it
**por defeito da capacidade de assento daquele quarto** — mas você pode substituí-la (um
seminário limitado a 12 em uma sala de 30 assentos) ou limpe-a (sem tampa). Deixá-lo em branco e
a seção é ilimitada e a lista de espera permanece inativa.

Ao lado disso, a seção mostra três números ao vivo:

- **Assentos Usados** — alunos que têm um lugar (matriculados, mais aqueles que foram
  faturados e estão pagando).
- **Registros** — procura total, incluindo rascunhos e lista de espera.
- **Lista de espera** — quantos estão enfileirados.

### Juntando-se à lista de espera

Quando uma seção está cheia, um aluno que se matricula é colocado na **lista de espera**
em vez de ocupar um lugar — eles veem um status **esperado** e sua **posição**
(#1, #2…). Nenhuma fatura é arrecadada para um estudante que está na lista de espera; ele está segurando um lugar
na linha, não um lugar.

### Promoção automática

The moment a seat frees up — someone withdraws, an unpaid seat is released, you
raise the cap, or you move the section to a bigger room — the **next student on
the waitlist is promoted automatically**. They (and you, the registrar) are
notified. For a paid course, promotion raises their invoice; for a free one, they
go straight in. A promoção é primeiramente vinda, primeiro servida quando eles se juntaram.

### Quando a linha não for clara: "Desconectado"

Se a matrícula for encerrada enquanto os alunos ainda estão esperando, esses alunos mudam para um terminal
**Não-sentado**. Isso não é uma retirada — eles nunca foram sentados —
é simplesmente o registro honesto no qual eles queriam e a sala não pôde segurar
. It powers the **Unmet Demand** report, your evidence for "we need a bigger
room or a second section."

> **Por que isso importa.** Antes, um curso completo ou silenciosamente sobreposto ou
> os alunos viraram fora sem traços. Agora a capacidade é respeitada, a fila é
> justa e automática, e todo aluno que não conseguiu ter um lugar é contado.

## Vendo todo o termo: relatórios

Relatórios de Three Desk (cada filtrável pelo Termo Acadêmico) transformam tudo isso em uma view de registro
.

- **Utilização do Quarto** — cada cômodo com as seções agendadas dentro dele, seus
  dias e horas e assentos vs. capacidade — **mais quartos sem seções**, portanto
  espaços vazios são visíveis. Esta é sua ferramenta para misturar seções quando
  uma sala está encharcada e outro está inativo.
- **Seções esperadas** — toda seção que tem atualmente uma lista de espera, com seu limite de
  , assentos usados, comprimento da lista de espera e demanda total. A sua shortlist para "onde
  precisamos de uma sala maior ou outra turma?"
- **Demanda não atendida** — alunos que aguardavam mas nunca ganharam assento (Unseted),
  agrupados por seção. O número difícil por trás da solicitação de mais espaço.

## Equipamento de rastreamento: integração de conteúdo

Se o seu seminário rastreia **Ativos** (cadastro de ativos fixos do ERPNext) — a unidade de projetor
real, o piano, o kit de laboratório), todos os ativos devem viver em um _local_.
Para evitar esse esforço, o seminário **espelha o seu Campus → Construção → Sala
hierarquia na árvore do local de ativos automaticamente**. Create a room, and a
matching location appears under its building and campus; an asset can then be
placed "in" that room with no parallel bookkeeping.

Isso é controlado em **Configurações de Seminário → Instalações e Ativos**:

- **Sincronizar salas para locais de ativos** — por padrão. Se você não rastrear ativos,
  desliga e nenhuma localização será criada. Volte e os
  campamentos existentes, edifícios e quartos são preenchidos.
- **Root Asset Location** — opcional. Where your spaces hang in the location
  tree. Deixe em branco para usar a raiz da "Localização dos Seminários" criada automaticamente, ou aponte
  para um local que você já usa.

O espelho é unificado (seus quartos dirigem os locais, nunca o reverso), e
nunca exclui um local que ainda mantém um ativo. Um bom efeito colateral: porque os _recursos_ de um cômodo
e seus _ativos_ agora compartilham um lugar. você pode conciliar "cômodos
que devem ter um projetor" com "quartos que realmente têm um."

## Exemplos práticos

### Exemplo 1 - Um curso de música que precisa de um piano

**Objetivo:** todas as seções do _Hymnody_ devem ser colocadas em um quarto com piano, e
você quer ser avisado se não estiver.

1. **Faça o recurso.** Mesa → Recurso da Sala → confirmar que existe _Piano_ (Category
   _Musical_).
2. **Marque as salas.** Em cada quarto que tenha um, adicione _Piano_ a seus recursos da sala.
3. **Descreva a necessidade.** Mesa → Curso Tipo → _Música_ → Requisitos: modalidade
   _Todos_ → _Piano_. Defina o **Tipo de Curso** do curso _Hymnody_ para _Música_.
4. \*\*Agende-o. \* Quando você coloca o quarto em uma seção de Hymnody, o seletor mostra
   _✓ fits_ para quartos de piano e _├faltando 1_ para o resto. Escolha um quarto sem piano
   e você receberá um aviso dispensável — sua chamada.

### Exemplo 2 - Um popular preenchimento electivo

**Objetivo:** _Introdução a Conselho_ tem 25 lugares; você espera mais interesse.

1. **Limite a seção.** Na seção, a sala tem 25 lugares, então **Matrícula Máxima**
   padrão é 25.
2. **Preenche.** A décima quarta aluna se matricula e está **Esperando #1**; a 27th é
   **#2**. Não foram emitidas faturas para elas.
3. **Um assento opõe.** Um aluno sentado saca. **#1 é promovido
   automaticamente**, faturado (é um curso pago) e ambos e você está
   notificado. **#2** se torna **#1**.
4. **Você decide crescer.** Você move a seção para um quarto de 40 lugares com
   **Alterar quarto** (razão: "mudou para a sala 300 por capacidade"). A lista de espera
   promove os novos lugares até que eles limpem ou a sala esteja cheia novamente.
5. **O termo começa.** Qualquer um ainda está esperando se torna **Oculto** e aparece em
   **Demanda desconhecida** — no próximo ano seu caso para uma segunda seção.

### Exemplo 3 — abre um segundo campus

**Objetivo:** modelar um novo campus para a cidade e rastrear o seu equipamento.

1. Crie **Câmera** _Para baixo_, e depois **Construir** _Anexo_ (campus _Para baixo_),
   e então **Salas** com a construção de _Anexo_ — o Campus de cada quarto se preenche à medida que
   _Para baixo_.
2. Com **Sincronizar cômodos para os Ativos Locais** ativado, os locais correspondentes aparecem automaticamente em
   _Downtown → Anexo_.
3. Registre os projetores e pianos do Anexo como **Assets**, colocando cada um no local de seu
   quarto. Agora equipamento, recursos e agendamento de toda a linha.

## Dia para o registrador

- **Adicione uma sala.** Mesa → Sala → Novo. Defina a capacidade e os recursos; opcionalmente, uma construção
  . Isso é o suficiente para começar a agendar contra ele.
- **Agende uma seção.** Na Agenda do Curso, escolha a **sala** (use o seletor de classificação
  , confirme **Inscrição Máxima** e salve. Cuidado avisos; conflitos
  e movimentos exagerados estão bloqueados.
- \*\*Encontre uma sala gratuita em determinado momento. \* Abra **Utilização do Quarto** para o termo e
  procure salas com lacunas (ou nenhuma seção).
- \*\*Gerencie a demanda. \* Verifique **Seções Esperadas** durante o registro; quando uma seção
  estiver acima da inscrição, aumente a tampa, mova-a para uma sala maior, ou abra uma
  nova seção. A lista de espera se promove enquanto os lugares aparecem.
- **Mova uma seção.** Use **Alterar Sala** (com um motivo) — nunca apenas deixe em branco o campo
  — então o movimento é registrado.
- **Justifique mais espaço.** Leve **Demanda desconhecida** à conversa de planejamento.

## Referência rápida

| Se você quiser... | Faça isto                                                                                                           |
| ----------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------- |
| Adicionar espaço                                                  | Criar uma sala (definir capacidade de assento)                                                   |
| Agrupar salas por local                                           | Crie Campus e Edifício, em seguida, coloque a Construção da Sala                                                    |
| Diga o que uma sala oferece                                       | Adicionar recursos da sala à sala                                                                                   |
| Diga o que um curso precisa                                       | Defina o tipo de curso do curso; adicione requisitos (modalidade → recurso)                      |
| Coloque uma seção                                                 | Defina a sala no cronograma do curso (a classe do seletor é melhor em primeiro lugar)            |
| Boné uma seção                                                    | Definir Matrícula Máxima (padrões da sala; branco = sem captura)                                 |
| Evite agendamento duplo                                           | Nada — agendamentos sobrepostos da mesma sala estão bloqueados ao salvar                                            |
| Mover uma seção, no registro                                      | Use **Mude a Sala** e dê uma razão                                                                                  |
| Deixe alunos da fila de cursos completos                          | Apenas se inscreva além do limite — extras estão esperando e promovidos automaticamente                             |
| Ver quem foi virado para fora                                     | Executar o relatório **Demanda Isolada**                                                                            |
| Encontre gratuitamente vs. quartos ocupados       | Execute o relatório **Utilização do Quarto**                                                                        |
| Rastrear equipamento em cômodos                                   | Mantenha **Salas de sincronização para Ativos Locais** ligados; registre-se em Ativos na localização de cada cômodo |
| Pular tudo isto                                                   | Deixar os tipos de curso, recursos e limites vazios; desativar a configuração de sincronização                      |

## Relacionados

- [Enrollment](enrollment.md) — como os alunos se matriculam e como a promoção da lista de espera
  e a liberação não paga se encaixa no ciclo de vida da matrícula.
- [Attendance](attendance.md) — janela de horário de check-in e a nota de fuso horário
  atrás do fuso horário do campus (informativo).
- [User Roles](../administration/user-roles.md) — who can manage rooms, course
  types, and schedules.
