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
