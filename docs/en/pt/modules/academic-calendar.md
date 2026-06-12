# Calendário Acadêmico

O calendário acadêmico gerencia períodos letivos, datas importantes e regras de prazos. Todos os aspectos são controlados pelo Desk.

## Visão geral

O calendário acadêmico tem uma estrutura em camadas:

### Ano Letivo:

Contém períodos letivos. Pode ser usado para disparar taxas específicas. No Período Acadêmico, você pode ver se e quando as faturas de "Ano Novo Acadêmico" (NAY) foram geradas.

### Período Letivo:

Os períodos letivos não podem se sobrepor. Todos os mandatos devem ser integralmente incluídos num Ano Académico, com datas de início e de fim no Ano Acadêmico. Os Termos Acadêmicos podem ser usados para acionar taxas específicas, e você pode ver se e quando as faturas do "Novo Termo Acadêmico" (NAT) foram geradas.
Cada termo acadêmico define a estrutura de um período de ensino: datas de início e fim e prazos de retirada (datas para cada [regra de retirada](withdrawal.md#withdrawal-rules)). Além disso, os Termos Acadêmicos são usados em todo o sistema como "ancoras" para calcular outros eventos, como período de matrícula e classificação (em Configurações do Seminário).

### Regras da Janela de Inscrição

As janelas de matrícula nos cursos controla **quando um Curso Programado abre e fecha para matrícula pelos alunos** (além de uma terceira data de corte para _fechamento de notas_).  São definidas uma vez, para todo o seminário, em **Configurações do Seminário  → Regras de Janela de Matrícula**, e aplicadas a cada Curso Programado automaticamente.

Cada uma das três janelas é definida com uma **âncora** mais um **deslocamento em dias**:

- **Âncora** — a data de referência da contagem de deslocamento de:
  - `term_start` / `term_end` — O [Período Letivo](#academic-term) data de início/término do mesmo.
  - `classes_start` / `classes_end` — _desse_ Curso Agendado da própria data de início/fim.
- **Offset (dias)** — quantos dias da âncora. **Negativo = antes** da âncora, positivo = depois, '0' = na própria âncora.

As três janelas:

| Janela                      | O que ele controla                                                                                                                                            |
| --------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Matrícula Aberta**        | Quando a programação do curso passa do _rascunho_ para o _Aberto para inscrição_ — os alunos podem se matricular.                             |
| **Fechamento da matrícula** | Quando ele se desloca de _Aberto para Matrícula_ para _Matrícula Encerrada_ — a matrícula para.                                               |
| **Fechamento de Notas**     | Prazo para envio de notas finais. Depois de passar, instrutores de cursos ainda sendo avaliados recebem e-mails de lembretes. |

> **Deixe uma âncora em branco para desistir** dessa janela. Sem nenhuma Matrícula Aberta
> (e nenhuma substituição), um novo Curso Agendado abre para matrícula
> _imediatamente_ na criação ao invés de esperar no Rascunho.

\*\*Avanço automático. \* Quando **avançar automaticamente o Curso Agendado** está ativado em
Configurações de seminário, um gatilho diário promove cada Curso Agendado conforme as datas chegam
(Rascunho → Abrir para matrícula → Matrícula Fechada). Com isso, as datas ainda são
calculadas e mostradas, mas o pessoal move cursos através dos estados à mão.

**Substituições por curso.** A regra em todo o seminário é apenas a padrão. Qualquer
Curso Agendado pode substituir uma data na sua seção **dados de matrícula**
(_Substituição de data de abertura_, _Substituição de data de Fechamento da Matrícula_,
_Substituição de data de Fechamento de Nota_) — o substituto sempre vence para esse curso. Use-o
para um curso adicionado tarde ou uma exceção única.

#### Exemplos práticos

Cada exemplo lista os valores a serem inseridos em **Configurações do seminário → Regras de Janelas de Matrícula**.

##### Exemplo 1 - Todos os cursos em um período letivo abrem e fecham juntos

Todos se matriculam durante uma única janela de todo o período letivo, não importa quando cada classe
realmente se encontra.

| Configuração                            | Valor                                                                                                                                              |
| --------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| Âncora de Matrícula Aberta              | Termo_Iniciar\`                                                                                                               |
| Dias da Âncora para Abrir Inscrições    | `-14` &nbsp;_(duas semanas antes do termo começar)_                                                         |
| Âncora para Fechar Inscrições           | Termo_Iniciar\`                                                                                                               |
| Dias da Âncora para Encerrar Inscrições | `7` &nbsp;_(uma semana após o início do período letivo — uma período de graça para inscrição/cancelamento)_ |

##### Exemplo 2 — Cada curso abre relativo a sua própria data de início

Útil quando as aulas dentro de um termo começam em datas diferentes (por exemplo, intensivos ou cursos
modulares).

| Configuração                            | Valor                                                                                                       |
| --------------------------------------- | ----------------------------------------------------------------------------------------------------------- |
| Âncora de Matrícula Aberta              | `classes_start`                                                                                             |
| Dias da Âncora para Abrir Inscrições    | `-30` &nbsp;_(A inscrição abre um mês antes de cada classe começar)_ |
| Âncora para Fechar Inscrições           | `classes_start`                                                                                             |
| Dias da Âncora para Encerrar Inscrições | `0` &nbsp;_(fecha o dia em que a classe começa)_                     |

##### Exemplo 3 - Fechar a matrícula antes do período letivo terminar

| Configuração                            | Valor                                                                                              |
| --------------------------------------- | -------------------------------------------------------------------------------------------------- |
| Âncora de Matrícula Aberta              | Termo_Iniciar\`                                                               |
| Dias da Âncora para Abrir Inscrições    | `0`                                                                                                |
| Âncora para Fechar Inscrições           | Termo_end\`                                                                   |
| Dias da Âncora para Encerrar Inscrições | `-10` &nbsp;_(não há novos matrículas nos últimos 10 dias)_ |

##### Exemplo 4 — Um prazo de avaliação depois do fim das aulas

Parear qualquer uma das janelas acima com um prazo de avaliação:

| Configuração                         | Valor                                                                                                                    |
| ------------------------------------ | ------------------------------------------------------------------------------------------------------------------------ |
| Âncora de fechar notas               | `classes_end`                                                                                                            |
| Dias da Âncora de Fechamento de Nota | `14` &nbsp;_(notas finais devem ser entregues duas semanas após o fim da classe)_ |

Instrutores cujos cursos ainda estejam como _Matrícula Fechada_ ou _Em Avaliação_ depois dessa data recebem alerta automático por email.

##### Exemplo 5 - Nenhuma janela automática (aberta imediatamente)

Deixe **todas as âncoras em branco**. A cada novo cronograma de cursos chega diretamente em _Abrir
para matrícula_ e fica lá até que a equipe o feche manualmente. Escolha isto se
seu seminário gerencia o tempo de matrícula manualmente ou curso a curso.

##### Exemplo 6 - Um curso precisa de uma exceção

Manter a regra em todo o seminário, mas para uma única agenda de curso adicionada atrasadamente, abra
a seção de **dados de matrícula** e defina **data de matrícula** para a data
desejada. Esse curso ignora a regra de seminário; todos os outros não são afectados.

## Conceitos-chave

- **Período Letivo** — a unidade de tempo fundamental (semestre, trimestre, semestre)
- **Resolvedor de Regras de Datas** — lógica configurável para calcular prazos acadêmicos em relação às datas do período letivo
- **Janelas de matrícula** — âncora em todo seminário + regras de deslocamento que abrem e fecham agendas de curso para matrícula (substituível por curso)
- **Regras do período letivo** — a configuração de prazos e políticas fica no nível do período, permitindo regras diferentes por período
