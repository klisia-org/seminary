# Cancelamento de Matrícula

O módulo de Cancelamento de Matrícula lida com cancelamentos de disciplina e trancamentos institucionais, com regras configuráveis por período letivo.

## Visão geral

Os estudantes podem solicitar Cancelamento de Matrícula pelo Portal do LMS.
As regras que regem prazos, penalidades e elegibilidade a reembolso são configuradas por usuários acadêmicos na visualização do Desk.

## Conceitos-chave

- **Janela sem penalidade** — período configurável após o início do período letivo em que o trancamento não acarreta penalidade acadêmica
- **Motivo de Trancamento** — um Doctype separado que permite às instituições acompanhar e relatar por que os estudantes trancam
- **Tratamento de Reembolso/Bolsa** — implicações financeiras configuradas junto com as regras de trancamento

## Pedido de Cancelamento de Matrícula

Iniciada pelo estudante (se permitido nas "Configurações do Seminário") ou por administradores/usuários acadêmicos

### Solicitação do Estudante

Os estudantes podem solicitar trancamento de qualquer disciplina em que estejam atualmente matriculados e à qual tenham acesso no Portal.
Navegue até uma Disciplina → Meu Status: ao final da página, os estudantes podem solicitar o trancamento daquela disciplina. O sistema exibirá, no topo dessa página, o status da solicitação de trancamento da disciplina.

Os estudantes precisarão informar um [motivo preconfigurado](#withdrawal-reasons) e qualquer documentação comprobatória exigida por esse motivo específico. O sistema preencherá automaticamente os campos obrigatórios.

Os estudantes também podem criar solicitações de trancamento para outras disciplinas, além desta, selecionando a opção apropriada em "Escopo do Trancamento". Cada curso acompanhará sua própria solicitação de retirada, mas os administradores de seminário verão as solicitações relacionadas.

![Tela do Portal de Solicitações de Trancamento](/modules/withdrawal/img/withdrawal_request_portal.png)

Depois que o estudante enviar a solicitação, o status ficará visível no topo da página Meu Status daquela disciplina. Os status dependem do Fluxo de Trabalho configurado.

![Tela de Status no Portal das Solicitações de Trancamento](/modules/withdrawal/img/withdrawal_request_portal_status.png)

### Solicitação da Secretaria Acadêmica

Registars or other assigned users can create and track progression of the Withdrawal Request within Desk, advancing it through the workflow with the Action menu (top right).
O SeminaryERP vem com um Fluxo de Trabalho predefinido, que pode ser personalizado pelo(a) administrador(a) do seminário. Isso é particularmente útil para incluir notificações por e-mail, entre outras possibilidades.

![Tela no Desk de Solicitações de Trancamento](/modules/withdrawal/img/withdrawal_request_desk.png)

## Motivos de Trancamento

É uma boa prática padronizar e avaliar periodicamente os motivos que levam os estudantes a desistirem de disciplinas. Muitas agências de credenciamento exigem isso, e o SeminaryERP facilita o atendimento a esse requisito.
Ao criar um motivo de trancamento, os administradores definirão um nome, uma descrição, se será obrigatório anexar documentação comprobatória (ela está sempre disponível, apenas não obrigatória) e, em caso afirmativo, qual rótulo será exibido aos estudantes. Isso facilita para que os estudantes saibam exatamente o que precisam enviar. Dois editores de texto rico informativos fornecem documentação inicial para estudantes e equipe.

![Tela de Motivos de Trancamento](/modules/withdrawal/img/withdrawal-reasons.png)

## Regras de Trancamento

1. Dê à regra um nome claro, fácil de entender por si só.
2. A caixa de seleção "Excluir do cálculo da nota" indica que isso não contará para o GPA final},{
3. Símbolo de Avaliação: como você quer que isso apareça no histórico escolar (pode ser uma palavra, não necessariamente um símbolo)
4. Permitir crédito parcial: as atividades avaliativas enviadas pelo estudante podem ser usadas para crédito parcial (recurso em desenvolvimento)
5. Se a configuração principal em "Configurações do Seminário" permitir, uma [**Data por Período Letivo**](#term-widrawal-rules) poderá ser calculada automaticamente para cada período letivo. Quando marcada, campos adicionais ficarão disponíveis para calcular a data "Válida até" para cada período letivo. Observe que, como a regra é aplicada por período letivo (mesmo que impacte cursos agendados), os limites de data são sempre relativos ao período letivo.
6. Reembolso: se a caixa de seleção estiver marcada, uma tabela filha ficará disponível. Isso definirá quanto será reembolsado e para quem, se a regra se aplicar. Ou seja, o sistema identificará automaticamente a Fatura de Venda daquela disciplina e criará uma Nota de Crédito vinculada a ela, seguindo o mesmo procedimento fiscal da Fatura de Venda. As regras contemplam três tipos de pagadores: Estudante (isto é, o Cliente do ERPNext associado ao Estudante), Bolsas (o Cliente do ERPNext associado a Bolsas nas Configurações do Seminário) e Outros Pagadores (pois o SeminaryERP também oferece a opção de igrejas/denominações pagarem parte da mensalidade).

![Tela de Regras de Trancamento](/modules/withdrawal/img/withdrawal-rules.png)

## Regras de Trancamento por Período Letivo

Se houver necessidade de ajuste manual das datas em que uma regra se aplica, isso pode ser feito no Desk, em Regras de Trancamento por Período Letivo.

![Tela de Regras de Trancamento por Período Letivo](/modules/withdrawal/img/withdrawal-term-rules.png)

## Fluxo de Trabalho da Solicitação de Trancamento

A maioria dos seminários não precisará editar o fluxo de trabalho pré-configurado. No entanto, isso é possível e instituições maiores podem se beneficiar especialmente de personalizações. Como isso é um recurso do ERPNext, a [documentação](https://docs.frappe.io/erpnext/workflows) deles pode ser útil.

<LifecycleDiagram type="withdrawal" />

The workflow has five states: **Draft → Academic Review → Financial Review → Completed**, plus **Rejected**. Academic Review is the registrar's queue; Financial Review belongs to the Accounts User. The _action_ you take carries the meaning — approving academically routes the request onward, and the side effects (withdrawing the course enrollment, issuing refunds, finalizing a program separation) are applied as those actions are taken.

The Academic Review step adapts to whether money is involved. When a refund could be due (a withdrawal rule with refunds applies and the program is not free), the registrar's approval is **Approve Academically**, which sends the request to Financial Review. When no refund is due, that same step becomes **Approve Academically & Conclude**, which settles the request in one click without a Financial Review stop.

### Vias rápidas para programas em andamento e gratuitos

Duas sinalizações no Programa subjacente alteram os botões mostrados em uma solicitação de cancelamento de matrícula para que os usuários não tenham que clicar através de estados de revisão que não têm nada para avaliar:

- **É Contínuo** — Uma propriedade do **Nível do Programa**, espelhada em cada Programa nesse nível. Programas Contínuos não têm nenhum conceito de graduação, GPA ou transcrição, portanto não há nada para revisar academicamente em uma retirada.
- **Programa gratuito** — uma caixa de verificação por programa. Quando definido, o registro não gera faturas de vendas, então não há nada para revisar financeiramente em uma retirada.

Os botões disponíveis em uma solicitação de cancelamento em rascunho se adaptam automaticamente:

| Sinalizadores do programa | Botão mostrado no rascunho                                                           | Leva à                                                                                                                                                                                             |
| ------------------------- | ------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Nenhum                    | **Submit**                                                                           | Academic Review (standard Academic → Financial → Completed chain)                                                                                                               |
| Apenas grátis             | **Submit**                                                                           | Academic Review; with no refund due, the registrar's approval appears as _Approve Academically & Conclude_ and settles it in one step (no Financial Review) |
| Ongoing only, refund due  | **Submit & Approve Academically** (Registrar) | Financial Review (academic auto-approved; paid courses still settle)                                                                                                            |
| Ongoing only, no refund   | **Submit & Conclude** (Registrar)             | Completed                                                                                                                                                                                          |
| Contínuo **e** grátis     | **Submit & Conclude** (Student or Registrar)  | Concluído (sem revisão alguma)                                                                                                                                                  |

On the ongoing-program fast-paths no grade treatment is applied — the system simply marks the underlying Course Enrollment as withdrawn.

If a student initiates a withdrawal for an ongoing-but-paid program, they still see the standard **Submit** button; the registrar later walks the request through Academic Review, where the academic processing for ongoing programs is a no-op by design.