# Programas

Um **programa** é aquilo em que um aluno se inscreve para obter acesso a cursos — um certificado
M.Div, um certificado de um ano, um caminho de educação contínua. É também onde
você define as regras acadêmicas e financeiras que regem todos os inscritos:
como o progresso é medido, independentemente de custar dinheiro, o que conta para
graduação, e como seus cursos e especializações são organizados.

Você autor programas inteiramente de Desk (**Programa → Novo**). Esta página caminha
através das opções e explica a parte que mais faz as pessoas viajarem —
**faixas e ênfares**.

## Como um programa é moldado

Um punhado de escolhas ortográficas define o _caractere_ de um programa. Defina estes
primeiro; tudo o resto os pendura.

| Escolha                 | Campo                                               | O que decide                                                                                                                                                  |
| ----------------------- | --------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Nível**               | `Nível do Programa`                                 | O nível (Certificado, Bachelor, Mestre, Doutorado, Continuando o Ed…) e se o programa está _em andamento_.                 |
| **Tem um fim?**         | _(espelhado)_ `Está acontecendo` | Estilo decrescente (graduação, GPA, transcrição) vs. em curso (sem fim, sem graduação). |
| **Modelo de progresso** | `Tipo de Inscrição`                                 | Medidos por **termos** concluídos (com base no tempo) ou **créditos** ganhos (baseados em créditos).    |
| **Admissões**           | `Modo de Matrícula`                                 | Aplicar somente durante janelas publicadas (Tempo) ou a qualquer momento (Continuar).                   |
| **Custo**               | `Programa Livre` + bandeiras de pagamento           | Grátis ou pago com inscrição no pagamento.                                                                                                    |

Estes são independentes — um programa pode ser _baseado em créditos_, _Contínuos_, e
_Gratuito_ de uma só vez, ou qualquer outra combinação.

### Nível do Programa e "em andamento"

Um **Nível do Programa** (Mesa → Nível do Programa) é um nível reutilizável que você anexa a um programa
— _Certificado_, _Bachelor_, _Mestre_, _Doutora_, _Continuando
Educação_, etc. Além de categorizar o programa, ele contém um interruptor
importante:

> **Is Ongoing** — _"Check this ONLY if the Program has no definitive end (no
> graduation, credits, etc.). Útil para cursos gratuitos, educação contínua,
> etc."_

Quando o nível escolhido estiver em andamento, o programa **espelhos** que, como sinalizador
'Está em andamento' e automaticamente salta tudo que assume um fim:
auditoria e solicitações de graduação, GPA e honras, a transição de antigos alunos e a etapa de Revisão Acadêmica
após retirada. Leave the level non-ongoing for any real
degree.

### Modelo de progresso — baseado em tempo vs. Créditos

Por grau (programas não-em andamento) **Tipo de inscrição** escolhe como você acompanha um estudante da
para a conclusão:

- **Baseado no tempo** — o progresso é contado em **termos**. Define \*\*Termos para conclusão
  \*\*. Os cursos podem carregar um **número de termo** sugerido, para que a auditoria saiba
  onde cada um pertence na sequência.
- **Baseado em créditos** — os alunos se matriculam em cursos em qualquer termo e o progresso é
  contado em **créditos**. Define **Créditos para conclusão**.

**Anos Máximos a Graduado** (opcional, anos fracionários permitidos, `0` = sem limite)
limita quanto tempo um aluno tem; na matrícula do sistema marca uma data máxima
de graduação da _data de matrícula + deste número de anos_.

### Admissões — Tempo vs. Continuidade

**Modo de inscrição** controla como os candidatos se encontram:

- **Tempo** — aplicativos são aceitos somente durante a publicação
  [Admissão de Termos](enrollment.md) janelas.
- **Contínuo** — Os candidatos podem aplicar a qualquer momento; os rótulos dos botões "Aplicar" públicos
  eles ao atual termo acadêmico.

### O formulário de aplicação

O botão público "Aplicar" abre um **Formulário Web** que cria um candidato do aluno.
A forma embutida é intencionalmente completa (pessoal, educação, emprego,
igreja, declaração doutrinal, assinatura…), o que é certo para um programa de graus, mas
muito mais pesado do que um curso livre ou necessidades de trilhos de educação contínua.

Para usar um formulário mais simples, defina **Formulário Web de Aplicativo** no programa. O botão
abre esse formulário em vez disso. A rota é resolvida neste pedido:

1. Se definido, o **Formulário Web de Aplicativo** do programa.
2. **Configurações do seminário → Formulário Web de aplicativo padrão**, se definido (um padrão
   para cada programa que não escolhe o seu).
3. A forma "aplicador-aluno" embutida como o recurso final.

Então você pode deixar a maioria dos programas em branco e apontar seus programas gratuitos/CE apenas em um formato
curto — ou virar o _padrão_ e reservar o formato longo para os poucos programas
que precisarem.

> \*\*Construa seu próprio formulário; não edite o próprio formulário. \* O formulário
> `applicant` enviado é um formulário web _padrão_ — ele é re-sincronizado do aplicativo
> a cada atualização, e as alterações que você fizer no Desk são substituídas. Em vez disso,
> **crie um novo formulário Web** (Desk → Formulário Web → Novo) para o _Aplicativo do Aluno_
> com apenas os campos que você deseja. Suas próprias formas aparecem no banco de dados e
> nunca são experimentados. O seletor de **Aplicação Web Form** lista apenas Formulários Web
> criado sobre o candidato dos alunos.

Algumas coisas para acertar em um formulário personalizado:

- **Mantenha os campos pré-preenchidos.** Inclua `programa` e`academic_term` (e
  `term_admission` se você aceitar aplicativos com tempo). O botão Aplicar passa
  isso no URL, e Frappe só os pré-preenche se o formulário realmente conter
  esses campos. Você também precisa do `Email do Aluno`, como isso é necessário para o login.
  Você **não** precisa adicionar o `academic_year` — ele é derivado automaticamente de
  do termo acadêmico, então deixe do formulário.
- **For the doctrinal statement, just add the `signdoctrine` signature field.**
  The current admission Doctrinal Statement is rendered automatically as a
  read-only block directly above the signature on every Student Applicant form
  (built-in or custom) — you don't add a `ds2` field and you don't write any
  script.
- **Defina seu próprio comportamento de sucesso.** O formulário embutido redireciona para a página de pagamento
  após o envio. Isso redireciona a vida na forma interna, então um formulário
  personalizado para um programa **gratuito** não o carrega — defina o **URL de sucesso** do novo formulário
  (ou uma mensagem de sucesso) para enviar candidatos onde quer que isso aconteça. . um simples
  de agradecimento em vez de uma página de pagamento.

### Custo e pagamento preferidos

- **Programa gratuito** — ignora a faturação de matrícula e ignora a Revisão Financeira sobre o cancelamento
  da retirada.
- For paid programs, **Require Payment Before Enrollment** holds each course
  enrollment at _Awaiting Payment_ until the student pays (or reaches the
  **Minimum Payment %**). **Exigir verificação de funcionários das matrículas do curso**
  faz um registro aprovar um rascunho de matrícula do aluno antes que eles possam pagar.

A mecânica da matrícula de pagamentos é coberta pelo
[Enrollment](enrollment.md).

## Cursos

A tabela de **cursos** lista todos os cursos que pertencem ao programa. Para cada
linha:

- **Mandatory for this program** (`required`) — every student must pass it to
  graduate. Deixe-o desmarcado para **eletivos**.
- **Obrigatório na matrícula do programa** (`pgm_course_reqonenroll`) — o aluno está
  **matriculado automaticamente** neste curso; ninguém deve registrá-lo manualmente.
  Isto está **separado** de _Obrigatório para este programa_ acima: que bandeira é sobre
  _graduação_, este é sobre _assinatura_. Um curso pode ser um, o
  outro, ambos, ou nenhum. Veja **Alunos com inscrição automática** abaixo.
- **Créditos para este programa** — o mesmo curso pode valer um número
  diferente de créditos em diferentes programas, então créditos ao vivo na linha do programa.
- **Número de termo** — um termo sugerido, usado para sequenciar a auditoria.
- **Allow more than once** — permit the course to count for credit more than
  once.
- **Desativado** (+ **Desativar Reason**) — aposentar um curso deste currículo
  sem excluir histórico. Students who already took it keep their record; new
  students no longer see it. O sistema usa **Desabilitado** automaticamente.

> **Liste todos os cursos aqui.** Mesmo os cursos que importam apenas uma faixa ou
> a ênfase devem aparecer nesta tabela principal dos cursos. As tabelas monitoradas abaixo apenas
> ponto nos cursos que já existem aqui.

### Inscrito automaticamente os alunos nos cursos

Marque **Obrigatório na matrícula dos programas** em um curso e os alunos já não possuam
para se inscreverem - o sistema as inscreve para você. This is meant for the
courses everyone in the program takes (a required orientation, a first-term core
sequence), so the registrar doesn't enroll each student one by one.

Algumas coisas que vale a pena ser entendidas sobre _quando_ e _como_ isso acontece:

- \*\*Espera por uma oferta. \* Um aluno só pode ser matriculado uma vez que o curso esteja
  sendo realmente oferecido — isto é, uma vez [Agenda do Curso](enrollment.md) para ele
  é **aberto para matrícula**. Se o curso não for oferecido no termo o aluno
  se matricular, nada falha: o aluno está simplesmente matriculado mais tarde, automaticamente, o
  momento em que uma futura oferta abrir.
- **It picks one offering sensibly.** When the course is open in more than one
  place at once, the system prefers an offering in the student's own enrollment
  term, then an online (**Virtual**) section, then the earliest-starting one.
- **Os programas pagos ainda são cobrados normalmente.** "Obrigatório na matrícula" **não** significa que
  quer dizer gratuitamente. Em um programa pago, a inscrição automática é faturada e fica sentada em
  _Aguardando pagamento_ exatamente como uma matrícula manual até que o aluno page.
- \*\*Os pré-requisitos são respeitados. \* Se o curso tiver um pré-requisito
  obrigatório não atendido, o aluno **não** está matriculado automaticamente; em vez de um a fazer é elevado
  para que o registrador ordene a sequência.
- **Sem inscrição dupla.** Um aluno já inscrito (ou quem já passou)
  o curso está sozinho.

> \*\*A lista é corrigida no tempo de matrícula. \* Em quais cursos um aluno é
> matriculado automaticamente é decidido **quando sua matrícula é submetida**, do
> sinalizadores conforme eles estão naquele dia. Ao virar a bandeira de um curso **mais tarde** o
> **não** volta e inscreva alunos que já estão no programa — pela
> design, então uma alteração do currículo nunca silenciosamente inscreve um grupo existente.
>
> Para empurrar um curso recém marcado para os alunos que _já estão matriculados_ , abra o Programa
> e use **Ações → Aplicar Inscrição obrigatória para Alunos Ativos**.
> Ele adiciona o novo curso à lista de cada aluno ativo e os matricula onde uma oferta
> é aberta. O botão só aparece quando o programa tem pelo menos um curso
> de matrícula obrigatória. e sempre _acrescenta_ — ele nunca remove um curso
> que um aluno já estava configurado.

## Acompanhamento e ênfases

Um **track** é um grupo nomeado de cursos dentro de um programa. Tracks come in two
flavors, distinguished by one checkbox — **Program Emphasis?** — and they behave
very differently.

### Faixas organizacionais (não enfatizadas)

Sair da \*\*Colocação do programa? \* desmarcado para usar uma faixa como um **requisito
carve-out** — uma maneira de dizer _"o programa requer N créditos deste grupo de cursos
."_

> Exemplo: \*"Os alunos devem ganhar 6 créditos de grego bíblico. \* Criar uma faixa
> _Grego bíblico_, defina **Créditos da Faixa Obrigatória = 6**, e liste os cursos Gregos
> sob ele (na tabela **Cursos por faixa**). O aluno pode satisfazer
> os 6 créditos de qualquer um desses cursos.

As faixas organizacionais são sobre a estrutura **de comunicação e agrupamento**.
Os alunos **não** os declaram; eles não são especializações em uma transcrição.

### Empregos (uma especialização declarada)

Verifique **A Emphasis do Programa?** para fazer uma trilha **declarada** — uma ênfase do
no Antigo Testamento, uma ênfase em seu aconselhamento, uma ênfase em Missões. Empregados são
ativamente acompanhados pela auditoria do aluno e (exceto aconselhamento marcado) **portar
graduação**.

Campos de chave em uma faixa de energia:

- **Créditos da faixa necessários** (`adicionar`) — o mínimo de créditos que o aluno
  deve ganhar dentro da ênfase. Estes contam para o total do programa.
- **Acompanhar Tecnologia de Créditos** (`max_credits`, `0` = ilimitado) — o máximo de
  créditos de ênfase que contam para o grau. Créditos além do limite ainda são
  ganhos, mas pare de contar para o total do programa.
- **Declaração de ênfase** — _quando_ um aluno leva ela em:
  - **Na matrícula** — deve ser escolhido antes da inscrição ser submetida.
  - **A qualquer momento** — pode ser declarado mais tarde (opcionalmente apenas após ganhar um
    **Min Credits to Declare**).
  - **Autor automático** — atribuído automaticamente quando o aluno atende aos requisitos de crédito de
    enfatizado.
- **Somente Consultório** — a ênfase é informativa e **não** bloqueia a graduação
  .
- **Fortalecimento de fundo?** — marca a ênfase padrão (por exemplo, _General
  Studies_) atribuída a alunos que nunca declaram uma expressão específica.

**Cursos obrigatórios para uma ênfase** são definidos na tabela **Cursos por Track**
marcando **Mandatório?** para um par (trilha, curso). Um aluno com essa ênfase
deve passar esses cursos específicos, acima de atender ao total de crédito.

### Múltiplos destaques

Se **permitir Múltiplas Fortalezas** estiver ativado, um aluno pode declarar mais de um. O
\*\*Políticas de sobreposição de Emphasis \*\* e decide como os créditos se somam:

- **Banco de Crédito Compartilhado** — todos os enfatos são sorteados no mesmo total de programa. Um curso
  pode ajudar a satisfazer dois enfatos de uma só vez.
- **Créditos adicionais necessários** — cada ênfase além do primeiro adiciona seus
  créditos de faixa _no topo de_ total do programa, então uma dupla ênfase genuinamente
  custa mais créditos.

### Exemplos práticos

**1 — Uma exigência de idioma (faixa organizacional).**
_Objetivo: 6 créditos de grego, a escolha do aluno no curso._
Faixa _Grego Bíblico_, **Emfágio do programa? off**, **Rastrear Créditos Necessários =
6**; liste os cursos gregos elegíveis em Cursos por faixa. Os documentos da faixa
a exigência e agrupa os cursos; o aluno escolhe o valor de 6 créditos.

**2 — An Old Testament emphasis declared up front.**
_Goal: students choose OT at enrollment, take 12 emphasis credits including two
required courses._
Track _Old Testament_, **Program Emphasis? on**, **Rastrear Créditos Necessários = 12**,
\*\*Declaração de Emphasis = Na Inscrição \*\*. Em Cursos por faixa, adicione os cursos
AT e o tick **Mandatório?** em _Hebreu I_ e \*Teologia AT \*. The student must
choose this emphasis before submitting enrollment, pass both required courses,
and reach 12 OT credits.

\*\*3 — Uma ênfase aconselhável declarada mais tarde. \*
O mesmo que acima, mas **Declaração de Emphasis = a qualquer momento** e **Min Credits to
Declare = 30** - o aluno só pode pegá-la depois de 30 créditos do programa.

**4 — ênfase dada automaticamente.**
Define **Declaração de Emfásis = concessão automática**. O aluno nunca o declara; uma vez que
ele cumpriu a exigência de crédito da faixa, o sistema registra o ênfase
para ele.

**5 — Dobre ênfase dupla que custa mais.**
Ative **Permitir múltiplas inserções** e defina **Políticas de sobreposição de Emphasis =
Créditos adicionais necessários**. Um aluno que declara ambos _Antigo Testamento_ e
_Missões_ deve completar o programa no total de **mais** do segundo controle de
créditos.

**6 — Uma ênfase na segurança dos cidadãos.**
Crie _Estudos Gerais_, tick **Ephasis do programa?** e **Impacto de resposta instantânea?**.
Estudantes que nunca declaram outra coisa são tratados como sendo nos Estudos Gerais
para graduação.

## GPA, honra e graduação

Por programas de graus:

- **Base para GPA** — o topo da sua escala (US = 4.0; outros variam).
- **GPA ponderada pelo crédito** — quando ativada, o GPA é ponderado pelos créditos do curso; quando desativado,
  é uma média simples.
- **Aceitar Notas de Transferência na GPA** — se as notas de curso transferidas na
  GPA (também requer que o Seminário de Parceiros de origem permita isso).
- **Honras Níveis** — Uma lista de nomes de honra com GPAs mínimas (por exemplo, _Cum Laude_
  às 3.5). O nível mais alto que um aluno se qualifica para séries em sua matrícula.
- **Os alunos podem solicitar a graduação** + **Solicitação de graduação** (_Inscrição
  em cursos finais_ vs. _Cursos finais passados_) — quando e quando um aluno pode fazer
  arquivar um [Pedido de Graduação](graduation-request.md) em sua página de auditoria.

Os requisitos para não-curso que um programa exige (letras, caapel, projetos, etc.)
são configuradas separadamente — veja [requisitos de graduação](graduation-requirements.md).

## Publicando na web

A aba **Web** controla a página do programa virada para o público: **Rota** (URL slug),
**Descrição** e imagens da lista do programa, **Descrição do Programa** e
**Requisitos**, campos de duração para ordenação/filtragem, e dois interruptores de visibilidade
— **Mostrar Windows Matrícula na Web** e **Exibir CTA na Web**
(ambos fora por padrão; o CTA não tem efeito para programas contínuos, que se aplicam
a qualquer momento). Desmarque **Publicar na web** para ocultar um programa completamente.

## Como tudo aparece na Auditoria do Programa

Tudo o que acima converge na página **Auditoria do Programa** (também visível para
funcionários). Para cada aluno inscrito, ele mostra:

- **Crédito / termo progride** em direção ao total do programa.
- **Cursos obrigatórios do programa** e seus status.
- **Cada expressão de ênfase** — créditos necessários vs. ganhos (respeitando o teto
  , e quaisquer cursos obrigatórios ainda ausentes.
- Os **requisitos de graduação** paralelos (provas que não são do curso).

A student is _eligible to graduate_ only when the credit/term total is met, all
program-mandatory courses are passed, every non-advisory emphasis has met its
credits and required courses, and the graduation requirements are clear.

## Referência rápida

| Se você quer…                                                                                                                                                                               | Faça isto                                                                                                                                                                                               |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Criar programa de graus                                                                                                                                                                     | Novo Programa; escolha um Nível do Programa não em andamento; defina o Tipo de Inscrição + Termos/Créditos para conclusão                                                                               |
| Crie uma oferta gratuita e sem fim (por exemplo, uma página de Cursos Gratuitos no site para treinar crentes e servir como uma ferramenta de marketing para o seminário) | Use um nível de programa com **Em andamento**; marque **Programa Livre** (muitas vezes, o modo de inscrição = continua)                                                              |
| Acompanhe o progresso por créditos, qualquer pedido                                                                                                                                         | Tipo de Matrícula = **Baseado em Créditos**; definir Créditos para conclusão                                                                                                                            |
| Marque um curso necessário para todos                                                                                                                                                       | Escolha **Obrigatório para este programa** em seu registro de Cursos                                                                                                                                    |
| Inscrever todos os alunos de um curso automaticamente                                                                                                                                       | Escolha **Obrigatória na matrícula do programa** em sua linha de Cursos                                                                                                                                 |
| Aplicar um curso auto-sinalizado aos alunos atuais                                                                                                                                          | Programa → **Ações → Aplicar Mandatory-on-Inscrição para Alunos Ativos**                                                                                                                                |
| Remover um curso do currículo                                                                                                                                                               | Marque **Desativado** na linha de seus Cursos e dê um motivo                                                                                                                                            |
| Exigir créditos de N de um grupo de cursos                                                                                                                                                  | Adicione uma faixa organizacional (Emphasis do programa? **desconto**) com **controle de créditos necessários**                                                                      |
| Oferecer uma especialização declarada                                                                                                                                                       | Adicione uma faixa com **Emphasis do programa? on**; definir créditos, cursos requeridos e tempo de declaração                                                                                          |
| Permitir que os alunos declarem duas especializações                                                                                                                                        | **Permitir Múltiplas Fortalezas**; escolha uma **Política de sobreposição de Emphasis**                                                                                                                 |
| Dar aos alunos não declarados um padrão                                                                                                                                                     | Marque uma ênfase como **Impacto de Fallback ?**                                                                                                                                                        |
| Deixe os alunos aplicarem a rodada de ano                                                                                                                                                   | Modo de Matrícula = **Continuar**                                                                                                                                                                       |
| Use um aplicativo mais curto para um programa grátis/CE                                                                                                                                     | Crie um Formulário Web no _Aplicativo do Aluno_; defina-o como o **Formulário Web do aplicativo** (ou o **Formulário Web do aplicativo** do programa nas configurações do seminário) |
| Mostrar o programa (e aplicar o botão) publicamente                                                                                                                      | Aba Web → **Publicar na web**, **Exibir CTA na Web**                                                                                                                                                    |

## Relacionados

- [Enrollment](enrollment.md) — como os alunos se matriculam e se inscrevem no curso
  com pagamento para programas pagos.
- [Requisitos de graduação](graduation-requirements.md) — os requisitos
  para não-curso (letras, caapela, projetos) que se sentam ao lado dos cursos.
- [Pedido de graduação](graduation-request.md) — o fluxo de pedido/aprovação.
- [Calendário Acadêmico](academic-calendar.md) — termos e as janelas de matrícula
  que abrem cursos para inscrição.
