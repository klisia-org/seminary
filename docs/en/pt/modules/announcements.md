# Anúncios},{

Seminary Announcements let you send a single message to everyone enrolled this term, everyone teaching this term, all alumni, or any combination you need. Messages are delivered over the channels you choose — email and the in-app inbox by default, with SMS, WhatsApp, and Telegram available for urgent reach. Os destinatários são resolvidos a partir de dados ao vivo no momento do envio, portanto estudantes que se matriculem ou cancelem a matrícula entre a redação e o envio serão incluídos corretamente.

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

### 1º. Subject, category, and message

- **Subject** — the email/message subject line. Mantenha curto e específico: "Semana de provas — prédio fechado na sexta" é melhor que "Anúncio importante".
- **Academic Term** — required when the audience is term-scoped (enrolled students, teaching instructors, or specific course schedules); optional for an all-alumni or custom-filter broadcast. Defaults to the current term.
- **Category** — the routing/consent class (default **Academic**). Most announcements are Academic. Choose **Emergency** for a genuine calamity (campus closure, safety alert): Emergency messages **bypass recipient opt-outs and the hourly send throttle** so they reach everyone at once. Promotional messages only reach recipients who have opted in.
- **Send via channels** — leave empty to send **Email + In-App** (the default). Add **SMS**, **WhatsApp**, **Telegram** (urgent reach), **Voice** (an automated call that reads the message), or **Print** (a PDF letter to mail). Each needs a configured provider account — see [Communication](communication.md); Print works out of the box. Submit is blocked if you pick a channel with no provider account configured.
- **Mensagem** — o corpo. Rich text completo: títulos, listas, links, negrito, imagens embutidas. Used for Email, In-App, **and Print** (the printed letter). You can personalize it with Jinja tokens that resolve per recipient: `{{ recipient.first_name }}`, `{{ recipient.name }}`, `{{ recipient.email }}` (and `{{ person.* }}` for spine fields). Example: _"Dear {{ recipient.first_name }},"_. Syntax errors are caught when you save.
- **Voice Recording** — _(shown when Voice is selected)_ an optional MP3/WAV the call plays instead of reading the text aloud (e.g. the director records the message). Up to ~40 MB; the file is made public so the carrier can fetch it.
- **Short Message** — a plain-text version for the length-limited / spoken channels (SMS, WhatsApp, Telegram, Voice). Leave it blank and the system strips the rich message down to plain text automatically; fill it in when you want a tighter wording for a 160-character world or a call.
- **Email + In-App fallback** _(on by default)_ — if a recipient can't be reached on any selected channel (no phone/Telegram connected, or opted out), they're sent Email + In-App instead, so the announcement still arrives. Email is always available. Turn it off only if you want a channel-exclusive send.

#### Print options

When **Print** is among the channels, a **Print Options** section appears:

- **Letter Head** — _Seminary Default_ (the one set in Seminary Settings), _None_, or _Specific_ (pick any Frappe Letter Head). The chosen letterhead wraps the printed PDF letter.
- **Print mailing labels** — also produce a sheet of mailing labels (PDF). Pick a **Label Format** — a **Mailing Label Format** record. Common Avery layouts (5160, 5161, 5163, L7160) are shipped; a seminary can add its own by measuring its label stock (columns, rows, label size, margins in mm) under **Mailing Label Format**. Use the **Mailing Labels (PDF)** button to generate/download; labels are also attached to the announcement when it's sent. Labels are produced for recipients with a postal address (on their Person record, or a Student record); those without one are listed as omitted so you know who to follow up.

**Printing the letters.** While drafting, **Letter Preview (PDF)** shows a single letter (subject + message in the letter head, personalized for one recipient) so you can check the layout. After you **submit**, the button becomes **Print Letters (PDF)**: the official, consolidated document — every recipient's personalized letter, one per page, ready to print and mail. It's also generated automatically on send and attached to the announcement (alongside the mailing labels), so the finished letters live on the announcement itself.

### 2º. Público

Os anúncios constroem sua lista de destinatários a partir de consultas ao vivo. Escolha uma ou mais regras de público — elas são combinadas (união) e depois desduplicadas por e-mail.

| Regra                                                      | Quem inclui                                                                                                                                                                                                                                                                                                                     |
| ---------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Todos os estudantes matriculados neste período letivo**  | Todo estudante com uma Matrícula em Curso não cancelada em um Cronograma de Curso para o período selecionado.                                                                                                                                                                                                   |
| **Todos os instrutores que lecionam neste período letivo** | Todo instrutor listado em qualquer Cronograma de Curso para o período selecionado.                                                                                                                                                                                                                              |
| **All alumni**                                             | Every enabled Alumni Profile. Term-independent — ignores the term/program/course narrowing. Use for alumni newsletters or invitations.                                                                                                                                          |
| **Apenas estes Programas**                                 | Restringe o público de estudantes aos programas listados. Deixe em branco para todos os programas. Não afeta os instrutores.                                                                                                                                                    |
| **Apenas estes Cronogramas de Curso**                      | Restringe para aquelas turmas específicas. Inclui os estudantes daquelas turmas e — se "Todos os instrutores que lecionam neste período letivo" também estiver marcado — apenas os instrutores dessas turmas. Use isto para enviar mensagem a "todos em Teologia 101, Turma A". |
| **Filtro Personalizado** _(avançado)_   | Escolha qualquer DocType e um filtro JSON. Útil para casos de borda: "todos os estudantes no programa MDiv com cancelamento pendente", "todos os instrutores de um departamento específico".                                                                                    |

Você deve escolher pelo menos uma regra. Caso contrário, o envio é bloqueado.

### 3º. Pré-visualizar Destinatários

Antes de enviar, salve o rascunho e clique em **Pré-visualizar Destinatários** no menu superior direito do formulário. A dialog shows a reachability tally — **how many are reachable on the channels you picked**, broken down per channel, and how many will rely on the Email/In-App fallback — plus a sample of up to 50 rows with a ✓/✗ **Reachable** column (with the reason: "no address" or "opted out"). Use this to sanity-check the audience _and_ to spot, before sending, when an urgent SMS/WhatsApp blast would actually reach only a fraction of people (e.g. "SMS 12 of 32") so you can act on it.

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

Wherever you sent it:

- **E-mail** — entregue via a Email Account de saída configurada do seminário.
- **In-App** — the **Inbox / Announcements** in the app sidebar lists every message a person received, most recent first. Não é necessário fazer login no Desk.
- **SMS / WhatsApp / Telegram** — if selected and the recipient has a number/chat connected for that channel, the Short Message is delivered there too.

A lista no app relaciona destinatários pelo usuário ou pelo e-mail, então funciona mesmo para quem não faz login com o mesmo e-mail em que recebe as mensagens. A recipient who has no address for a chosen channel (e.g. no Telegram connected) simply doesn't get that copy; the other channels still go out.

---

## Acompanhando a entrega

Abra um anúncio enviado e vá até a aba **Destinatários**. Cada linha mostra a parte (Estudante / Instrutor / personalizado), e-mail e um **Status**:

- **Sent** — at least one of the chosen channels reached the recipient (any successful channel marks the recipient Sent).
- **Failed** — every channel attempted for that recipient failed. A coluna **Erro** contém a mensagem.
- **Pendente** — ainda não processado (agendado para mais tarde ou em andamento).

A contagem de destinatários e o status geral do anúncio no topo dão uma visão rápida. Aprofunde-se na aba para ver os detalhes por pessoa. For full per-channel detail (which channels were tried, delivery receipts), open the recipient's Person record and its **Conversation** tab, or the **Communication Log** list filtered by this announcement.

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

**Does this respect unsubscribe preferences?**
Yes, by category. A recipient who has opted out of the announcement's category on a channel is skipped for that channel — except for **Emergency** announcements, which are delivered regardless of consent. Promotional announcements only reach recipients who have explicitly opted in. Recipients manage these preferences on their portal **Preferences** page.
