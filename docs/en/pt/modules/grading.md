# Atribuição de Notas

A atribuição de notas é como você decide o que um aluno aproveitou do curso e como você mantém o
controle de que os objetivos pedagógicos serão alcançados. SeminaryERP lhe dá dois lugares para trabalhar, e eles
se encaixam bem juntos: um **Cartão To-Do** que mostra o que está esperando sua
atenção, e um **Quadro de Notas** que lhe dá a imagem toda em uma grade.

## Visão geral

Dar Notas no SeminaryERP se baseia em torno de duas ideias:

- **Critério da Avaliação** defina _o que conta_ para a nota final de um curso
  (o conteúdo programático diz "30% de artigos, 20% de questionários, 50% de teste final" e
  os critérios da Avaliação expressam isso no Curso Agendado).
- **Submissões** são _o que os alunos enviam_ (um artigo, uma tentativa do teste, um exame
  , uma publicação de discussão). Cada submissão é avaliada em função do
  Critério de Avaliação a que pertence, e então se eleva ao total de
  dos alunos.

Algumas avaliações não têm uma submissão - participação da capela,
de classe, uma apresentação na classe. Esses usam um tipo especial
chamado **Offline**, onde você entra na nota diretamente no Quadro de Notas
sem qualquer artefato entregue no sistema.

## Tipos de avaliação

Quando você cria um Critério da Avaliação (na página de Avaliação do Curso),
você escolhe um **tipo**. Este tipo decide como a avaliação é coletada
e como os alunos enviam (ou não).

### Teste

Auto-avaliado múltipla escolha / perguntas estilo verdadeiras-falsas / de resposta curta.
O aluno faz o teste no navegador, e o sistema já mostra a nota corrigida quando o teste é submetido. Você pode configurar uma porcentagem para avançar e o número máximo de tentativas para o teste. Testes não precisam de intervenção do instrutor para dar as notas. Esse feedback rápido aumenta o aproveitamento dos alunos.

> **Use isso para:** verificações semanais de compreensão, testes de vocabulário,
> relatórios de leitura, qualquer coisa em que a resposta seja mecanicamente
> correta ou errada.

### Tarefa

Um papel ou arquivo que o aluno grava e carrega (PDF, documento, imagem, URL,
ou texto). Os alunos veem um aviso na lição, escrevam ou anexem
resposta e enviem. Em seguida, abra cada Submissão de Tarefa, avalie,
e dê uma nota e observações de feedback.

> **Use isto para:** artigos, trabalhos exegéticos, notas de reflexão,
> projetos — qualquer coisa onde o aluno produz algo que gera um arquivo a ser submetido.

### Exame

Um teste mais elaborado, frequentemente cronometrado, no navegador. Os exames suportam vários tipos
de questões (múltiplas escolhas, abertas, envio de arquivos), limites de tempo,
e por feedback. Partes que podem ser classificadas automaticamente marcam;
porções abertas são sinalizadas como "Não avaliadas" até que você as pontue.

> **Use isto para:** meio-termos, finais, avaliações formais em processo de análise onde
> você quer uma única experiência de teste linear para o aluno.

### Discussão

Tópico de diálogo on-line. Os alunos postam sua posição inicial em um prompt
e respondem aos colegas de classe. As discussões podem ser **avaliadas** (vinculadas a um
Critério da Avaliação) ou **forma livre** (só para engajamento). Discussões
avaliadas requerem que os alunos respondam a um número mínimo de publicações originais de
dos colegas de classe; você definiu isso na Atividade de Discussão como
_"Mínimo de respostas para outros alunos"_. O sistema rastreia a contagem de respostas
de cada aluno e não marcará a discussão completa até que o limite
seja atingido.

> **Use isso para:** conversas semanais em torno das leituras, debates
> de estudos-de-caso, rodadas de feedback dos colegas — em qualquer situação onde a _interação_ é a aprendizagem
> .

### Offline

A solução para todas as coisas que você dá nota fora do LMS. Não há nenhuma submissão
doctype, sem upload, sem página de pontuação. Você apenas abre o Quadro de Notas e digita
a nota para cada aluno.

> **Use isto para:** Participação da capela, participação de classe,
> apresentações presenciais, exames orais, laboratório de pregação, pontuação de avaliação por pares, qualquer coisa
> que viva em seu caderno e você transcreve. Crie uma avaliação
> off-line por categoria para que os pesos ainda sejam somados corretamente.

## Onde a avaliação acontece no dia a dia

### Cartão To-Do (canto superior direito de cada página do Curso)

Todas as páginas de Detalhes do Curso mostram um quadro **To-Do** à direita. Para instrutores
e usuários acadêmicos, ela lista, em texto simples:

- **"Tarefas a avaliar — N"**, **"Exame a avaliar — N"**, etc. — uma linha
  por atividade com submissões não avaliadas, com contagem.
- Cada linha é um atalho clicável diretamente para a fila de notas
  para essa atividade.

Esta é a sua visão de triagem diária. Abra o curso, olhe o quadro,
clique na atividade com o maior atraso. O quadro só mostra coisas
que realmente precisam de atenção — colapsa filas vazias para _"Parabéns!
Sem avaliações para avaliar agora."_

> **O que NÃO está no cartão de To-Do:** Avaliações off-line. Já que não há registro online das submissões, elas não aparecerão aqui. Use o Quadro de Notas para isso.

### A fila de Avaliação (uma atividade de cada vez)

Ao clicar em um item do cartão To-Do, você será levado à página de avaliação daquela tarefa. Lá você vê uma linha por aluno, com seu estado de
envio (não enviado / Não avaliado / corrigido), data de post-original
ou data de upload, e qualquer contagem de resposta para discussões. Clique na linha
de um aluno para abrir seu envio, avalie, dê uma nota, deixe
comentários e salve. Use os botões de navegação para ver outros alunos.

Este é o lugar certo quando você deseja se concentrar em uma única avaliação
e classificá-la em uma única sessão.

### O Quadro de Notas (a grade completa)

O **Quadro de Notas** (vinculado a cada página do Curso) é uma única tabela:

- **Linhas:** todos os alunos do curso.
- **Colunas:** cada Critério da Avaliação, em ordem, com peso
  porcentagem exibida abaixo do título.
- **Células:** nota de cada aluno para essa avaliação.

Três coisas para saber:

1. **Links no cabeçalho** Clique em qualquer título de coluna para ser levado à pagina de avaliação daquela tarefa (a visão por-atividade mencionada). O
   Quadro de Notas é o lançador natural quando você está se movendo pelas avaliações
   e não entre os alunos.
2. **Edite células diretamente.** Você pode digitar uma nota em qualquer célula. Este é **o único lugar para entrar as notas de tarefas offline**— não há nada a clicar aqui. Também
   funciona como uma substituição para os outros tipos se você precisar ajustar uma nota
   depois que a submissão foi salva.
3. **Salve todas as alterações.** As edições são registradas localmente até que você clique no botão
   _Salvar todas as alterações_ no topo (ou pressione `Ctrl+S`). O botão
   mostra a quantidade de células que ainda não foram salvas. Isso processa em lote para que
   você possa fluir através da grade sem salvar a cada célula.

Colunas extra-crédito são azuladas e avisam "Max Extra: N"
sob o título ao invés de um peso, então são fáceis de visualizar.

## Uma semana típica

Um ritmo comum para um instrutor seminário:

1. **Segunda de manhã** — abra o curso. O cartão de destino mostra
   _"Tarefas a avaliar — 8"_. Clique nela, trabalhe através das oito
   submissões, salvando após cada uma.
2. **Meio da semana** — o prazo da discussão passa. O quadro To-Do agora mostra
   _"Discussões para avaliar — 12"_. Abrir a fila, veja a coluna _"Respostas "_
   (formato X / Y quando um mínimo é definido) para que você saiba rapidamente
   quem atingiu o requisito de participação e quem não o fez. Avalie os
   que os atingiram; entre em contato com os que não o fizeram.
3. **Fim da sessão da classe** — abra o **Quadro de notas**, encontre a coluna
   _"Participação de classe"_ (Offline), e digite notas para
   os alunos que participaram bem. Pressione _Salvar todas as alterações_ uma vez.
4. **Final do Período Letivo**— abra o Quadro de Notas para ver a grade completa, verifique se há caselas não avaliadas, especialmente de tarefas offline, e verifique que os totais estão condizentes antes de publicar as notas finais.

## Definindo um plano de avaliação de um curso

Para que tudo isso funcione, você precisa definir os Critérios de Avaliação do Curso. De um Curso Agendado, clique em **Avaliação do Curso** para abrir
da página de configuração. Adicionar uma linha para atividade com nota no conteúdo programático:

- Escolha o **tipo** (Teste / Tarefa / Exame / Discussão / Offline).
- Para tipos não-off-line, vincule a atividade real (Teste específico,
  Tarefa, etc.).
- Defina o **peso** (porcentagem da nota final) — ou marque
  **Crédito extra** e insira os pontos máximos, que serão adicionados na nota final (já ponderada para todas outras atividades).
- Opcionalmente, defina uma **data de vencimento** — usada para a lista do cartão To-Do "Para Em Breve"
  e para marcar os envios atrasados.

O peso total de linhas não-extra-crédito deve ser igual a **100** antes que
possa salvar. No topo da página, existe um total calculado que ficará vermelho até atingir 100%.

## Dicas

- \*\*Não dê notas no Quadro de Notas por padrão. \* Clicando através da fila
  por atividade lhe dá a visualização completa da submissão (o arquivo, a caixa de feedback, comentários prévios). O Quadro de Notas é para
  Notas off-line, substituições e ajustes ao final do curso.
- \*\*Use off-line liberalmente. \* Qualquer coisa que viva em uma área de transferência ou em
  sua cabeça — presença, pontuação do exame oral, total de avaliação por pares,
  Notas de apresentação — se torna uma coluna limpa no Quadro de Notas
  assim que você adicionar um Critério de Avaliação Offline.
- \*\*Uma linha off-line por categoria. \* Uma única coluna _"Participação"_
  combinando presenças, envolvimento oral, e o trabalho em grupo fica bem quando
  o conteúdo programático o descreve dessa forma. Dividi-las em linhas
  separadas também está bem — os alunos veem a falha e você pode pesar
  cada parte.
- **Respostas de discussão contam para "completar".**
  Os controles de configuração de respostas mínimas determina quando a discussão é marcada
  _completa_ na visão do aluno e To-Do. A nota em si é
  tudo o que você inserir na Submissão de Discussão — você pode recompensar
  participação com a pontuação, deduza por estar faltando, ou use uma avaliação Offline separada por
  se você quiser rastrear a participação
  além do conteúdo da discussão.

## Relacionados

- [Atividades de Discussão](discussions.md) — configuração e requisitos de resposta
- [Matrícula](enrollment.md) — quem aparece nas linhas do quadro de notas
- [Cancelamento de Matrícula](withdrawal.md) — como os alunos retirados são representados.
- [Requisitos de Graduação](graduation-requirements.md) — evidências
  fora de cursos que complementa os requisitos de formação
