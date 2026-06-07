# Matrícula

O recurso de matrícula gerencia como os estudantes se matriculam em disciplinas dentro de um período letivo.

## Visão geral

Os estudantes podem se matricular pelo portal do LMS durante os períodos de matrícula configurados, ou os administradores podem matricular estudantes diretamente pelo Frappe Desk.

## Conceitos-chave

- **Período de matrícula** — o intervalo de datas durante o qual a automatrícula fica aberta
- **Matrícula em disciplina** — o registro que vincula um estudante a uma disciplina em um período letivo específico
- **Capacidade de matrícula** — limite opcional de estudantes por turma da disciplina

## Ciclo de Matrícula em Curso

Uma Matrícula de Curso Individual se move através de um fluxo de trabalho de quatro estados:

<LifecycleDiagram type="enrollment" />

- **Rascunho** — criado mas ainda não apresentado; nada aconteceu além de salvar a linha
- **Aguardando pagamento** — enviado, Faturas de Vendas geradas, mas o aluno ainda não foi adicionado à lista de participantes do curso (sem acesso ao LMS)
- **Enviado** — O aluno está totalmente matriculado: na lista de cursos do curso, na lista de cursos do Programa, elegível para receber as notas
- **Cancelamento de Matrícula** - defina automaticamente quando uma Solicitação de Cancelamento de Matrícula do Curso chega à Aprovação Acadêmica; visível na vista da lista CI como uma pílula de estado listada

Qual caminho o CEI pega a partir do rascunho depende do **Programa** ao qual o curso pertence:

| Sinalizadores do programa                        | Rascunho enviado para | Porquê                                            |
| ------------------------------------------------ | --------------------- | ------------------------------------------------- |
| Programa gratuito (`is_free`) | Enviado               | Sem faturamento, sem portão de pagamento          |
| Pago + Exigir pagamento antes da matrícula       | Aguardando Pagamento  | Mantenha o lugar até que o aluno pague            |
| Pago + pagamento não necessário                  | Enviado               | Fatura para o aluno, mas matriculá-lo mesmo assim |

Para programas configurados como _Exigir pagamento antes da inscrição_, o CEI avança automaticamente de **Aguardando Pagamento** para **Enviado** quando os pagamentos cumulativos do aluno ultrapassem o limite de _Pagamento Mínimo %_ (padrão 100%) do programa. Para cenários de pagador misto (aluno + bolsa + terceira pessoa), o limite é calculado contra o valor _total_ faturado em todas as faturas de vendas vinculadas.

### Substituição manual

Se um pagamento chegar fora da plataforma (dinheiro na secretaria, transferência bancária reconciliada mais tarde, exceção especial), um usuário acadêmico pode usar o botão de fluxo de trabalho **Marque como Pago** em um CEI aguardando pagamento para avançar para Submetido sem gravar um Entrada de Pagamento primeiro.

### Reembolsos e notas de crédito

Se uma nota de crédito é criada após o CEI ser enviado e a porcentagem paga recalculada cair abaixo do limite, o CEI **permanece em Enviado** — o aluno não será silenciosamente des-inscrito no meio do período letivo. Em vez disso, um ToDo é criado e um e-mail é enviado a todos os usuários acadêmicos, então o agente de registo pode decidir se deve criar uma solicitação de cancelamento de matrícula do curso, seguimento e cobrança, ou apenas ter ciência.

### Seção Status de pagamento no CEI

O formulário CEI expõe uma seção _Status de pagamento_ mostrando o estado ao vivo:

- **Total faturado** — soma de todas as faturas de vendas vinculadas
- **Total pago** — soma de `(total – a pagar)` entre essas faturas
- **Pago %** — derivado; mostrado na lista de exibição
- **Limiar Alcançado em** — data e hora estampada pelo sistema quando o avanço automático for disparado (vazio para sobrescrever manuais e programas gratuitos)

## Programas gratuitos e contínuos

Duas marcas no programa moldam a experiência de matrícula de ofertas não tradicionais:

- **É Contínuo** (espelhado do Nível do Programa) — programas sem graduação: educação contínua, auditoria gratuita e cursos devocionais. CEIs em curso em programas ignorando o cálculo GPA, nunca ativando as verificações de auditoria de graduação e tenha cancelamento de matrícula sem taxa (nenhuma Revisão Acadêmica).
- **Programa Livre** (definição por programa) — ignora totalmente a geração de faturas de vendas e ignora Revisão Financeira após cancelamento de matrícula. Muitas vezes combinado com _É Contínuo_, mas os dois são independentes: um seminário pago modular deixa _Programa gratuito_ desmarcado; um programa de livre graduação deixa _É Contínuo_ desmarcado e a lógica de graduação ainda funciona.

Veja [Cancelamento de Matrícula → via-rápida para programas em andamento e gratuitos](withdrawal.md#fast-paths-for-ongoing-and-free-programs) sobre como as mesmas bandeiras moldam o fluxo de retirada.

## Duração máxima da matrícula

Programas que vinculam quanto tempo um aluno pode ficar matriculado (por exemplo, "MDiv deve terminar em 7 anos") defina **Máximo de Anos para Graduar** no Programa (suporta anos fracionados). Na submissão da matrícula, a _Data Máxima de Graduação_ do aluno é definida automaticamente como _data de matrícula + Máximo de Anos para Graduar_. A secretaria pode editar a _Data de Graduação Máxima_ depois para conceder extensões.

O relatório **Risco de Tempo-para-Graduar** (em Relatórios → Seminário) lista cada Matrícula ativa cujo Programa tenha uma duração máxima de inscrição, calcula os créditos remanescentes e o tempo restante e ordena os alunos pelo número de créditos por ano que precisam para cumprir o seu limite. Os alunos com maior risco aparecem no topo.
