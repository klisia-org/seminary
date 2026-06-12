# Papéis de usuário

O SeminaryERP usa o sistema de permissões baseado em papéis do Frappe para controlar o acesso. O módulo
define e possui os seguintes papéis. Um usuário pode ter mais do que um papel.

## Papéis da equipe (Desk)

- **Gerente de seminários** — administrador do módulo. Acesso completo aos doctipos de configuração acadêmicos
  incluindo ações de fluxo de trabalho.
- **Secretaria de Alunos**— todos os arquivos de alunos: admissões, matrículas, períodos letivos, cancelamento de matrículas, graduação e relatório de notas, e notas disciplinares.
- **Diretores de Programa** — programas e autoridade do currículo: programas, cursos,
  avaliações, avaliação e política acadêmica. (Esta função foi anteriormente nomeada de
  _Usuário Acadêmico_.)
- **Instrutor** — ensina e classifica seus próprios cursos e pode reportar
  incidentes disciplinares.

## Papéis de portal (frontend)

- **Aluno**— matrícula em cursos, submete tarefas, e vê seus próprios arquivos e currículo.
- **Alumni** — alunos formados; acesso ao portal de antigos alunos e seus próprios registros
  .
- **Inscrição de aluno** — futuros alunos completando o aplicativo
  formulário web.

## Acesso: Portal vs Desk

Alunos, antigos alunos e candidatos usam o portal LMS (frontend) e não têm acesso ao Desk;
são redirecionados para o portal ao acessar. Funcionários trabalham no Desk Frappe
para configuração, registros e relatórios.

## Notas

- `Diretor de Programas` e `Gerente de Seminário` são criados pelo aplicativo ao instalar — sem dependência
  externa.
- `Gerenciador do Sistema` (Núcleo da Frappe) retém o acesso de superadministrador em todos os lugares.
