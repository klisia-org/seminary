# Calendário Acadêmico

O calendário acadêmico gerencia períodos letivos, datas importantes e regras de prazos. Todos os aspectos são controlados pelo Desk.

## Visão geral

O calendário acadêmico tem uma estrutura em camadas:

### Ano Letivo:

Contém períodos letivos. Pode ser usado para disparar taxas específicas.

### Período Letivo:

Os períodos letivos não podem se sobrepor. Cada período letivo deve estar totalmente contido em um Ano Letivo, com datas de início e término dentro do Ano Letivo.  
Cada período letivo define a estrutura de um período de ensino: datas de início e término, janelas de matrícula, prazos de trancamento e períodos de avaliação.

## Conceitos-chave

- **Período Letivo** — a unidade de tempo fundamental (semestre, trimestre, quarter)
- **DateRuleResolver** — lógica configurável para calcular prazos acadêmicos em relação às datas do período letivo
- **Regras no nível do período letivo** — a configuração de prazos e políticas fica no nível do período, permitindo regras diferentes por período
