/**
 * favorites.js — 즐겨찾기/북마크 관리 (localStorage)
 */
const Favorites = (() => {
    const STORAGE_KEY = 'hello_busan_favorites';

    function _load() {
        try {
            const raw = localStorage.getItem(STORAGE_KEY);
            return raw ? JSON.parse(raw) : [];
        } catch (e) {
            console.warn('즐겨찾기 로드 실패:', e);
            return [];
        }
    }

    function _save(ids) {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(ids));
    }

    function add(spotId) {
        const ids = _load();
        if (!ids.includes(spotId)) {
            ids.push(spotId);
            _save(ids);
        }
        window.dispatchEvent(new CustomEvent('favorites-changed', { detail: { spotId, action: 'add' } }));
    }

    function remove(spotId) {
        let ids = _load();
        ids = ids.filter(id => id !== spotId);
        _save(ids);
        window.dispatchEvent(new CustomEvent('favorites-changed', { detail: { spotId, action: 'remove' } }));
    }

    function toggle(spotId) {
        if (isFavorite(spotId)) {
            remove(spotId);
            return false;
        } else {
            add(spotId);
            return true;
        }
    }

    function isFavorite(spotId) {
        return _load().includes(spotId);
    }

    function getAll() {
        return _load();
    }

    return { add, remove, toggle, isFavorite, getAll };
})();
