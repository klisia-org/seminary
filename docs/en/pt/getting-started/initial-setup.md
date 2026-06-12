# Configuração Inicial

Depois de [instalação](installation.md), prossiga pelas seções abaixo **em ordem**. Cada uma depende da anterior. Tudo é feito no Frappe Desk, a menos que seja informado.

:::tip Fundamentos do ERPNext
O SeminaryERP é construído sobre o ERPNext. Vários itens abaixo (Itens, Lista de Preços, Grupos de Clientes e Preços dos Produtos, Termos de Pagamento) são \*registros padrões ERPNext \* — esta página abrange o que um seminário especificamente precisa, com links para o manual ERPNext para a referência completa.
:::

## 1. Escala de Notas Padrão

Cria a escala de notas padrão usada em todo o seminário. Você pode criar escalas adicionais mais tarde e atribuí-las por curso. Ver [Avaliação](../modules/grading.md) sobre como as escalas interagem com avaliações e registro de notas.

## 2. Configurações do Seminário

Navegue até **Configurações do Seminário** no Frappe Desk para configurar: Este é o painel de controle em todo o seminário:

- **Detalhes e logotipo da instituição**
- **Escala de Notas Padrão**
- **Bolsas de Estudo** — Centro de Custo e Cliente Padrão
- **Ouvintes** — se é para permitir alunos cursarem matérias sem crédito e como eles são cobrados (taxa fixa ou por hora de crédito)
- **Cancelamento de Matrícula de Curso** — Política de base (regras detalhadas são configuradas no [Módulo de cancelamento de matrícula](../modules/withdrawal.md))
- \*\*Ciclo de Cursos Agendados \*\*:
  - **Auto-avançar estados de Cursos Agendados** (padrão ligado) - quando selecionado, o agendador diário avança os Curosos Agendados automaticamente com base nas datas abaixo (Rascunho → Abrir para inscrição → Matrícula Fechada) e envia e-mails aos intrutores que não enviaram as notas dentro do prazo. Desmarque se o seu seminário prefere o controle totalmente manual.
  - **Regras da Janela de Inscrição** — três pares de (âncora, deslocamento em dias) que definem quando cada Curso Agendado abre para matrícula, fecha a matrícula e espera as notas finais. Âncoras: `term_start`, `term_end`, `classes_start` (= data de início de cada Curso Agendado), `classes_end` (= data final de término de cada Curso Agendado). Número negativo = antes da âncora; positivo = depois. Uma âncora em branco ignora uma janela — os Cursos Agendados afetados precisam de definições explícitas no seu próprio formulário (seção do ciclo de vida) ou aterrissagem diretamente em Aberto para Inscrição sem prazo de matrícula. Veja [Seção 12](#_12-course-schedule-lifecycle).
- **RH/Folha de Pagamento** - Você pode estender a funcionalidade de SeminaryERP com a nossa integração com Frappe HRMS para processar a folha de pagamento. Para fazer isso, clique em [Habilite folha de pagamento HRMS](../modules/instructor-payment.md)
- **Portal do aluno** — ative cada facilidade para os de alunos:
  - Solicitar matrículas no curso
  - Solicitar cancelamento de matrícula de curso
  - Pagar online através de um gateway de pagamento (e qual gateway é o padrão — por exemplo, Stripe)
  - Editar instruções do calendário do curso
  - Fluxo de aplicação online para novos estudantes

## 3. Itens do ERP

No ERPNext, tudo o que pode ser cobrado é um **item** (hora de crédito, taxa de cadastro, taxa de biblioteca, alojamento, etc.). SeminaryERP vem com um conjunto inicial — revise estes itens e decida quais se encaixam no seu seminário antes de criar mais.

:::warning UOM (unidade de medida) não deve ser "número inteiro"
Ao criar um novo Item, certifique-se de que seu [UOM](https://docs.frappe.io/erpnext/uom) tem **"Deve ser Número inteiro"** desmarcado. Horas de crédito e muitas taxas são fracionárias.
:::

Para qualquer outra coisa sobre itens — itens sem estoque, grupos de itens, impostos — veja a [documentação do item no ERPNext](https://docs.frappe.io/erpnext/item).

## 4. Listas de Preços

Uma [Lista de Preços](https://docs.frappe.io/erpnext/price-lists) é simplesmente um conjunto de preços nomeado. Você pode ter quantos você quiser (por exemplo, _Alunos Nacionais_, _Alunos Estrangeiros_), mas **cada lista adicional exigirá manutenção** — adicione uma apenas quando os preços diferem verdadeiramente.

## 5. Grupos de Clientes

SeminárioERP cria automaticamente um grupo de cliente **Aluno**. Se você precisar de listas de preços diferentes aplicadas automaticamente (por exemplo, nacionais vs. estrangeiros), crie [Grupos de clientes adicionais](https://docs.frappe.io/erpnext/customer-group) e defina a lista de preços padrão de cada um. Os alunos associados ao grupo serão cobrados a partir dessa lista.

## 6. Preços dos Itens

Aqui é onde você insere o preço de cada item em cada Lista de Preços. Veja [Preço do Item](https://docs.frappe.io/erpnext/item-price) para mais explicações.

Antes de inserir os preços, leia [Estratégia de Preços](pricing-strategy.md) — a granularidade de seus preços vai determinar quanto a automação e os relatórios de SeminaryERP poderão fazer por você mais tarde.

## 7. Termos de Pagamento

Um [Modelo de Termos de Pagamento](https://docs.frappe.io/erpnext/payment-terms-template) compreende um ou mais [Termos de Pagamento](https://docs.frappe.io/erpnext/payment-terms) (por exemplo, _50% na inscrição, 50% no meio do período letivo_).
Portanto, os modelos são uma forma simples e prática de configurar **quando** cada **porção (%)** de uma fatura deve ser paga.

Os termos de pagamento definirão a data limite de uma fatura com base na data de sua criação, bem como a porcentagem da fatura a ser paga.
Os modelos estão anexados às taxas e às faturas, então crie os modelos que você realmente precisa antes de configurar categorias de taxas.

## 8. Categoria de Taxa

Uma **categoria de taxas** é a unidade de automação de faturamento do SeminaryERP. Cada categoria une:

- Um **item de ERP** (o que é faturado)
- Um **Modelo de Termos de Pagamento** (como é cobrado)
- Um **Tipo de Categoria** (Grupo de Itens) para relatórios
- Um **Evento de Cobrança** (quando a fatura é criada)
- Marcas para **É Crédito Acadêmico** e **É Ouvinte** --Apenas categorias de taxas com esses indicadores serão calculadas por hora de crédito (no caso de Ouvintes, ver também configurações de seminário)

O seminário define o **Evento de Cobrança** e eles são invocados de forma programática. Os seguintes gatilhos estão disponíveis para a criação de categorias de taxas:

- **Inscrição no programa** - dispara uma vez na submissão do programa.
- **Inscrição no curso** — dispara uma vez por curso, na submissão da matrícula do curso.
- **Novo Período Acadêmico** — o agendador diário dispara na data de início do Período Acadêmico (ou no dia seguinte o trabalho é executado, se cron não funcionar).
- **Novo Ano Acadêmico** — O agendador diário dispara na data de início do Ano Acadêmico (ou no dia seguinte, se cron não funcionar).
- **Mensal** — O agendador diário dispara no primeiro dia de cada mês para cada programa ativo. Uma data `A Partir de` na Categoria de Taxa restringe o faturamento para Inscritos no Programa cuja data de inscrição seja estritamente posterior a essa data (deixe em branco para faturar todos atualmente inscritos).

Os três gatilhos impulsionados pelo tempo (NAA / NPA / Mensal) são idempotentes: o agendador registra que um período foi faturado (por meio de `invoiced_nat_on`, `faturado_nay_on`, `última_mensal_faturada_on`) e não vai faturar duas vezes. Se uma execução cron for perdida, a próxima execução diária pega qualquer período pendente. O faturamento pode ser pausado globalmente em **Configurações do Seminário → Ativar a Cobrança Automatizada**. Para uma recuperação única, use o **Registrar Hub → Regenerar faturas atuais**.

Configure uma Categoria de Taxa por evento cobrável para que o SeminaryERP possa postar faturas automaticamente quando o evento acontecer. É por isso que os itens, as listas de preços e os termos de pagamento devem existir primeiro.

Depois que as Categorias de Taxas são criadas, você as usará durante a criação de Programas e Cursos.

## 9. Ano Letivo

Crie seu primeiro [**Ano acadêmico**](../modules/academic-calendar.md#academic-year). É um recipiente para Períodos Letivos — os períodos não podem ultrapassar os limites do seu ano. Algumas taxas e tarefas administrativas são agendadas uma vez por ano.

## 10. Período Letivo

Crie seu primeiro período acadêmico

1. Defina as datas de início e término
2. Configurar janelas de matrícula e prazos de cancelamento de matrícula - ver [Calendário Acadêmico](../modules/academic-calendar.md#academic-term) e [Cancelamento de Matrícula](../modules/withdrawal.md) sobre como estas datas determinam regras posteriores.

## 11) Programa

Um [**Programa**](../modules/program.md) é a estrutura de currículos em que os alunos se inscrevem (por exemplo, _M.Div._, _Certificado em Estudos Bíblicos_). Ele define créditos/termos necessários, cursos, áreas de concentração, grupos e taxas ao nível do programa. Crie pelo menos um programa antes de abrir as inscrições.
Modelagem detalhada do programa (grupos, áreas de concentração, requisitos de crédito) é abrangida por [Matrículas](../modules/enrollment.md). Durante a matrícula do programa, também será estabelecido **quem** paga cada categoria de taxas e qual porcentagem (Pagador por Categoria da Taxa).

Todas as categorias de taxas para qualquer curso desse programa **devem** primeiro ser vinculado no nível do Programa.

### Nível do Programa

Todos os links do programa para um **Nível do Programa** (ex: _Bacharel_, _Mestrado_, _Doutorado_, _Certificado_, _Programa não formal_). Os níveis são **enviáveis**: uma vez enviado, um nível é bloqueado e visível no seletor de nível do programa. Para alterar os campos escolhidos em um nível após o fato, é necessário alterá-lo (criar uma nova revisão) e repor Programas conforme necessário — isso oferece uma trilha de auditoria limpa e impede mudanças de comportamento silencioso em programas que já estão em curso.

O nível carrega uma marca de modelagem de comportamento:

- **É Contínuo** — marque esta opção somente quando o programa não tiver um fim definitivo (educação contínua, auditoria gratuita e cursos devocionais). Programas Contínuos não tem GPA, graduação, transição para ex-alunos e a etapa de Revisão Acadêmica no cancelamento de matrícula. A marca é espelhada do Nível do Programa para cada programa daquele nível (somente leitura no formulário do programa).

Quando _É Contínuo_ for definido, a seção de GPA e honras, _Tipo de matrícula_, _Termos para conclusão_, e campos _Créditos para conclusão_ desaparecem do formulário do programa — eles não têm significado para programas contínuos.

### Programa Gratuito

Um checkbox separado por Programa **Programa Gratuito** dissocia o lado financeiro do lado acadêmico:

- Quando ativado, o programa **não** gera notas fiscais de venda na matrícula (de cursos, Novo Período Acadêmico/Ano Novo Acadêmico/Faturamento Mensal), e as solicitações de cancelamento de matrícula ignoram a etapa de Revisão Financeira.
- A aba _Financeira_ e a tabela de _Taxas de Programa_ ocultam-se no formulário do Programa quando _Programa Gratuito_ for definido.

As duas marcas são ortogonais: um programa conínuo e pago, (por exemplo, cursos modulares) deixam o _Programa Gratuito_ desmarcado, portanto as taxas por curso e os fluxos de reembolso ainda funcionam; um programa gratuito mas com diploma deixa _É Contínuo_ desmarcado, portanto a lógica de graduação ainda é executada. Veja [Cancelamento de Matrícula → via rápida para programas contínuos e gratuitos](../modules/withdrawal.md#fast-paths-for-ongoing-and-free-programs) sobre como as duas sinalizações combinadas moldam os botões de cancelamento de matrícula.

### Filtros de Pagamento (programas pagos)

Para programas pagos, mais dois campos controlam se uma Matrícula do Curso requer pagamento antes de o aluno ser totalmente matriculado:

- **Exigir pagamento antes da matrícula** (padrão, oculto quando o _Programa Gratuito_ é marcado) — quando definido, uma matrícula no Curso começa no estado _Aguardando pagamento_. O aluno é faturado mas não é adicionado à lista de participantes até que o pagamento seja efetuado.
- **Pagamento Mínimo %** (padrão 100) — o pagamento acumulado, em percentagem do total faturado do curso, para que o sistema avance a inscrição para _Enviada_. Defina 50 se as matrículas pagas pela metade são ativas; deixe às 100 para exigir o pagamento completo.

Ambos os campos estão ocultos para programas contínuos (sem conceito de filtros). Veja [Inscrição → Vida da matrícula do curso](../modules/enrollment.md#course-enrollment-lifecycle) para a máquina de estado completa.

### Duração máxima no programa (tempo limite)

**Máximo de Anos para Graduar** (Float, valores fracionários suportados) é o tempo máximo que um aluno pode ficar matriculado antes de se formar. 0 significa sem limite (o padrão). Quando definido, cada nova inscrição de programa para este Programa obtém uma **Data de graduação máxima** automaticamente calculada como \`Data de Matrícula + Máximo de Anos para Graduar; a secretaria de alunos pode editar essa data para conceder extensões.

O relatório do **Risco de Tempo-para-Graduação** (Relatórios → Seminário) lista matrículas ativas cujo Programa tem um Ano Máximo diferente de zero, ordena-os pelo número de créditos/ano que precisam para terminar a tempo, e sinaliza estudantes em atraso no topo.

## 12. Ciclo de Curso Agendado

Cada **Curso Agendado** se move através de um fluxo de trabalho de seis estados que os agendadores diários avançam automaticamente (quando [Seção 2](#_2-seminary-settings) "Avanço automático" está ligado) ou que a secretaria de alunos muda manualmente:

<LifecycleDiagram type="courseSchedule" />

- **Rascunho** — criado, ainda não visível para os alunos. O agendador promove a Abertura para Matrícula quando chega a data de matrícula definida.
- **Aberto para matrícula** — os alunos podem solicitar inscrição no portal.
- **Matrícula fechada** — a janela de registro passou, período letivo em curso, com aulas.
- **Avaliação** — o sistema entra nesse estado automaticamente na primeira vez que uma nota não nula é salva em qualquer aluno ativo (seja por meio de Quiz/Tarefa/Exame/Discussão ou diretamente no Quadro de Notas). Nenhuma ação da secretaria de alunos é necessária.
- **Fechado** — estado final, definido quando o professor clica em **Enviar notas** no quadro de notas (ou, no Desk, no formulário Curso Agendado). As notas finais são escritas no registro de notas nesse momento.
- **Cancelado** — terminal. Alcançável somente antes de começar a dar notas (veja _Cancelamento de um Curso_ abaixo).

### Substituições de data por Curso Agendado

A seção **Ciclo de Curso Agendado** (na aba Roster da turma) mostra as datas-chave de matrícula aberta/fechar/ notas definidas pelas configurações de seminário, mais três campos de data \*\* \*\* opcionais. Preencher uma substituição substitui a regra para esse agendamento - útil para cursos adicionados, intensivos, ou exceções únicas.

### Motivos de cancelamento de curso

Os cancelamentos requerem um **motivo** escolhido de uma lista configurável. SeminaryERP já vem com cinco motivos:

- Matrículas Insuficientes
- Instrutor Indisponível
- Mudança no Currículo
- Decisão Administrativa
- Força Maior

Para adicionar ou renomear motivos, abra o **Motivo de Cancelamento de Curso** no Desk (barra de pesquisa). Marque motivos antigos como inativos ao invés de apagá-los para que os cancelamentos históricos mantenham um rótulo válido.

### Cancelamento de um Curso (fluxo de trabalho da secretaria)

Um curso só pode ser cancelado enquanto estiver em **Aberto para matrícula** ou **Fechado para matrícula**. Quando qualquer nota for inserida, o sistema move o curso para **Avaliação** e o cancelamento não é mais oferecido — nesse momento, o cancelamento correria o risco de perder dados de alunos.

Etapas:

1. Abra o formulário Curso Agendado (Desk).
2. Grupo de ação **Status** → **Cancelar curso**.
3. Escolha um motivo de cancelamento na caixa de diálogo e confirme.

O sistema irá:

- Marcar todos os alunos com Matrícula Individual no Curso com `Curso Cancelado`, o motivo escolhido e um carimbo de data (diferente de um cancelamento iniciado pelo aluno).
- Remova as linhas das Matrículas nos Cursos do Programa afetadas para que os cursos cancelados não apareçam em registros de notas ou auditorias de progresso. As linhas que vieram das notas transferidas por um seminário parceiro são preservadas.
- Envie um Aviso do Seminário para todos os alunos matriculados explicando o cancelamento.
- Libere para os alunos se matricularem em outra seção ou curso imediatamente — verificações de matrícula duplicada e listas de "cursos disponíveis" ignoram CEIs de curso cancelados.

Cancelamento não pode ser desfeito nesta versão. A caixa de diálogo avisa sobre isso, então verifique antes de confirmar.

:::tip Emergência: cancelar após avaliação iniciada
Se um curso deve ser aposentado após o início da das avaliações (por exemplo, o instrutor morre no meio do período), o procedimento é: retirar cada aluno matriculado através do fluxo padrão de cancelamento de matrícula, depois a secretaria de alunos clica em **Enviar Notas** na lista de alunos vazia. O curso fecha limpo, sem notas para contestar.
:::

:::warning Faturas de Vendas NÃO são tocadas no cancelamento
Esta versão não mexe nas Faturas de Vendas quando um curso é cancelado. Faça a reconciliação manualmente — normalmente cancelando a fatura relativa ao curso e criando uma nota de crédito. Uma futura iteração pode automatizar isto; até lá, tratar a limpeza de faturas como uma tarefa separada da secretaria.
:::

### Número Mínimo de Matrículas

Cada **Curso** tem um campo opcional de **Padrão Mínimo de Matrículas**. Cada Curso Agendado tem sua própria substituição de **Matrícula Mínima** (na seção do ciclo de vida). Ambos são _apenas informativos_ — o sistema não cancela automaticamente cursos que não atendem o limite. Use o relatório **Status de Matrículas do Período** (Desk → relatórios) para ver, por Período Letivo, cada Curso Agendado com o seu mínimo, matrículas atuais e a diferença. Cursos com matrículas abaixo do mínimo são destacados; cancele-os pelo fluxo de trabalho acima antes do início das aulas.

### Lembretes de notas atrasadas

Quando o **avanço automático** é ativado, todos os dias o agendador envia emails a qualquer instrutor cujo Curso Agendado passou da data de envio de noras e ainda não está no estado **Fechado**. A função de Secretaria é CC'd. O lembrete é enviado uma vez por Curso Agendado (sinalização idempotente impede remessas de repetição).

### Auto-semeando critérios de avaliação do curso

Um novo Curso Agendado não começa em branco. Assim que você salvar um novo Curso Agendado, sua tabela de **Critérios da Avaliação** é auto-preenchida do `Critério da Avaliação` do Curso pai (definida em **Curso → Avaliação**). O mapeamento copia o título, link dos critérios e peso — portanto, se o seu curso tiver 100% de peso atribuído, o novo Curso Agendado começa quase pronto para ensinar, sem entrada de dados manuais.

Se você mudar o curso de um curso agendado existente, o semeamento **não** executa novamente — ele só dispara uma vez na criação. Para puxar uma nova cópia, use **Importar o modelo do curso** abaixo.

:::tip Crie avaliações de cursos primeiro
Configure o Critério de Avaliação do Curso pai (Curso → Aba Avaliação) com pesos somando 100% antes de criar qualquer Curso Agendado. A mesma configuração transfere automaticamente todo período letivo.
:::

### Reutilizando um Curso Agendado como modelo

A semente automática acima cobre os critérios de avaliação, mas um cronograma de cursos completo, tipicamente tem mais: capítulos, aulas (com vídeos, PDFs, notas de instrutor) e links de avaliação direcionados para aulas específicas. Para reutilizar tudo isso em outros períodos letivos:

1. Abra o curso pai (Desk → Curso → _seu curso_).
2. Na guia **Avaliação**, defina o **Modelo padrão de Curso Agendado** para o Curso Agendado que você deseja usar como estrutura canônica.

Então, ao criar um novo Curso Agendado para aquele curso:

1. Salve o novo Curso Agendado como de costume (semente de critérios de avaliação automaticamente - não é necessário inserir manualmente).
2. No formulário do novo agendamento, clique em **Ações → Importar modelo de curso**.
3. O diálogo pré-preenche com o modelo padrão do curso; você pode escolher qualquer outro curso agendado do mesmo curso. Clique **Importar**.

A importação copia:

- **Capítulos** (incluindo pacotes SCORM, referências de arquivos compartilhados entre os programas)
- **Lições** — cada uma, independentemente de ter um link para avaliação. Vídeos, PDFs, notas de instrutor, conteúdo, flag de permitir discussão — tudo é copiado.
- **Critérios da avaliação** — substitui o que há no novo Curso Agendado (então as linhas auto-preenchidas são substituídas pelo modelo). Links de avaliação a nível da lição são remapeados automaticamente para os critérios do novo Curso Agendado.

A importação **não** copia:

- Participantes, matrículas ou dados avaliados
- Data de entrega das avaliações (ficam nulas até defini-las para o novo período letivo)
- Histórico de cancelamento ou datas de fluxo de trabalho

Um comentário no Curso Agendado registra o que foi importado, de onde, quando e por quem.

**Restrições:**

- Disponível no estado **Rascunho** ou **Aberto para matrícula** — uma vez que o período de matrícula é fechado, a estrutura é confirmada.
- Permitido ao **Usuário Acadêmico**, **Gerente Seminário** ou **Secretaria**.
- Recusa se o Curso Agendado alvo já tem capítulos (a operação importa tudo, não faz uma mesclagem). Para importar novamente, exclua os capítulos existentes primeiro.
- Recusa se o Curso Agendado fonte não tem critério de avaliação, ou se seus pesos não somam 100% - conserte a fonte primeiro.

:::warning A importação não é reversível
Não há "desfazer" para a importação. O diálogo avisa sobre isso. Se você importou o modelo errado, exclua os capítulos e tente novamente.
:::

## 13. Defina os papéis de usuário

Consulte [Papéis de Usuário](../administration/user-roles.md) para obter detalhes sobre a configuração de acesso de instrutores, estudantes e administradores.

## 14. Entrada manual OU Importar os seguintes dados

O seguinte deve estar presente para que você comece seu primeiro termo.
Se você tiver um pequeno número de alunos e preferir fazê-lo manualmente, ao criar um Estudante, o SeminaryERP criará um usuário vinculado e um cliente. No entanto, também é fácil importar esses dados. Você pode seguir [estas instruções](https://docs.frappe.io/erpnext/data-import).

| _**Importar**_ nesta ordem                 | _**Insira manualmente**_ nesta ordem       |
| ------------------------------------------ | ------------------------------------------ |
| 1º. Usuários               | 1º. Estudantes             |
| 2º. Clientes               | 2º. Cursos                 |
| 3º. Estudantes             | 3º. Lista de Feriados      |
| 4º. Cursos                 | 4º. Matrículas no Programa |
| 5º. Lista de Feriados      |                                            |
| 6º. Matrículas no Programa |                                            |

Em seguida, você precisa vincular cursos aos seus programas.
**É altamente recomendado** verificar novamente a importação e **complementar** a informação sobre Cursos antes de adicioná-los aos Programas. Os cursos propagarão várias informações a **Curso Agendados**, então a integralidade dessas informações acelerará o trabalho a cada termo.
Para adicioná-los em massa, navegue até os Cursos, selecione todos os cursos que deseja adicionar a um programa, e clique em **Ações** ⇒ **Adicionar ao Programa**. Uma janela pop-up abrirá onde você precisa selecionar o Programa ao qual estes cursos devem ser adicionados. A janela também tem uma caixa de seleção para indicar se todos os cursos selecionados devem ser obrigatórios para este programa ou não.

## 15. Importar notas existentes

SeminaryERP usa um único processo para aceitar notas de outros seminários que também servem para importar notas de qualquer sistema legado, manualmente ou através de arquivos CSV. Veja [Importação de Notas de Sistema Legado](legacy-grade-import.md) para o fluxo de trabalho completo — configuração do seminário de parceria única, criação de equivalência em massa, validação de execução em dry-run e finalização idempotente.

## 16. Adicionar Instrutores

Crie um registro de **Instrutor** para cada pessoa que ensinará. Cada instrutor precisa de um **Usuário do Sistema** vinculado (para que possa fazer login no Desk e LMS) e um **Tipo de Instrutor** que reflete como eles são pagos:

- **Voluntário** — somente para sem pagamento ou honorário. Clique em _Criar Fornecedor_ no formulário para permitir a cobrança de honorários através da fatura de compra.
- **Assalariado** ou **Por-Curso** — requer [HRMS Folha de Pagamento habilitado](../modules/instructor-payment.md) e um registro de funcionário vinculado.

Para fins de acreditação, preencha a seção **Educação** com os graus de cada instrutor, instituições e documentos de suporte. Quando um funcionário é vinculado, use _Educação → Importe do Colaborador_ para copiar a educação já registrada no HRMS em vez de inseri-la novamente.

---

Depois que todos os items acima estiverem configurados, vá para [Seu Primeiro Período](first-term.md).
