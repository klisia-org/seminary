import { Code } from "lucide-vue-next"
import { h, createApp } from "vue"
import hljs from 'highlight.js/lib/core';
import { sanitize } from './sanitize.js';


const DEFAULT_THEMES = ['light', 'dark'];
const COMMON_LANGUAGES = {
	none: 'Auto-detect', apache: 'Apache', bash: 'Bash', cs: 'C#', cpp: 'C++', css: 'CSS', coffeescript: 'CoffeeScript', diff: 'Diff',
	go: 'Go', html: 'HTML, XML', http: 'HTTP', json: 'JSON', java: 'Java', javascript: 'JavaScript', kotlin: 'Kotlin',
	less: 'Less', lua: 'Lua', makefile: 'Makefile', markdown: 'Markdown', nginx: 'Nginx', objectivec: 'Objective-C',
	php: 'PHP', perl: 'Perl', properties: 'Properties', python: 'Python', ruby: 'Ruby', rust: 'Rust', scss: 'SCSS',
	sql: 'SQL', shell: 'Shell Session', swift: 'Swift', toml: 'TOML, also INI', typescript: 'TypeScript', yaml: 'YAML',
	plaintext: 'Plaintext'
};

export class CodeBox {
	api: any;
	config: { themeName: any; themeURL: any; useDefaultTheme: any; };
	readOnly: boolean;
	data: { code: any; language: any; theme: any; };
	highlightScriptID: string;
	highlightCSSID: string;
	codeArea: HTMLDivElement;
	selectInput: HTMLInputElement;
	selectDropIcon: HTMLElement;

	constructor({ data, api, config, readOnly }) {
		this.api = api;
		this.readOnly = readOnly;
		this.config = {
			themeName: config.themeName && typeof config.themeName === 'string' ? config.themeName : '',
			themeURL: config.themeURL && typeof config.themeURL === 'string' ? config.themeURL : '',
			useDefaultTheme: (config.useDefaultTheme && typeof config.useDefaultTheme === 'string'
				&& DEFAULT_THEMES.includes(config.useDefaultTheme.toLowerCase())) ? config.useDefaultTheme : 'dark',
		};
		this.data = {
			code: data.code && typeof data.code === 'string' ? data.code : '',
			language: data.language && typeof data.language === 'string' ? data.language : 'Auto-detect',
			theme: data.theme && typeof data.theme === 'string' ? data.theme : this._getThemeURLFromConfig(),
		};
		this.highlightScriptID = 'highlightJSScriptElement';
		this.highlightCSSID = 'highlightJSCSSElement';
		this.codeArea = document.createElement('div');
		this.selectInput = document.createElement('input');
		this.selectDropIcon = document.createElement('i');

		this._injectHighlightJSCSSElement();

		this.api.listeners.on(window, 'click', this._closeAllLanguageSelects, true);
	}

	static get isReadOnlySupported() {
		return true
	}

	static get sanitize() {
		return {
			code: true,
			language: false,
			theme: false,
		}
	}

	static get toolbox() {
		const app = createApp({
			render: () => h(Code, { size: 18, strokeWidth: 1.5, color: 'black' }),
		});

		const div = document.createElement('div');
		app.mount(div);

		return {
			title: 'CodeBox',
			icon: div.innerHTML
		};
	}

	static get displayInToolbox() {
		return true;
	}

	static get enableLineBreaks() {
		return true;
	}

	render() {
		const codeAreaHolder = document.createElement('pre');
		const languageSelect = this._createLanguageSelectElement();

		codeAreaHolder.setAttribute('class', 'codeBoxHolder');
		this.codeArea.setAttribute('class', `codeBoxTextArea ${this.config.useDefaultTheme} ${this.data.language}`);
		this.codeArea.setAttribute('contenteditable', 'true');
		// data.code is stored WITH highlight.js markup (save() reads innerHTML), so it
		// cannot be set as text; the 'code' profile keeps span[class], br and div only.
		this.codeArea.innerHTML = sanitize(this.data.code, 'code');
		this.api.listeners.on(this.codeArea, 'blur', event => this._highlightCodeArea(event), false);
		this.api.listeners.on(this.codeArea, 'paste', event => this._handleCodeAreaPaste(event), false);

		codeAreaHolder.appendChild(this.codeArea);
		!this.readOnly && codeAreaHolder.appendChild(languageSelect);

		return codeAreaHolder;
	}

	save(blockContent) {
		return Object.assign(this.data, { code: this.codeArea.innerHTML, theme: this._getThemeURLFromConfig() });
	}

	validate(savedData) {
		if (!savedData.code.trim()) return false;
		return true;
	}

	destroy() {
		this.api.listeners.off(window, 'click', this._closeAllLanguageSelects, true);
		this.api.listeners.off(this.codeArea, 'blur', event => this._highlightCodeArea(event), false);
		this.api.listeners.off(this.codeArea, 'paste', event => this._handleCodeAreaPaste(event), false);
		this.api.listeners.off(this.selectInput, 'click', event => this._handleSelectInputClick(event), false);
	}

	_createLanguageSelectElement() {
		const selectHolder = document.createElement('div');
		const selectPreview = document.createElement('div');
		const languages = Object.entries(COMMON_LANGUAGES);

		selectHolder.setAttribute('class', 'codeBoxSelectDiv');

		this.selectDropIcon.setAttribute('class', `codeBoxSelectDropIcon ${this.config.useDefaultTheme}`);
		this.selectDropIcon.innerHTML = '&#8595;';
		this.selectInput.setAttribute('class', `codeBoxSelectInput ${this.config.useDefaultTheme}`);
		this.selectInput.setAttribute('type', 'text');
		this.selectInput.setAttribute('readonly', 'true');
		this.selectInput.value = this.data.language;
		this.api.listeners.on(this.selectInput, 'click', event => this._handleSelectInputClick(event), false);

		selectPreview.setAttribute('class', 'codeBoxSelectPreview');

		languages.forEach(language => {
			const selectItem = document.createElement('p');
			selectItem.setAttribute('class', `codeBoxSelectItem ${this.config.useDefaultTheme}`);
			selectItem.setAttribute('data-key', language[0]);
			selectItem.textContent = language[1];
			this.api.listeners.on(selectItem, 'click', event => this._handleSelectItemClick(event, language), false);

			selectPreview.appendChild(selectItem);
		});

		selectHolder.appendChild(this.selectDropIcon);
		selectHolder.appendChild(this.selectInput);
		selectHolder.appendChild(selectPreview);

		return selectHolder;
	}

	_highlightCodeArea(event) {
		hljs.highlightBlock(this.codeArea);
	}

	_handleCodeAreaPaste(event) {
		event.stopPropagation();
	}

	_handleSelectInputClick(event) {
		event.target.nextSibling.classList.toggle('codeBoxShow');
	}

	_handleSelectItemClick(event, language) {
		event.target.parentNode.parentNode.querySelector('.codeBoxSelectInput').value = language[1];
		event.target.parentNode.classList.remove('codeBoxShow');
		this.codeArea.removeAttribute('class');
		this.data.language = language[0];
		this.codeArea.setAttribute('class', `codeBoxTextArea ${this.config.useDefaultTheme} ${this.data.language}`);

		hljs.highlightElement(this.codeArea);
	}

	_closeAllLanguageSelects() {
		const selectPreviews = document.querySelectorAll('.codeBoxSelectPreview');
		for (let i = 0, len = selectPreviews.length; i < len; i++) selectPreviews[i].classList.remove('codeBoxShow');
	}

	_injectHighlightJSCSSElement() {
		const highlightJSCSSElement = document.querySelector(`#${this.highlightCSSID}`);
		let highlightJSCSSURL = this._getThemeURLFromConfig();
		// No URL means the theme is bundled with the app (the default since
		// p010 H12). Injecting a <link href="null"> would fetch the SPA's own
		// index.html as a stylesheet.
		if (!highlightJSCSSURL) return;
		if (!highlightJSCSSElement) {
			const link = document.createElement('link');
			const head = document.querySelector('head');
			link.setAttribute('rel', 'stylesheet');
			link.setAttribute('href', highlightJSCSSURL);
			link.setAttribute('id', this.highlightCSSID);

			if (head) head.appendChild(link);
		}
		else highlightJSCSSElement.setAttribute('href', highlightJSCSSURL);
	}

	_getThemeURLFromConfig() {
		// Only an explicitly configured URL. The two jsDelivr fallbacks that
		// used to live here loaded a stylesheet from a **mutable GitHub tag
		// ref** (`cdn-release@9.18.1`), with no SRI, on every student lesson
		// view -- `getEditorTools` is called from the viewer, not just the
		// editor (p005a A03-3, verified still true in the deployed bundle on
		// the canary). CSS injection in an authenticated session needs no
		// script execution to do damage.
		//
		// They also pinned **9.18.1** while the app imports `highlight.js`
		// 11.11.x, so the markup being highlighted and the theme colouring it
		// were two major versions apart. `utils/index.js` now imports the
		// theme from that same package, so vite bundles it and the versions
		// cannot drift again (p010 H12).
		return this.config.themeURL || null;
	}
}


export default CodeBox;