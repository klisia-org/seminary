# Anúncios},{

Os Anúncios do Seminário permitem enviar uma única mensagem para todos os estudantes matriculados neste período letivo, todos os instrutores que lecionam neste período, ou qualquer combinação de que você precise. As mensagens são entregues por e-mail e também aparecem no aplicativo do estudante/instrutor em **Anúncios**. Os destinatários são resolvidos a partir de dados ao vivo no momento do envio, portanto estudantes que se matriculem ou cancelem a matrícula entre a redação e o envio serão incluídos corretamente.

## Quando usar

- Lembretes de prazos (datas de trancamento, janelas de prova, envio de notas).
- Mudanças no campus ou no calendário (fechamentos, feriados, alterações de agenda).
- Avisos de políticas ou administrativos que precisam alcançar todo um público de uma só vez.

Para mensagens com escopo de um único curso (uma turma de estudantes + seu instrutor), use o painel de **Anúncios** do próprio curso na página do curso. Os Anúncios do Seminário são para públicos que abrangem várias turmas.

---

## Quem pode enviar

A função **Academics User** pode criar, enviar e cancelar Anúncios do Seminário. Estudantes e instrutores podem ler os anúncios que receberam, mas não podem redigir.

---

## Criando um anúncio

Abra **Desk → Seminary Announcement → New**.

### 1º. Assunto e mensagem

- **Assunto** — a linha de assunto do e-mail. Mantenha curto e específico: "Semana de provas — prédio fechado na sexta" é melhor que "Anúncio importante".
- **Período Letivo** — por padrão é o período atual. Altere apenas se você estiver anunciando algo para um período diferente (por exemplo, um aviso prévio ao público do próximo período).
- **Mensagem** — o corpo. Rich text completo: títulos, listas, links, negrito, imagens embutidas.

### 2º. Público

Os anúncios constroem sua lista de destinatários a partir de consultas ao vivo. Escolha uma ou mais regras de público — elas são combinadas (união) e depois desduplicadas por e-mail.

| Regra                                                      | Quem inclui                                                                                                                                                                                                                                                                                                                     |
| ---------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Todos os estudantes matriculados neste período letivo**  | Todo estudante com uma Matrícula em Curso não cancelada em um Cronograma de Curso para o período selecionado.                                                                                                                                                                                                   |
| **Todos os instrutores que lecionam neste período letivo** | Todo instrutor listado em qualquer Cronograma de Curso para o período selecionado.                                                                                                                                                                                                                              |
| **Apenas estes Programas**                                 | Restringe o público de estudantes aos programas listados. Deixe em branco para todos os programas. Não afeta os instrutores.                                                                                                                                                    |
| **Apenas estes Cronogramas de Curso**                      | Restringe para aquelas turmas específicas. Inclui os estudantes daquelas turmas e — se "Todos os instrutores que lecionam neste período letivo" também estiver marcado — apenas os instrutores dessas turmas. Use isto para enviar mensagem a "todos em Teologia 101, Turma A". |
| **Filtro Personalizado** _(avançado)_   | Escolha qualquer DocType e um filtro JSON. Útil para casos de borda: "todos os estudantes no programa MDiv com cancelamento pendente", "todos os instrutores de um departamento específico".                                                                                    |

Você deve escolher pelo menos uma regra. Caso contrário, o envio é bloqueado.

### 3º. Pré-visualizar Destinatários

Antes de enviar, salve o rascunho e clique em **Pré-visualizar Destinatários** no menu superior direito do formulário. Uma caixa de diálogo mostra a contagem total e uma amostra de até 50 linhas (tipo, nome, e-mail). Use isso para uma verificação rápida de que você não direcionou por engano o programa errado ou esqueceu um curso.

Se a contagem na pré-visualização for zero, suas regras de público estão muito restritas — nada será enviado nesse estado também. O formulário informa o mesmo no momento do envio.

### 4º. Enviar imediatamente ou agendar

- Deixe **Send At** em branco para enviar no momento em que você clicar em Enviar.
- Preencha **Send At** com uma data/hora futura para agendar. O anúncio é salvo com status **Na Fila** e processado pelo agendador que roda a cada hora. A granularidade é de aproximadamente uma hora — não use isso para mensagens sensíveis ao tempo que precisem sair em um minuto exato.

### 5º. Enviar

Clique em **Enviar**. Neste momento:

1. A consulta do público é executada e a lista resultante é congelada na aba **Destinatários** como um registro permanente de auditoria.
2. Se o envio for imediato, os e-mails entram na fila na hora; se for agendado, entram na fila no próximo ciclo do agendador após o horário de Send At.
3. O status avança **Rascunho → Na Fila → Enviando → Enviado**. Uma transação SMTP com falha para um destinatário marca aquela linha como **Falhou** e registra o erro; o restante da lista ainda é enviado.

Após o envio, o anúncio é selado — você não pode editar o assunto, o corpo ou o público. Se precisar corrigir algo, cancele e faça uma alteração (ou simplesmente crie um novo anúncio).

---

## Onde os destinatários veem

Em dois lugares:

- **E-mail** — entregue via a Email Account de saída configurada do seminário.
- **Anúncios** na barra lateral do app — estudantes e instrutores veem uma lista de todos os anúncios que receberam, mais recentes primeiro, dentro do app principal. Não é necessário fazer login no Desk.

A lista no app relaciona destinatários pelo usuário ou pelo e-mail, então funciona mesmo para quem não faz login com o mesmo e-mail em que recebe as mensagens.

---

## Acompanhando a entrega

Abra um anúncio enviado e vá até a aba **Destinatários**. Cada linha mostra a parte (Estudante / Instrutor / personalizado), e-mail e um **Status**:

- **Enviado** — e-mail aceito pelo servidor de saída.
- **Falhou** — um erro de entrega. A coluna **Erro** contém a mensagem.
- **Pendente** — ainda não processado (agendado para mais tarde ou em andamento).

A contagem de destinatários e o status geral do anúncio no topo dão uma visão rápida. Aprofunde-se na aba para ver os detalhes por pessoa.

---

## Tarefas comuns

### Enviar um lembrete para um programa específico

1. Novo Anúncio do Seminário.
2. Marque **Todos os estudantes matriculados neste período letivo**.
3. Em **Apenas estes Programas**, adicione o programa. Deixe instrutores e cursos em branco.
4. Pré-visualize — confirme que apenas os estudantes do programa correto aparecem. Enviar.

### Enviar mensagem juntos aos estudantes e ao instrutor de uma mesma turma

1. Novo Anúncio do Seminário.
2. Marque **Todos os estudantes matriculados neste período letivo** e **Todos os instrutores que lecionam neste período letivo**.
3. Em **Apenas estes Cronogramas de Curso**, adicione a turma.
4. Pré-visualize. Enviar. A lista de estudantes é restringida àquela turma; a lista de instrutores é restringida aos instrutores daquela turma.

### Enviar e-mail a todos que lecionam, em todos os programas

1. Novo Anúncio do Seminário.
2. Marque **Todos os instrutores que lecionam neste período letivo**. Deixe todo o resto em branco.
3. Pré-visualize. Enviar.

### Enviar e-mail para um recorte personalizado (avançado)

Use **Filtro Personalizado** quando nenhuma das regras nativas servir:

- **DocType do Filtro:** o doctype a consultar (`Student`, `Instructor` ou qualquer outro com um campo de e-mail).
- **Campo de E-mail:** o nome da coluna de e-mail nesse doctype (por exemplo, `student_email_id` para Student, `prof_email` para Instructor).
- **Filtros (JSON):** uma expressão de filtro do Frappe, por exemplo, `[[\"Student\",\"enabled\",1]]`.

Combine com as regras nativas ou use sozinho.

---

## Perguntas frequentes

**Posso editar um anúncio após enviar?**
Não. O envio congela o assunto, o corpo e o instantâneo de destinatários — isso é intencional, para que o que foi enviado sempre corresponda ao que está registrado. Se você precisar corrigir algo, cancele e envie um novo anúncio informando a correção.

**O que acontece se a Email Account de saída não estiver configurada?**
O envio ainda será concluído — os destinatários são congelados e as linhas entram no estado Pendente — mas nenhum e-mail sai do sistema. Configure ou corrija a Email Account e a fila será esvaziada na próxima tentativa.

**E se um estudante cancelar a matrícula entre a redação e o envio?**
A lista de destinatários é congelada no momento do envio, e não no momento do disparo. Se alguém cancelar a matrícula entre o envio e o momento agendado para envio, ainda receberá a mensagem. Se você precisar reprocessar os destinatários, cancele o anúncio na fila e crie um novo mais próximo do horário de envio.

**Posso agendar um anúncio para se repetir?**
Não — cada anúncio é de uma única vez. Para lembretes recorrentes (lembretes mensais de mensalidade, avisos semanais de frequência), use Frappe Notifications com um gatilho agendado.

**Isso respeita as preferências de cancelamento de inscrição?**
Sim. As regras padrão da fila de e-mails do Frappe se aplicam: quem cancelou a inscrição nos e-mails deste seminário é ignorado.
