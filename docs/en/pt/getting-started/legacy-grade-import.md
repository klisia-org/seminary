# Importação de Notas Legadas},{

O SeminaryERP usa uma única abordagem tanto para créditos de transferência de uma instituição parceira quanto para o preenchimento retroativo em massa de notas de um sistema legado. O modelo trata "nossa própria história pré-SeminaryERP" como um Seminário Parceiro autorreferenciado, de modo que o mesmo fluxo de trabalho que ingere o histórico escolar de um aluno transferido também incorpora décadas de dados históricos.

A importação é um fluxo de trabalho em etapas e idempotente:

**Seminário Parceiro → Equivalências de Disciplinas → Lote de Importação de Histórico (Rascunho → Dry-Run → Enviar)**

O Dry-Run resolve cada linha com base nas equivalências e na política de conversão sem mexer no registro do estudante. Enviar efetiva cada linha na Matrícula no Programa do estudante e atualiza os totais da auditoria de graduação. Reenviar o mesmo (estudante, código da disciplina de origem, período de origem) atualiza a linha existente do histórico no local — sem duplicatas.

## 1º. Configuração única (Legado Interno)

Para importar os dados históricos da sua própria instituição, crie um **Seminário Parceiro** autorreferenciado e uma **política de conversão de notas**. Cadastre uma vez, reutilize para sempre.

1. **Crie a Política de Conversão de Notas "Identidade (Interno)"**
   - Escala de Notas de Origem = sua escala interna
   - Escala de Notas de Destino = sua escala interna (mesma)
   - Método de Conversão = `identity`
   - Enviar. Políticas enviadas podem ser referenciadas por registros de Seminário Parceiro; rascunhos não.
2. **Crie o registro de Seminário Parceiro**
   - Nome: p.ex. `ESWA Legacy (pre-2026)`
   - `Is Internal Legacy`: marcado (essa opção fica somente leitura após a criação, impede a exclusão e oculta o registro das visualizações de lista padrão)
   - `Counts in GPA`: marcado (notas legadas SÃO as notas da sua própria instituição — devem participar do cálculo do GPA)
   - `Credit Unit Ratio`: `1,0`
   - Escala de Notas Padrão = sua escala interna
   - Política de Conversão Padrão = `Identity (Internal)`
3. **Criar em lote as Equivalências de Disciplinas**
   - Abra a visualização de lista de Equivalência de Disciplinas do Seminário Parceiro.
   - Clique em **Create Legacy Integration** (apenas para Gerente do Sistema).
   - Selecione o Seminário Parceiro legado que você acabou de criar.
   - Uma equivalência `legacy_identity` submetida é criada por disciplina no seu catálogo, mapeando a disciplina a si mesma. Disciplinas já mapeadas são ignoradas — a ação é idempotente.

Após isso, o Seminário Parceiro legado está pronto para receber importações de históricos. Vá para a etapa 3 para o fluxo real de importação.

## 2º. Configuração única (Parceiro Externo)

Para um parceiro realmente externo (um seminário parceiro transferindo créditos para cá):

1. Crie (ou reutilize) a **Escala de Notas** do parceiro se for diferente da sua. Enviar.
2. Crie a **Política de Conversão de Notas** da escala do parceiro para a sua escala interna:
   - Escolha um `conversion_method`: `identity`, `linear_multiplier`, `linear_with_offset`, `interval_map` ou `manual_per_course`.
   - Para `linear_*`, defina o `multiplier` (e o `offset`, se aplicável). Ex. Escala francófona 0–20 → Porcentagem interna = ×5.
   - Para `interval_map`, preencha a tabela de mapeamento símbolo a símbolo. Os menus de seleção Símbolo de Origem e Símbolo de Destino são preenchidos automaticamente a partir das respectivas escalas — todo símbolo de origem deve ser mapeado (símbolos de destino sem origem são permitidos).
   - Enviar.
3. Crie o registro de **Seminário Parceiro** para a instituição:
   - `Is Internal Legacy`: desmarcado
   - `Counts in GPA`: geralmente desmarcado (padrão do setor — créditos transferidos contam para o diploma mas não para o GPA)
   - `Credit Unit Ratio`: horas-crédito internas por 1 unidade de crédito do parceiro (por exemplo, `0,5` para ECTS → horas de semestre dos EUA com metade do peso)
   - `Minimum Transferable Grade`: código de nota na sua escala interna abaixo do qual transferências são bloqueadas no momento do commit (p.ex., `C`)
   - Escala de Notas Padrão / Política de Conversão Padrão = o que você acabou de criar
4. Crie **Equivalências de Disciplinas do Seminário Parceiro** uma de cada vez, da disciplina do parceiro para a sua disciplina interna:
   - Preencha `source_course_code`, `source_course_name`, `source_credit_value` e a `internal_course` de destino.
   - Substituições opcionais por disciplina: `credit_override` (para forçar uma contagem específica de créditos), `conversion_policy_override` (para uma disciplina em uma escala diferente da padrão do parceiro — p.ex., um departamento de música em aprovação/reprovação).
   - Anexe um `Supporting Document` (aprovação da direção, ata de comitê, carta do credenciador) para trilha de auditoria.
   - Enviar. Apenas equivalências enviadas podem ser usadas durante a importação.

Equivalências de disciplinas são enviáveis: para alterar uma, cancele e faça uma emenda — a versão antiga é mantida via `amended_from`, e as linhas de histórico existentes continuam referenciando a original.

## 3º. Importando históricos

O Lote de Importação de Histórico de Parceiro atende tanto ao caso manual de um único estudante quanto ao caso em massa via CSV. Cada lote contém:

- `Partner Seminary`: de qual parceiro são os dados representados por este lote
- `Target Program`: o programa interno ao qual os créditos se aplicam
- `Target Academic Term`: o período letivo interno ao qual estas linhas estão ancoradas (normalmente o período atual do estudante para transferência externa, ou um período legado designado para preenchimento retroativo)

### Entrada manual (um estudante)

1. Crie um novo **Partner Transcript Import Batch**.
2. Selecione Partner Seminary, Target Program, Target Academic Term. Salvar. _(Os preenchimentos automáticos ativam somente após o primeiro salvamento.)_
3. Na tabela Rows, adicione uma linha por disciplina:
   - `Student` (Link) OU `Student Email` — qualquer um identifica o estudante. Se apenas o e-mail for fornecido, o dry-run o resolve para o registro de Student via `Student.user`.
   - `Source Course Code` — menu preenchido a partir das equivalências enviadas para esse parceiro. Selecionar um código preenche automaticamente `Source Course Name` e `Source Credit Value` a partir da equivalência.
   - `Source Term` — texto livre (os períodos do parceiro não são rastreados aqui como registros de Academic Term).
   - `Source Grade` — menu preenchido com os códigos de nota da escala de notas padrão do parceiro.
   - `External Reference` — ID opcional do sistema de origem; tem precedência sobre a chave natural de idempotência.
4. **Salvar**, depois clique em **Run Dry-Run**.
5. Se o dry-run estiver limpo, o status avança para `Dry-Run Clean`. Clique em **Enviar**.

### Entrada em massa por CSV

1. Use a ferramenta nativa de **Data Import** do Frappe (use a barra de pesquisa) --> Add Data Import

2. Document type: Partner Transcript Import Batch Import
   Import Type: Insert New records
   A única caixa de seleção marcada deve ser Don't send emails.
   **Salvar**

3. Você pode baixar um modelo de CSV pela ferramenta para enviar seus dados. Observe que não é necessário repetir os campos iniciais (seminário de origem, programa de destino e período letivo de destino)

    ```csv
    Seminário Parceiro,Programa de Destino,Período Acadêmico de Destino,Código da Disciplina de Origem (Linhas),Nota de Origem (Linhas),Período de Origem (Linhas),E-mail do estudante (Linhas)
    T-LINK,Master of Divinity,2025-2026 (SP26),SFD-101,A,1S 24,modest@gmail.com
    ,,,THM-201,A,1S24,modest@gmail.com
    ```

4. Após a importação bem-sucedida, abra o Lote — todas as linhas devem estar na grade com `Student` em branco e `Student Email` preenchido.

5. Clique em **Run Dry-Run**. Cada linha é resolvida:
   - E-mail → Link do Estudante
   - Disciplina de origem → disciplina interna via a equivalência
   - Créditos de origem → créditos internos (via `credit_override`, `source_credit_value` da equivalência ou o próprio valor da linha × `credit_unit_ratio`)
   - Nota de origem → nota de destino via a política de conversão

6. Corrija quaisquer avisos (veja a referência abaixo) e depois clique em Enviar.

## 4º. Referência de avisos do Dry-Run

| Aviso                          | Significado                                                                                                                                  | Correção                                                                                                                                      |
| ------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------- |
| `unknown_student_email`        | Nenhum registro de Student tem um campo `user` correspondente ao e-mail.                                                     | Corrija o e-mail na linha ou atualize o link de Usuário do Student.                                                           |
| `no_submitted_equivalence`     | Nenhuma Equivalência de Disciplina enviada para este parceiro + código de origem.                                            | Crie e envie a equivalência ou corrija o código de origem.                                                                    |
| `zero_credits`                 | O crédito de origem da linha está em branco e a equivalência não possui `source_credit_value` / `credit_override`.           | Preencha o `source_credit_value` da linha ou edite a equivalência para ter um padrão.                                         |
| `below_minimum_transferable`   | A nota convertida está abaixo do `Minimum Transferable Grade` do parceiro.                                                   | Julgamento da secretaria acadêmica — pule a linha ou adicione uma `Override Note` para aceitá-la.                             |
| `clamped_high` / `clamped_low` | A conversão linear produziu um valor fora da escala de destino; o resultado foi limitado.                                    | Normalmente aceitável; informativo. Revise o multiplicador da política se a limitação ocorrer com frequência. |
| `no_mapping`                   | Uma conversão `interval_map` não tinha linha para este símbolo de origem, ou a nota não foi encontrada na escala de destino. | Emende o mapeamento da política para cobrir o símbolo ausente.                                                                |
| `unparseable_source`           | A conversão linear não conseguiu interpretar a nota de origem como um número.                                                | Corrija a nota de origem ou mude a política para `interval_map` / `manual_per_course`.                                        |

Uma linha com aviso bloqueia o Dry-Run Clean, a menos que a secretaria acadêmica preencha `Override Note` nessa linha. O commit tem proteção adicional: toda linha deve ter um `Student` resolvido para que o envio seja bem-sucedido.

## 5º. Enviar

Ao enviar:

- Cada linha se torna um lançamento transferido de `Program Enrollment Course` na Matrícula no Programa do estudante para (Target Program, Target Academic Term). `Is Transfer` fica marcado; `Partner Seminary`, `Mapping Type`, `Course Equivalence`, `Conversion Policy Applied`, `Source Course Code`, `Source Term`, `Source Grade`, `External Reference` são todos registrados para auditoria.
- O `Total Credits` da Matrícula no Programa é recalculado a partir da SOMA das linhas aprovadas.
- Os créditos da trilha de ênfase são recalculados; ênfases concedidas automaticamente são marcadas.
- A visualização de histórico voltada ao estudante mostra as disciplinas transferidas ao lado das internas.

## 6º. Reexecutando e emendando

O lote é idempotente. Reenviar um lote com as mesmas linhas atualiza as entradas existentes do histórico no local (correspondência em `partner_seminary + source_course_code + source_term`, ou `external_reference` quando presente). Para corrigir dados:

- **Correção no mesmo período** — Crie um novo lote com as linhas corrigidas; as linhas de PEC existentes são atualizadas. Os totais são atualizados.
- **Período errado selecionado** — Cancele o lote original (com supervisão; bloqueado se linhas de histórico ainda existirem) e crie um novo lote com o `Target Academic Term` correto.
- **Correção de política** — Emende a Política de Conversão de Notas (a emenda nativa do Frappe cria a linhagem `amended_from`). Os históricos existentes continuam referenciando o ID da política original; novas importações usam a versão emendada. Isso preserva a reprodutibilidade histórica.

## Relacionado

- [Configuração Inicial](initial-setup.md) — a sequência completa de primeira instalação
- [Frappe Data Import](https://docs.frappe.io/framework/user/en/data-import)
