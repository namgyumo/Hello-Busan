/**
 * search.js — 검색 입력 디바운스 처리
 */
const Search = (() => {
    let timer = null;
    let onChange = null;
    let currentQuery = '';

    function init(callback) {
        onChange = callback;

        const input = document.getElementById('search-input');
        const clearBtn = document.getElementById('search-clear');
        if (!input) return;

        // Visual feedback: highlight search bar while typing
        input.addEventListener('focus', () => {
            const bar = document.getElementById('search-bar');
            if (bar) bar.classList.add('search-bar--focused');
        });
        input.addEventListener('blur', () => {
            const bar = document.getElementById('search-bar');
            if (bar) bar.classList.remove('search-bar--focused');
        });

        input.addEventListener('input', () => {
            const value = input.value.trim();
            currentQuery = value;

            if (clearBtn) {
                clearBtn.style.display = value ? '' : 'none';
            }

            if (timer) clearTimeout(timer);
            timer = setTimeout(() => {
                if (value && typeof Analytics !== 'undefined') {
                    Analytics.trackSearch(value);
                }
                if (onChange) onChange(value);
            }, 300);
        });

        // Enter key: immediately trigger search (skip debounce)
        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                const value = input.value.trim();
                currentQuery = value;
                if (timer) clearTimeout(timer);
                if (value && typeof Analytics !== 'undefined') {
                    Analytics.trackSearch(value);
                }
                if (onChange) onChange(value);
            }
        });

        if (clearBtn) {
            clearBtn.addEventListener('click', () => {
                input.value = '';
                currentQuery = '';
                clearBtn.style.display = 'none';
                input.focus();
                if (timer) clearTimeout(timer);
                if (onChange) onChange('');
            });
        }
    }

    function getQuery() {
        return currentQuery;
    }

    return { init, getQuery };
})();
