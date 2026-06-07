import { defineConfig } from 'vitepress'
import { withMermaid } from 'vitepress-plugin-mermaid'
import { readFileSync } from 'fs'
import { resolve, dirname } from 'path'
import { fileURLToPath } from 'url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const initPy = readFileSync(resolve(__dirname, '../../seminary/__init__.py'), 'utf-8')
const appVersion = 'v' + initPy.match(/__version__ = "(.+)"/)[1]

export default withMermaid(defineConfig({
  title: 'SeminaryERP Docs',
  description: 'Documentation for SeminaryERP — a theological seminary management system built on Frappe/ERPNext',

  srcDir: 'en',
  outDir: '.vitepress/dist',

  head: [
    ['link', { rel: 'icon', href: '/klisia_icon.png' }],
  ],

  themeConfig: {
    logo: '/klisia_icon.png',

    socialLinks: [
      { icon: 'github', link: 'https://github.com/klisia-org/seminary' },
    ],

    search: {
      provider: 'local',
    },
  },

  locales: {
    root: {
      label: 'English',
      lang: 'en',
      themeConfig: {
        nav: [
          { text: 'Home', link: '/' },
          { text: 'Getting Started', link: '/getting-started/installation' },
          { text: 'Modules', link: '/modules/enrollment' },
          { text: 'Administration', link: '/administration/user-roles' },
          { text: appVersion, link: 'https://github.com/klisia-org/seminary/releases' },
        ],
        sidebar: [
          {
            text: 'Getting Started',
            collapsed: true,
            items: [
              { text: 'Installation', link: '/getting-started/installation' },
              { text: 'Initial Setup', link: '/getting-started/initial-setup' },
              { text: 'Pricing Strategy', link: '/getting-started/pricing-strategy' },
              { text: 'Legacy Grade Import', link: '/getting-started/legacy-grade-import' },
              { text: 'Your First Term', link: '/getting-started/first-term' },
              { text: 'Translations', link: '/getting-started/translations' },
            ],
          },
          {
            text: 'Modules',
            collapsed: true,
            items: [
              { text: 'Programs', link: '/modules/program' },
              { text: 'Enrollment', link: '/modules/enrollment' },
              { text: 'Withdrawal', link: '/modules/withdrawal' },
              { text: 'Academic Calendar', link: '/modules/academic-calendar' },
              { text: 'Grading', link: '/modules/grading' },
              { text: 'Graduation Requirements', link: '/modules/graduation-requirements' },
              { text: 'Graduation Request', link: '/modules/graduation-request' },
              { text: 'Discussions', link: '/modules/discussions' },
              { text: 'Announcements', link: '/modules/announcements' },
              { text: 'Instructor Payment', link: '/modules/instructor-payment' },
            ],
          },
          {
            text: 'Administration',
            collapsed: true,
            items: [
              { text: 'User Roles', link: '/administration/user-roles' },
              { text: 'Customization', link: '/administration/customization' },
            ],
          },
        ],
        editLink: {
          pattern: 'https://github.com/klisia-org/seminary/edit/develop/docs/en/:path',
          text: 'Edit this page on GitHub',
        },
        footer: {
          message: `Released under the GNU Affero General Public License. | ${appVersion}`,
          copyright: 'Copyright © Klisia / SeminaryERP',
        },
      },
    },

    pt: {
      label: 'Português',
      lang: 'pt',
      themeConfig: {
        nav: [
          { text: 'Início', link: '/pt/' },
          { text: 'Primeiros Passos', link: '/pt/getting-started/installation' },
          { text: 'Módulos', link: '/pt/modules/enrollment' },
          { text: 'Administração', link: '/pt/administration/user-roles' },
          { text: appVersion, link: 'https://github.com/klisia-org/seminary/releases' },
        ],
        sidebar: [
          {
            text: 'Primeiros Passos',
            collapsed: true,
            items: [
              { text: 'Instalação', link: '/pt/getting-started/installation' },
              { text: 'Configuração Inicial', link: '/pt/getting-started/initial-setup' },
              { text: 'Estratégia de Preços', link: '/pt/getting-started/pricing-strategy' },
              { text: 'Importação de Notas Antigas', link: '/pt/getting-started/legacy-grade-import' },
              { text: 'Seu Primeiro Período Letivo', link: '/pt/getting-started/first-term' },
              { text: 'Traduções', link: '/pt/getting-started/translations' },
            ],
          },
          {
            text: 'Módulos',
            collapsed: true,
            items: [
              { text: 'Matrícula', link: '/pt/modules/enrollment' },
              { text: 'Trancamento', link: '/pt/modules/withdrawal' },
              { text: 'Calendário Acadêmico', link: '/pt/modules/academic-calendar' },
              { text: 'Avaliação', link: '/pt/modules/grading' },
              { text: 'Requisitos de Formatura', link: '/pt/modules/graduation-requirements' },
              { text: 'Pedido de Formatura', link: '/pt/modules/graduation-request' },
              { text: 'Discussões', link: '/pt/modules/discussions' },
              { text: 'Avisos', link: '/pt/modules/announcements' },
              { text: 'Pagamento de Professores', link: '/pt/modules/instructor-payment' },
            ],
          },
          {
            text: 'Administração',
            collapsed: true,
            items: [
              { text: 'Funções de Usuário', link: '/pt/administration/user-roles' },
              { text: 'Personalização', link: '/pt/administration/customization' },
            ],
          },
        ],
        editLink: {
          pattern: 'https://github.com/klisia-org/seminary/edit/develop/docs/en/:path',
          text: 'Editar esta página no GitHub',
        },
        footer: {
          message: `Licenciado sob a GNU Affero General Public License. | ${appVersion}`,
          copyright: 'Copyright © Klisia / SeminaryERP',
        },
      },
    },

    es: {
      label: 'Español',
      lang: 'es',
      themeConfig: {
        nav: [
          { text: 'Inicio', link: '/es/' },
          { text: 'Primeros Pasos', link: '/es/getting-started/installation' },
          { text: 'Módulos', link: '/es/modules/enrollment' },
          { text: 'Administración', link: '/es/administration/user-roles' },
          { text: appVersion, link: 'https://github.com/klisia-org/seminary/releases' },
        ],
        sidebar: [
          {
            text: 'Primeros Pasos',
            collapsed: true,
            items: [
              { text: 'Instalación', link: '/es/getting-started/installation' },
              { text: 'Configuración Inicial', link: '/es/getting-started/initial-setup' },
              { text: 'Estrategia de Precios', link: '/es/getting-started/pricing-strategy' },
              { text: 'Importación de Calificaciones Antiguas', link: '/es/getting-started/legacy-grade-import' },
              { text: 'Su Primer Período', link: '/es/getting-started/first-term' },
              { text: 'Traducciones', link: '/es/getting-started/translations' },
            ],
          },
          {
            text: 'Módulos',
            collapsed: true,
            items: [
              { text: 'Inscripción', link: '/es/modules/enrollment' },
              { text: 'Retiro', link: '/es/modules/withdrawal' },
              { text: 'Calendario Académico', link: '/es/modules/academic-calendar' },
              { text: 'Calificaciones', link: '/es/modules/grading' },
              { text: 'Requisitos de Graduación', link: '/es/modules/graduation-requirements' },
              { text: 'Solicitud de Graduación', link: '/es/modules/graduation-request' },
              { text: 'Discusiones', link: '/es/modules/discussions' },
              { text: 'Anuncios', link: '/es/modules/announcements' },
              { text: 'Pago de Profesores', link: '/es/modules/instructor-payment' },
            ],
          },
          {
            text: 'Administración',
            collapsed: true,
            items: [
              { text: 'Roles de Usuario', link: '/es/administration/user-roles' },
              { text: 'Personalización', link: '/es/administration/customization' },
            ],
          },
        ],
        editLink: {
          pattern: 'https://github.com/klisia-org/seminary/edit/develop/docs/en/:path',
          text: 'Editar esta página en GitHub',
        },
        footer: {
          message: `Publicado bajo la Licencia Pública General Affero GNU. | ${appVersion}`,
          copyright: 'Copyright © Klisia / SeminaryERP',
        },
      },
    },
  },
}))
