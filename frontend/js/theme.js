/**
 * theme.js — Dark mode toggle with localStorage persistence
 */
const Theme = (() => {
    const STORAGE_KEY = 'theme';
    const DARK = 'dark';
    const LIGHT = 'light';

    function init() {
        const saved = localStorage.getItem(STORAGE_KEY);
        const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
        const theme = saved || (prefersDark ? DARK : LIGHT);
        apply(theme);

        // Listen for OS theme changes
        window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
            if (!localStorage.getItem(STORAGE_KEY)) {
                apply(e.matches ? DARK : LIGHT);
            }
        });

        // Bind toggle button
        const btn = document.getElementById('theme-toggle');
        if (btn) {
            btn.addEventListener('click', toggle);
        }
    }

    function toggle() {
        const current = document.documentElement.getAttribute('data-theme');
        const next = current === DARK ? LIGHT : DARK;
        localStorage.setItem(STORAGE_KEY, next);
        apply(next);
    }

    function apply(theme) {
        document.documentElement.setAttribute('data-theme', theme);
        const icon = document.querySelector('.theme-toggle__icon');
        if (icon) {
            icon.textContent = theme === DARK ? '\u{1F319}' : '\u{2600}';
        }
        const btn = document.getElementById('theme-toggle');
        if (btn) {
            btn.setAttribute('aria-label', theme === DARK ? '라이트모드 전환' : '다크모드 전환');
        }
    }

    function getTheme() {
        return document.documentElement.getAttribute('data-theme') || LIGHT;
    }

    // Auto-init
    init();

    return { toggle, getTheme };
})();
