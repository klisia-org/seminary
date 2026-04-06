import { defineConfig } from 'vitepress'

export default defineConfig({
  title: 'SeminaryERP Docs',
  description: 'Documentation for SeminaryERP — a theological seminary management system built on Frappe/ERPNext',

  srcDir: 'en',
  outDir: '.vitepress/dist',

  head: [
    ['link', { rel: 'icon', href: '/assets/klisia_icon.png' }],
  ],

  themeConfig: {
    logo: '/assets/klisia_icon.png',

    nav: [
      { text: 'Home', link: '/' },
      { text: 'Getting Started', link: '/getting-started/installation' },
      { text: 'Modules', link: '/modules/enrollment' },
      { text: 'Administration', link: '/administration/user-roles' },
    ],

    sidebar: [
      {
        text: 'Getting Started',
        collapsed: true,
        items: [
          { text: 'Installation', link: '/getting-started/installation' },
          { text: 'Initial Setup', link: '/getting-started/initial-setup' },
          { text: 'Your First Term', link: '/getting-started/first-term' },
          { text: 'Translations', link: '/getting-started/translations' },
        ],
      },
      {
        text: 'Modules',
        collapsed: true,
        items: [
          { text: 'Enrollment', link: '/modules/enrollment' },
          { text: 'Withdrawal', link: '/modules/withdrawal' },
          { text: 'Academic Calendar', link: '/modules/academic-calendar' },
          { text: 'Grading', link: '/modules/grading' },
          { text: 'Discussions', link: '/modules/discussions' },
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

    socialLinks: [
      { icon: 'github', link: 'https://github.com/klisia-org/seminary' },
    ],

    editLink: {
      pattern: 'https://github.com/klisia-org/seminary/edit/develop/docs/en/:path',
      text: 'Edit this page on GitHub',
    },

    search: {
      provider: 'local',
    },

    footer: {
      message: 'Released under the MIT License.',
      copyright: 'Copyright © Klisia / SeminaryERP',
    },
  },

  locales: {
    root: {
      label: 'English',
      lang: 'en',
    },
    pt: {
      label: 'Portugues',
      lang: 'pt',
    },
    fr: {
      label: 'Francais',
      lang: 'fr',
    },
  },
})
