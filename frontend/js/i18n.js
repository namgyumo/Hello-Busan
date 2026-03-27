/**
 * i18n.js — 다국어 처리
 */
const I18n = (() => {
    const SUPPORTED = ['ko', 'en', 'ja', 'zh', 'ru'];
    const DEFAULT = 'ko';
    let currentLang = DEFAULT;
    let translations = {};

    function detectLanguage() {
        const nav = (navigator.language || '').slice(0, 2);
        return SUPPORTED.includes(nav) ? nav : DEFAULT;
    }

    async function load(lang) {
        if (!SUPPORTED.includes(lang)) lang = DEFAULT;
        try {
            const res = await fetch(`/locales/${lang}.json`);
            if (res.ok) {
                translations = await res.json();
                currentLang = lang;
                apply();
            }
        } catch (e) {
            console.warn('i18n load failed:', e);
        }
    }

    function t(key) {
        return translations[key] || key;
    }

    // Whitelist of safe inline HTML tags allowed in translations
    const SAFE_TAG_RE = /<(br|strong|em|b|i|u|span)\b[^>]*\/?>/i;

    /**
     * Sanitize translation value: strip all tags except whitelisted ones.
     * Prevents XSS when using innerHTML for translations containing safe tags.
     */
    function _sanitizeI18nVal(val) {
        return val.replace(/<\/?([a-zA-Z][a-zA-Z0-9]*)\b[^>]*\/?>/gi, (match, tag) => {
            const allowed = ['br', 'strong', 'em', 'b', 'i', 'u', 'span'];
            return allowed.includes(tag.toLowerCase()) ? match : '';
        });
    }

    function apply() {
        document.querySelectorAll('[data-i18n]').forEach(el => {
            const key = el.getAttribute('data-i18n');
            if (!translations[key]) return;
            const val = translations[key];
            // Use innerHTML for values with safe inline tags, with sanitization
            if (SAFE_TAG_RE.test(val)) {
                el.innerHTML = _sanitizeI18nVal(val);
            } else {
                el.textContent = val;
            }
        });
        document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
            const key = el.getAttribute('data-i18n-placeholder');
            if (translations[key]) el.placeholder = translations[key];
        });
        document.documentElement.lang = currentLang;
    }

    function getLang() { return currentLang; }

    async function setLang(lang) {
        if (!SUPPORTED.includes(lang)) lang = DEFAULT;
        localStorage.setItem('lang', lang);
        await load(lang);
        window.dispatchEvent(new CustomEvent('langchange', { detail: { lang } }));
    }

    async function init() {
        const saved = localStorage.getItem('lang');
        const lang = saved || detectLanguage();
        await load(lang);

        const select = document.getElementById('lang-select');
        if (select) {
            select.value = currentLang;
            select.addEventListener('change', async (e) => {
                await setLang(e.target.value);
            });
        }
    }

    return { init, t, getLang, setLang, load };
})();
