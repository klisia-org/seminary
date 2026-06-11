# Solicitação de Formatura},{

A **Solicitação de Formatura** é o requerimento formal que o estudante apresenta para se formar. É o momento em que a Secretaria Acadêmica deixa de perguntar _"este estudante poderia se formar?"_ e passa a processar _"este estudante quer se formar neste período"._ Ela pode ter uma taxa opcional, passa por revisão acadêmica e financeira e termina — após ambas as revisões — em `Approved`.

Este módulo é **opt-in por programa**. As escolas que tratam a formatura inteiramente pelo lado da secretaria (sem solicitação iniciada pelo estudante) deixam o recurso desativado e usam a página [Auditoria do Programa](graduation-requirements.md) como uma visão passiva de elegibilidade.

## Visão geral

Duas perguntas aparecem lado a lado na página de Auditoria do Programa:

| Pergunta                                                        | Respondido por                                                                                                         |
| --------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------- |
| _Este estudante atendeu a todos os requisitos para se formar?_  | O banner de elegibilidade da auditoria (`Eligible` / `Conditionally Eligible` / `Not Yet Eligible`) |
| _Este estudante solicitou formalmente se formar neste período?_ | O CTA de Solicitação de Formatura abaixo do banner                                                                     |

A primeira é automática. A segunda é uma ação explícita do estudante que lança uma taxa, aparece na fila da Secretaria Acadêmica e passa por revisão.

## Ativar em um programa

No doctype **Program**, dois novos campos — ambos ocultos para programas em andamento — ligam o fluxo:

- **Estudantes Podem Solicitar Formatura** (Checkbox) — a chave mestre. Quando desativado, não há CTA, nenhuma candidatura é calculada e nenhuma Solicitação de Formatura pode ser apresentada para este programa. Use isto para programas tratados inteiramente pela Secretaria Acadêmica.
- **Gatilho da Solicitação de Formatura** (Seleção, obrigatório quando o checkbox está marcado) — quando o estudante se torna elegível para protocolar:
  - **Matriculado nas disciplinas finais** — o estudante se torna candidato no momento em que as disciplinas em que está atualmente matriculado, _se todas forem aprovadas_, encerrariam o programa. Use quando você deseja visibilidade antecipada (começar a preparar o diploma, organizar a cerimônia) e confia que o estudante não fará a solicitação até estar confiante.
  - **Aprovado nas disciplinas finais** — o estudante só se torna candidato depois que as notas finais são lançadas e a matemática de elegibilidade é satisfeita. Use quando a política é "sem participar da cerimônia se você pode reprovar na última disciplina".

> **Dica.** Os dois modos de gatilho usam a mesma lógica de elegibilidade. A diferença é se disciplinas **em andamento** contam para o cômputo final. Se você não tiver certeza de qual escolher, **Aprovado nas disciplinas finais** é a opção conservadora.

## Como o estudante recebe o CTA

O sistema mantém um sinalizador gerenciado pelo sistema em cada Matrícula no Programa chamado `grad_candidate`. Ele é reavaliado automaticamente sempre que o estado da PE muda — matrícula em disciplina, cancelamento, lançamento de notas ou qualquer edição da secretaria. O estudante não faz nada para "ativar" seu CTA; ele simplesmente aparece quando as condições são atendidas.

`grad_candidate = 1` requer **todos** os itens:

- A marcação **Estudantes Podem Solicitar Formatura** do programa está ligada e o **Gatilho da Solicitação de Formatura** está definido.
- Todas as disciplinas obrigatórias do programa estão pelo menos _Em andamento_ (ou _Concluídas_, dependendo do modo de gatilho).
- Todas as disciplinas obrigatórias nas trilhas de ênfase ativas do estudante estão pelo menos _Em andamento_ (ou _Concluídas_).
- O total de créditos — concluídos mais em andamento (ou apenas concluídos, dependendo do modo de gatilho) — atende aos créditos exigidos do programa.
- Todo requisito de formatura obrigatório marcado como **Bloqueia Solicitação de Formatura** está `Fulfilled` ou `Waived`.

Se algum bloqueador estiver pendente, a candidatura permanece em 0 mesmo quando a matemática de créditos/disciplinas seria verdadeira. Isto é por design — a escola marcou explicitamente esse requisito como um pré-requisito rígido.

## O que o estudante vê

Na página **Auditoria do Programa** (`/program-audit/<enrollment>`):

1. O banner de elegibilidade agora tem três estados:
   - **Elegível para Formatura** (verde) — aprovou tudo.
   - **Elegível Condicionalmente para Formatura** (azul) — matriculado nas disciplinas finais; ficará elegível quando essas notas saírem.
   - **Ainda Não Elegível para Formatura** (âmbar) — o estado inicial padrão.

2. Abaixo do banner, quando o estudante é um candidato, o **CTA de Solicitação de Formatura**:
   - Caminho **Elegível**: _"Você atende aos critérios de solicitação de formatura do programa. Envie uma solicitação para iniciar o processo de aprovação."_
   - Caminho **Elegível Condicionalmente**: _"Você pode enviar uma solicitação para iniciar o processo de formatura. Você deve ser aprovado nas disciplinas em que está atualmente para que ela seja aceita."_

3. Abaixo do CTA, uma tabela de **Pagamentos Pendentes** agrupa todas as Faturas de Venda não pagas desta matrícula por pagador. Isto inclui as faturas do próprio estudante _e_ faturas devidas por outros pagadores (igreja patrocinadora, doadores de bolsa, fundo denominacional). O estudante só pode pagar as suas próprias na página de Taxas; esta tabela mostra o panorama completo para todos.

   A maioria das escolas exige que todos os saldos estejam quitados antes da formatura. A etapa de revisão financeira (abaixo) é o portão, mas vê-la destacada aqui permite que o estudante cobre seus outros pagadores com antecedência.

## O que acontece quando a solicitação é protocolada

Clicar em **Solicitar Formatura** faz três coisas de forma atômica:

1. Cria o registro de **Solicitação de Formatura** vinculado a esta Matrícula no Programa.
2. Submete-o pelo fluxo de trabalho.
3. Gera uma **Fatura de Venda** para a taxa de Solicitação de Formatura do programa, endereçada ao pagador configurado na matrícula para o evento `Graduation Request`. (Vários pagadores dividem a taxa proporcionalmente, exatamente como as taxas de Matrícula em Disciplina.)

O estudante retorna para a página de auditoria; o cartão do CTA agora mostra **Aguardando Pagamento** com a porcentagem paga e um link para a fatura.

Se o programa estiver marcado como **Gratuito**, nenhuma fatura é gerada e a solicitação vai diretamente para `Academic Review`.

## O fluxo de trabalho

<LifecycleDiagram type="graduationRequest" />

| Estado                   | Status do documento | Quem pode editar    | O que significa                                                                                                                                                                                             |
| ------------------------ | ------------------- | ------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Rascunho**             | 0                   | Usuário Acadêmico   | Sendo preparado; normalmente transitório (o sistema cria e submete em uma etapa a partir da página de auditoria).                                                        |
| **Aguardando Pagamento** | 1                   | Usuário Acadêmico   | Fatura gerada; o estudante precisa pagar. Avança automaticamente quando o pagamento é integral.                                                                             |
| **Revisão Acadêmica**    | 1                   | Usuário Acadêmico   | Pagamento realizado (ou o programa é gratuito). A equipe acadêmica confirma notas lançadas, bloqueadores resolvidos e requisitos de formatura atendidos. |
| **Revisão Financeira**   | 1                   | Usuário de Contas   | A Tesouraria verifica que não há outros saldos em aberto na matrícula.                                                                                                                      |
| **Aprovado**             | 1                   | Gestor do Seminário | Carimbo final. O estudante está liberado para a formatura.                                                                                                                  |
| **Cancelado**            | 2                   | Gestor do Seminário | Retirado do processo.                                                                                                                                                                       |

### Aguardando Pagamento → Revisão Acadêmica (automático)

Quando um Lançamento de Pagamento é lançado na fatura da GR e `paid_percent ≥ 100`, o sistema avança o fluxo de trabalho automaticamente. Nenhuma etapa manual é necessária no caso comum.

Se a escola operar com políticas de pagamento parcial, um Usuário Acadêmico pode clicar manualmente em **Marcar como Pago** para avançar a solicitação antes que o pagamento integral seja lançado.

### Revisão Acadêmica → Revisão Financeira (manual)

O Usuário Acadêmico clica em **Enviar para Revisão Financeira** quando estiver satisfeito de que:

- As notas finais estão lançadas em todas as disciplinas da matrícula.
- Todo requisito de formatura obrigatório ativo está `Fulfilled` ou `Waived`.
- Não há decisões acadêmicas pendentes (notas incompletas, recursos pendentes).

O formulário de Solicitação de Formatura no Desk mostra duas tabelas instantâneas em HTML para agilizar esta revisão:

- **Requisitos de Formatura** — cada linha do SGR com status, marcação de obrigatório, marcação _Bloqueia Solicitação_, data de vencimento e um link para o documento vinculado (Carta de Recomendação, Projeto de Conclusão, etc.). Abra qualquer um com um clique.
- **Pagamentos Pendentes** — toda fatura não paga na matrícula, agrupada por pagador, com links no Desk para cada Fatura de Venda.

### Revisão Financeira → Aprovado (manual)

O Usuário de Contas clica em **Aprovar Financeiramente** quando estiver satisfeito de que:

- A taxa de formatura está paga integralmente.
- Não há outros saldos em aberto na matrícula (ou a escola os aceitou explicitamente).
- Reembolsos, conciliações de bolsas e quaisquer bloqueios estão resolvidos.

Esta é a aprovação final. A Solicitação de Formatura chega a `Approved`.

> **Atenção — `Approved` não carimba a PE como "graduado".** Essa é uma ação separada da secretaria (em uma versão futura, um fluxo de trabalho na própria PE). `Approved` significa que a solicitação está concluída; a secretaria então executa o processamento real da formatura (carimbo no histórico escolar, criação do registro de ex-aluno) fora deste módulo.

## Cancelamento

Duas formas:

1. **Manual** — a equipe acadêmica ou o Gerente do Seminário clica em Cancelar no formulário da GR. Quaisquer **totalmente não pagas** Faturas de Venda vinculadas também são canceladas. Faturas **parcialmente pagas** permanecem — a secretaria trata as decisões de reembolso explicitamente (use o fluxo padrão de Nota de Crédito do ERPNext, se necessário).

2. **Cascata a partir da retirada da PE** — quando a secretaria desativa uma Matrícula no Programa (`pgmenrol_active = 0`), toda GR ativa nessa PE é automaticamente cancelada. **A taxa é não reembolsável** nesse caminho — as faturas permanecem intactas. Esta é a política padrão porque a maioria das escolas trata a taxa de formatura como uma taxa de serviço não reembolsável, e um estudante que está se retirando não vai se formar de qualquer maneira.

## No dia a dia da equipe

### Onde procurar

- **Por estudante** — abra a Matrícula no Programa no Desk; a GR (se houver) fica visível na barra lateral Conexões.
- **Fila** — a visualização de lista de **Solicitação de Formatura**, filtrada para `workflow_state` em `("Academic Review", "Financial Review")`, é a fila diária da secretaria.
- **Coorte** — a mesma lista filtrada por `expected_graduation_date` dentro de um período letivo fornece a coorte de formandos para o planejamento da cerimônia.

### Revisando uma solicitação

1. Abra a Solicitação de Formatura pela visualização de lista.
2. Examine o instantâneo de **Requisitos de Formatura** — há algo que não esteja `Fulfilled` ou `Waived`?
3. Examine o instantâneo de **Pagamentos Pendentes** — o total não pago é preocupação da Tesouraria.
4. Clique em **Enviar para Revisão Financeira** (se Acadêmicos) ou **Aprovar Financeiramente** (se Contas), ou **Cancelar** se a solicitação precisar voltar para o estudante.

### Quando o estudante não vê o CTA

Se um estudante disser que "deveria poder se formar" mas não vê o botão, percorra as verificações de candidatura:

1. `Students Can Request Graduation` está marcado no Programa?
2. `Graduation Request Trigger` está definido?
3. Todas as disciplinas obrigatórias do programa + ênfase estão pelo menos Em andamento (modo Matriculado) ou Concluídas (modo Aprovado)?
4. Os totais de créditos somam corretamente?
5. Existe algum requisito de formatura **obrigatório** com `Blocks Graduation Request` marcado que ainda esteja `Not Started`, `In Progress` ou `Submitted`?

O quinto é o bloqueador silencioso mais comum. Abra a Matrícula no Programa e veja a tabela Student Graduation Requirements — qualquer coisa com a marcação **Bloqueia Solicitação** deve estar `Fulfilled` ou `Waived` primeiro.

> **Dica — bench helper.** Se você mudar o gatilho de um programa ou corrigir um caso difícil de depurar para um estudante, o sistema reavalia a candidatura automaticamente no próximo salvamento relacionado à PE. Para forçar um recálculo em todo um programa, execute:
>
> ```
> bench --site <site> execute seminary.seminary.graduation_candidate.recompute_for_program --kwargs "{'program': 'MDiv'}"
> ```

## Exemplos práticos

### Exemplo 1 — Formatura padrão do MDiv com taxa

1. **Configurar o programa.** Abra o programa _MDiv_. Marque **Estudantes Podem Solicitar Formatura**. Defina **Gatilho da Solicitação de Formatura** como _Aprovado nas disciplinas finais_ (o padrão conservador).
2. **Configurar o pagador da taxa.** Em cada Matrícula no Programa, abra a tabela _Payers Fee Category PE_ e adicione uma linha com `Event = Graduation Request`, a Categoria de Taxa apropriada, o pagador e a porcentagem.
3. O estudante conclui seu último período. Assim que as notas finais forem lançadas, o sistema muda `grad_candidate` para 1.
4. O estudante vê **Elegível para Formatura** + o botão **Solicitar Formatura** na página de auditoria. O estudante clica.
5. O sistema cria a GR + Fatura de Venda. O estudante paga. A GR avança automaticamente para **Revisão Acadêmica**.
6. A equipe acadêmica abre a GR, revisa as tabelas de instantâneo e clica em **Enviar para Revisão Financeira**.
7. A Tesouraria verifica se não há outros saldos não pagos e clica em **Aprovar Financeiramente**. A GR chega a **Aprovado**.

### Exemplo 2 — Programa gratuito, solicitar assim que estiver matriculado nas disciplinas finais

1. Configure o programa _Online Certificate_: marque **Programa Gratuito**, marque **Estudantes Podem Solicitar Formatura**, defina o gatilho para _Matriculado nas disciplinas finais_.
2. O estudante se matricula em suas últimas disciplinas do período.
3. A página de auditoria mostra o banner **Elegível Condicionalmente** + o CTA com o aviso "você deve ser aprovado".
4. O estudante protocola a solicitação. A GR pula **Aguardando Pagamento** e vai diretamente para **Revisão Acadêmica**.
5. A equipe acadêmica aguarda até as notas saírem. Se tudo foi aprovado, **Enviar para Revisão Financeira**. Se alguma disciplina foi reprovada, **Cancelar** — o estudante pode reprotocolar quando cumprir o requisito.

### Exemplo 3 — Pré-requisito rígido: a tese deve ser aprovada primeiro

1. Abra o item de **Biblioteca Senior Project** (Documento Vinculado, alvo _Projeto de Conclusão_). Marque **Obrigatório**, marque **Bloqueia Solicitação de Formatura**.
2. O estudante finaliza as disciplinas, mas a tese ainda está em revisão. Mesmo que a matemática de créditos esteja satisfeita, `grad_candidate` permanece em 0 — a página de auditoria mostra **Elegível Condicionalmente**, mas nenhum CTA aparece.
3. O orientador do estudante aprova a tese. O fluxo de trabalho do Projeto de Conclusão chega a `Completed`. A linha do SGR muda para `Fulfilled`. O avaliador de candidatura roda, vê que o bloqueador agora foi satisfeito e muda `grad_candidate` para 1.
4. O estudante atualiza a página de auditoria. O CTA agora está visível. O estudante protocola.

### Exemplo 4 — Igreja patrocinadora em atraso com pagamentos

1. O estudante conclui as disciplinas. Ele(a) protocola a Solicitação de Formatura e paga a taxa de formatura. A GR avança para Revisão Acadêmica.
2. A equipe acadêmica revisa os requisitos; tudo está em ordem. Envia para Revisão Financeira.
3. A Tesouraria abre a GR e examina o instantâneo de **Pagamentos Pendentes**. Vê que a igreja patrocinadora deve US$ 4.200 em três faturas mensais.
4. A Tesouraria retém a Aprovação e contata a igreja. Uma vez pago, **Aprovar Financeiramente**. (Alternativamente, se a escola tiver um acordo escrito com a igreja, a Tesouraria pode aprovar e cobrar o saldo separadamente — isso é uma decisão de política institucional que o sistema não impõe.)

## Referência rápida

| Se você quer...                    | Faça isto                                                                                                                                                                           |
| ---------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Ativar Solicitações de Formatura em um programa                                    | Program → marque _Estudantes Podem Solicitar Formatura_ + escolha um gatilho                                                                                                        |
| Desativar Solicitações de Formatura para um programa específico                    | Desmarque _Estudantes Podem Solicitar Formatura_ nesse Programa                                                                                                                     |
| Tornar um requisito de formatura um pré-requisito rígido até mesmo para protocolar | Library → marque _Bloqueia Solicitação de Formatura_ (visível apenas se Obrigatório)                                                                             |
| Forçar o recálculo de candidatura para um estudante                                | Salve a Matrícula no Programa (qualquer campo) — o recálculo dispara em `on_update_after_submit`                                                                 |
| Forçar um recálculo para um programa inteiro                                       | `bench execute seminary.seminary.graduation_candidate.recompute_for_program --kwargs "{'program': 'XYZ'}"`                                                                          |
| Ver a fila de revisão da Secretaria Acadêmica                                      | Lista de Solicitações de Formatura, filtro `workflow_state in ("Academic Review", "Financial Review")`                                                                              |
| Cancelar uma solicitação sem reembolso                                             | Clique em Cancelar na GR (faturas parcialmente pagas permanecem)                                                                                                 |
| Confirmar conclusão da formatura                                                   | Chega ao estado de fluxo de trabalho `Approved` — o processamento real da formatura (histórico escolar, registro de ex-aluno) é uma etapa separada da secretaria |

## Relacionados

- [Requisitos de Formatura](graduation-requirements.md) — as camadas de política + Biblioteca + SGR das quais o avaliador de candidatura lê.
- [Matrícula](enrollment.md) — a Matrícula no Programa é onde vivem `grad_candidate`, o instantâneo de política e a configuração do pagador da taxa.
- [Retirada](withdrawal.md) — retirar uma PE cancela automaticamente qualquer Solicitação de Formatura ativa.
- [Funções de Usuário](../administration/user-roles.md) — Usuário Acadêmico vs Usuário de Contas vs Gerente do Seminário (etapas de revisão).
