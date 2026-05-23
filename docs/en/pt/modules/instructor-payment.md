# Pagamento de Instrutores

SeminaryERP oferece três formas de pagar instrutores: como **voluntários** recebendo honorários, como funcionários **assalariados**, ou em base **por curso / por estudante**. Esta página orienta você na configuração de tudo isso.

## Visão geral

Cada registro de instrutor tem um campo **Tipo de Instrutor**. Escolha a opção que descreve como a escola remunera essa pessoa:

| Tipo de Instrutor | Como são pagos                                                     | O que você irá configurar                                                                     |
| ----------------- | ------------------------------------------------------------------ | --------------------------------------------------------------------------------------------- |
| **Voluntário**    | Honorário / "oferta de amor" por visita                            | Um registro de Fornecedor + Faturas de Compra                                                 |
| **Assalariado**   | Salário fixo recorrente                                            | Funcionário padrão do HRMS + Estrutura Salarial                                               |
| **Por Curso**     | Pago por curso ministrado, opcionalmente por estudante matriculado | Funcionário do HRMS + o componente **\"Instructor Pay\"** (automatizado) |

Você pode combinar entre o corpo docente — alguns assalariados, alguns por curso, alguns voluntários — todos no mesmo sistema de folha de pagamento.

O fluxo de **Voluntário** funciona sozinho, sem aplicativos extras. Os fluxos **Assalariado** e **Por Curso** exigem que o aplicativo Frappe HRMS esteja instalado no seu site.

---

## Pré-requisitos (apenas para Assalariado e Por Curso)

Ignore esta seção se você planeja pagar apenas voluntários por meio de Fatura de Compra.

### 1º. Instalar o HRMS

Peça ao administrador do bench para instalar o aplicativo Frappe HRMS no seu site. No terminal do bench, é assim:

```
bench get-app hrms
bench --site <your-site> install-app hrms
```

> **Observação:** o HRMS `v16.5.1` tem um erro conhecido de instalação com o ERPNext v16. Se a instalação falhar com o erro `repost_allowed_types`, fixe o HRMS na tag `v16.4.8`:
>
> ```
> cd ~/frappe-bench/apps/hrms
> git checkout v16.4.8
> ```
>
> …em seguida, tente novamente `bench install-app hrms`.

### 2º. Habilitar HRMS Payroll nas Configurações de Seminário

Abra **Seminary Settings** no Desk, role até a seção **HR / Payroll** e marque **Enable HRMS Payroll**. Salvar.

Ao salvar, isto irá:

- Adicionar os campos de pagamento de instrutor por categoria a cada Salary Slip.
- Criar um Salary Component pronto para uso chamado **\"Instructor Pay\"**.

Se você vir um erro dizendo que o HRMS não está instalado, volte ao passo 1.

### 3º. Definir a HRMS Live Date

Ainda em **Seminary Settings → HR / Payroll**, preencha **HRMS Live Date (Pay Cutoff)** com a data em que sua escola começará a usar o HRMS para a folha de pagamento.

Cursos cuja data de início seja **anterior** a esse corte **não** aparecerão na folha de pagamento. Isso evita que você, por engano, puxe anos de cursos históricos para sua primeira execução de folha de pagamento. Deixe em branco somente se quiser incluir todos os cursos registrados.

### 4º. Escolher uma política de divisão de pagamento

**Instructor Payment Split** informa ao sistema quando o pagamento por curso é liberado nas execuções da folha de pagamento:

- **End of period** (padrão) — o valor total é pago no Salary Slip cujo período contém a data de término do curso.
- **50% at start + 50% at end** — metade paga no Salary Slip que contém a data de início do curso e a outra metade no Salary Slip que contém a data de término do curso.

Escolha uma. Você pode alterá-la depois, mas as mudanças só afetam cursos pagos dali em diante.

---

## Categorias de Instrutor

Todo instrutor atribuído a um curso possui uma **Categoria** — \"Instrutor Responsável\", \"Assistente de Ensino de Pós-Graduação\", \"Avaliador\", etc. As categorias determinam duas coisas: relatórios de acreditação e quanto o instrutor recebe.

O sistema vem com quatro categorias padrão: **Instrutor Responsável**, **Co-instrutor**, **Assistente de Ensino de Pós-Graduação**, **Avaliador**. Você pode adicioná-las, renomeá-las ou ocultá-las em **Desk → Instructor Category**.

Observação: atualmente, não há configuração para pagamento diferente por programa ou nível de programa. Se isso for importante para você, crie uma issue em nosso repositório no GitHub. Uma forma de fazer isso sem programar é simplesmente criar uma nova categoria, por exemplo, \"Instrutor Responsável - PhD\" com valores de taxa de pagamento diferentes.

### Vinculando taxas de pagamento a uma categoria

Abra uma **Instructor Category** e role até **Pay Rates**. Cada linha é uma taxa:

| Coluna                 | O que significa                                                                                                                     |
| ---------------------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| **Modo de Pagamento**  | `Per-Course` (valor fixo por curso) ou `Per-Student` (valor × tamanho da turma)               |
| **Valor**              | Quanto pagar                                                                                                                        |
| **Moeda**              | A moeda para esta taxa (suporta USD para programas financiados por doadores e moeda local para operações locais) |
| **Válido a partir de** | A data em que esta taxa entra em vigor                                                                                              |
| **Ativo**              | Marque a taxa atual. Desmarque as antigas para manter o histórico visível, porém sem uso                            |

Você pode ter uma linha Por Curso e uma linha Por Estudante ativas ao mesmo tempo — o sistema paga ambas. Para alterar uma taxa, **desmarque Ativo na linha antiga** e **adicione uma nova linha** com o novo valor e uma nova data em **Válido a partir de**. Isso mantém o histórico de pagamento preciso para Salary Slips passados.

#### Exemplo: categoria \"Instrutor Responsável\"

| Modo de Pagamento | Valor | Moeda | Válido a partir de | Ativo                              |
| ----------------- | ----- | ----- | ------------------ | ---------------------------------- |
| Por Curso         | 200   | USD   | 2024-01-01         | ☐ (taxa antiga) |
| Por Curso         | 300   | USD   | 2026-01-01         | ☑ (atual)       |
| Por Estudante     | 10    | USD   | 2024-01-01         | ☑                                  |

Um Instrutor Responsável lecionando um curso no outono de 2025 com 8 estudantes receberia 200 + 80 = **US$ 280**. O mesmo curso na primavera de 2026 receberia 300 + 80 = **US$ 380**.

---

## Atribuindo uma categoria em cada curso

Ao criar ou editar um **Course Schedule**, a tabela **Instructors** agora tem uma coluna **Category**. Escolha a categoria para cada instrutor nesse curso. A categoria determina quais taxas se aplicam para aquela pessoa naquele curso específico.

Quando a Folha de Pagamento do HRMS está habilitada, salvar um **Course Schedule** sem categoria em cada linha de instrutor é bloqueado — isso evita esquecer o pagamento de alguém.

Após atribuir os instrutores, abra o registro de cada instrutor uma vez e clique em **Update Instructor Log** (ou aguarde a atualização no próximo carregamento). Isso sincroniza o curso com o registro deles, a partir do qual a folha de pagamento lê.

---

## Configurando cada fluxo de pagamento

### Fluxo de voluntário

Para palestrantes convidados ou professores visitantes que recebem um honorário:

1. Crie o registro de **Instructor** com **Instructor Type = Volunteer**.
2. Abra o formulário de **Instructor** e clique em **Actions → Create Supplier**. Um registro de **Supplier** é criado automaticamente com o nome, e-mail e telefone copiados do **Instructor**. O vínculo de **Supplier** é salvo de volta no **Instructor**.
3. Sempre que quiser pagar o voluntário, crie uma **Purchase Invoice** para esse **Supplier**. Adicione um Item (por exemplo, \"Instructor Honorarium\") e o valor.
4. Envie a **Purchase Invoice** e, em seguida, crie um **Payment Entry** para efetuar o pagamento.

Voluntários **não** precisam de um registro de **Employee** e **não** aparecem em **Payroll Entry**. A remuneração deles é acompanhada no razão de fornecedores usual.

### Fluxo assalariado

Para funcionários em tempo integral ou parcial com salário recorrente:

1. Crie o registro de **Employee** (módulo de RH).
2. Crie ou edite o registro de **Instructor** e defina **Instructor Type = Salaried**. Vincule ao **Employee**.
3. Crie uma **Salary Structure** (por exemplo, \"Instructor — Full-Time\") com os **Salary Components** necessários (Base, auxílios, deduções).
4. Crie uma **Atribuição de Estrutura de Salário** conectando o **Funcionário** à **Estrutura de Salário**.
5. Execute o **Payroll Entry** na sua programação mensal normal. O HRMS faz o restante.

Nenhuma configuração específica do seminário é necessária — este é o HRMS padrão.

### Fluxo Por Curso

Para instrutores pagos por curso ministrado:

1. Crie o registro de **Employee**.
2. Crie ou edite o registro de **Instructor** e defina **Instructor Type = Per-Course**. Vincule ao **Employee**.
3. Garanta que a **Instructor Category** atribuída em cada **Course Schedule** deste instrutor tenha **Pay Rates** definidas (veja a seção acima).
4. Crie uma **Salary Structure** chamada algo como \"Instructor — Per-Course\". Na tabela **Earnings**, adicione uma única linha:
   - **Salary Component:** `Instructor Pay` _(este componente foi criado automaticamente quando você habilitou o HRMS Payroll — não o recrie)_
5. Atribua a **Estrutura de Salário** ao **Funcionário** via **Atribuição de Estrutura de Salário**.

É isso. Quando o **Payroll Entry** é executado, o sistema calcula o pagamento com base nos cursos ministrados nesse período × as taxas da categoria, e coloca o resultado no Salary Slip.

Você **não** precisa de componentes por categoria (\"IoR Pay\", \"GTA Pay\"). O único componente \"Instructor Pay\" atende a todas as categorias, porque as taxas ficam nas próprias categorias.

---

## Executando a folha de pagamento

Execute o **Payroll Entry** da mesma forma de sempre:

1. **HR → Payroll → Payroll Entry → New**.
2. Defina as datas do período, a empresa e o filtro de **Atribuição de Estrutura de Salário**.
3. Enviar. O HRMS gera um Salary Slip por funcionário.

Abra um Salary Slip gerado. Perto do topo, na seção **Instructor Pay Inputs**, você verá:

- **Computed Instructor Pay** — o total calculado.
- **Instructor Log Summary** — um detalhamento somente leitura que mostra, para cada curso pago neste Salary Slip: o curso, a categoria, a taxa aplicada, a fração (100% ou 50%), o evento de pagamento (Start / End) e o subtotal.

Esta é a sua trilha de auditoria. Se algo parecer incorreto, esta tabela informa exatamente quais cursos e taxas foram usados.

### Reexecutando a folha de pagamento

Se você cancelar um Salary Slip e reexecutar o **Payroll Entry**, o sistema exclui automaticamente os cursos que foram pagos no Salary Slip cancelado. **Você não pode pagar em dobro por engano.**

---

## Conciliação: o relatório **Unpaid Instructor Log**

Após cada ciclo de folha de pagamento, verifique **Reports → Unpaid Instructor Log**. Ele lista cada linha de ensino (instrutor × curso) cujo período terminou, mas que ainda não foi pago em 100%.

Isso identifica os erros comuns:

- Um instrutor que não tem um **Employee** vinculado, portanto foi ignorado.
- Um **Course Schedule** sem categoria atribuída (não deveria acontecer com a validação ativada, mas será identificado se ocorrer).
- Uma categoria sem taxa de pagamento definida.
- Uma execução de folha que simplesmente não foi feita em determinado mês.

Filtros no topo permitem restringir por instrutor, período acadêmico ou categoria.

---

## Tarefas do dia a dia

### Adicionando uma nova categoria de instrutor

1. **Desk → Instructor Category → New**. Forneça um nome, descrição e marque **Is Instructor of Record?** se ela deve contar para a acreditação.
2. Abra **Seminary Settings** e salve uma vez (não são necessárias alterações — apenas **Save**). Isso atualiza os campos do Salary Slip para que os contadores da nova categoria apareçam em Salary Slips futuros.
3. Adicione taxas de pagamento à categoria conforme descrito acima.

### Alterando uma taxa (por exemplo, aumento de fim de ano)

1. Abra a **Instructor Category**.
2. Na linha ativa atual em **Pay Rates**, **desmarque Ativo**.
3. Adicione uma nova linha com o novo valor e uma nova data em **Válido a partir de**.
4. Salvar.

Salary Slips históricos continuam usando automaticamente a taxa antiga (com base na data de início do curso), portanto a folha passada não é afetada.

### Iniciando um novo ano acadêmico com uma nova Live Date

Se quiser redefinir o que conta para a folha do HRMS (por exemplo, seu primeiro ano usou uma política piloto), atualize **Seminary Settings → HRMS Live Date** para o novo corte. Somente cursos que começarem na data do novo corte ou depois serão considerados.

---

## Perguntas comuns

**O mesmo instrutor pode ter categorias diferentes em cursos distintos?**
Sim. A categoria é por linha de instrutor no **Course Schedule**, não por instrutor. Um professor pode ser \"Instrutor Responsável\" em um curso e \"Co-instrutor\" em outro.

**O que acontece se eu me esquecer de atribuir uma categoria a um curso?**
Quando o HRMS Payroll está habilitado, salvar o **Course Schedule** é bloqueado até que cada linha de instrutor tenha uma categoria. As categorias também têm padrão em branco; você pode usar um script ou atualização em massa para preencher.

**E se um curso intensivo ocorrer dentro de um período mais amplo?**
Preencha **Start Date** e **End Date** no próprio **Course Schedule**. Quando essas datas são definidas, o sistema as usa em vez das datas do período acadêmico — assim, um intensivo de duas semanas é pago no Salary Slip cujo período contém o término do intensivo, não o do período.

**E se um voluntário mais tarde se tornar um instrutor remunerado?**
Altere o **Instructor Type** dele de Volunteer para Salaried ou Per-Course. Vincule a um registro de **Employee**. O vínculo antigo de **Supplier** permanece (para **Purchase Invoices** históricas), mas é ignorado daqui para frente.

**Posso ver quanto um Salary Slip vai pagar antes de executá-lo?**
Sim. Crie um **Salary Slip** manualmente para o funcionário e período — a seção **Instructor Log Summary** é preenchida assim que você salva como rascunho.
