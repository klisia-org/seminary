# Estratégia de precificação

O SeminaryERP cobra dos estudantes criando faturas a partir de **Categorias de Taxa**, cada uma vinculada a um **Item** do ERPNext com um preço em uma **Tabela de Preços**. O quão granulares você torna esses Itens é uma decisão estratégica que afeta os relatórios, as projeções e quanto trabalho será necessário para alterar os preços depois.

## Precificação em pacote vs. granular

Ambas as abordagens a seguir produzem o mesmo total da fatura. Elas não são equivalentes para o seminário.

| Abordagem A — _em pacote_        | Abordagem B — _granular_                       |
| -------------------------------- | ---------------------------------------------- |
| Curso de 1h: 250 | Hora-crédito: 200              |
| Curso de 2h: 450 | Taxa de matrícula no curso: 50 |

**A Abordagem A** é mais rápida de configurar. Os preços ficam embutidos em cada Item no nível de curso.

**A Abordagem B** separa _o que varia com a carga de créditos_ (custo de ensino por crédito) do _que é fixo por matrícula_ (custo administrativo). Isso permite que você:

- Projete a receita em cenários de matrícula (por exemplo, "e se a carga média cair de 12 para 9 créditos?")
- Aumente os preços por crédito sem alterar cada Item de curso
- Aplique bolsas ou descontos apenas à parcela por crédito
- Emitir relatórios claros separando receita administrativa e acadêmica

Para qualquer situação além de um seminário muito pequeno, **prefira a Abordagem B**. O esforço de modelagem inicial compensa na primeira vez que você precisar ajustar a precificação ou justificar um orçamento.

## Diretrizes práticas

- **Um Item por direcionador de custos**, não por curso. Horas-crédito, matrícula, taxa de tecnologia, acesso à biblioteca, moradia — cada um é seu próprio Item.
- **Mantenha pequeno o número de Tabelas de Preços.** Cada lista adicional multiplica o esforço de manutenção. Só adicione uma lista quando toda a estrutura de preços realmente diferir (por exemplo, estudantes internacionais pagam valores diferentes em toda a estrutura), não para descontos pontuais — use bolsas ou Regras de Preço para esses casos.
- **Mapeie cada evento passível de cobrança a uma Categoria de Taxa.** É isso que torna o faturamento automático: quando o estudante se matricula, o período letivo abre ou o gatilho por crédito é acionado, o SeminaryERP cria as linhas de fatura corretas a partir da Categoria de Taxa.
- **Reavalie antes do seu primeiro período letivo, não depois.** Mudar o modelo de precificação quando já existem faturas é doloroso; acertá-lo antes da entrada em produção é fácil.

## Relacionado

- [Configuração inicial](initial-setup.md) — a sequência completa de configuração
- [Item do ERPNext](https://docs.frappe.io/erpnext/item) · [Tabela de Preços](https://docs.frappe.io/erpnext/price-lists) · [Preço de Item](https://docs.frappe.io/erpnext/item-price)
