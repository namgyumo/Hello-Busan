/**
 * offline-store.js — IndexedDB storage for offline access to favorited spots
 */
const OfflineStore = (() => {
    const DB_NAME = 'hello_busan_offline';
    const DB_VERSION = 1;
    const STORE_NAME = 'spots';

    let dbPromise = null;

    function _openDB() {
        if (dbPromise) return dbPromise;
        dbPromise = new Promise((resolve, reject) => {
            const request = indexedDB.open(DB_NAME, DB_VERSION);
            request.onupgradeneeded = (event) => {
                const db = event.target.result;
                if (!db.objectStoreNames.contains(STORE_NAME)) {
                    db.createObjectStore(STORE_NAME, { keyPath: 'id' });
                }
            };
            request.onsuccess = () => resolve(request.result);
            request.onerror = () => reject(request.error);
        });
        return dbPromise;
    }

    async function saveSpot(spotData) {
        if (!spotData || !spotData.id) return;
        try {
            const db = await _openDB();
            const tx = db.transaction(STORE_NAME, 'readwrite');
            const store = tx.objectStore(STORE_NAME);
            store.put({
                ...spotData,
                _cachedAt: Date.now(),
            });
            return new Promise((resolve, reject) => {
                tx.oncomplete = resolve;
                tx.onerror = () => reject(tx.error);
            });
        } catch (e) {
            console.warn('OfflineStore: saveSpot failed', e);
        }
    }

    async function getSpot(spotId) {
        try {
            const db = await _openDB();
            const tx = db.transaction(STORE_NAME, 'readonly');
            const store = tx.objectStore(STORE_NAME);
            const request = store.get(spotId);
            return new Promise((resolve, reject) => {
                request.onsuccess = () => resolve(request.result || null);
                request.onerror = () => reject(request.error);
            });
        } catch (e) {
            console.warn('OfflineStore: getSpot failed', e);
            return null;
        }
    }

    async function removeSpot(spotId) {
        try {
            const db = await _openDB();
            const tx = db.transaction(STORE_NAME, 'readwrite');
            const store = tx.objectStore(STORE_NAME);
            store.delete(spotId);
            return new Promise((resolve, reject) => {
                tx.oncomplete = resolve;
                tx.onerror = () => reject(tx.error);
            });
        } catch (e) {
            console.warn('OfflineStore: removeSpot failed', e);
        }
    }

    async function getAllSpots() {
        try {
            const db = await _openDB();
            const tx = db.transaction(STORE_NAME, 'readonly');
            const store = tx.objectStore(STORE_NAME);
            const request = store.getAll();
            return new Promise((resolve, reject) => {
                request.onsuccess = () => resolve(request.result || []);
                request.onerror = () => reject(request.error);
            });
        } catch (e) {
            console.warn('OfflineStore: getAllSpots failed', e);
            return [];
        }
    }

    async function cacheSpotForFavorite(spotId, lang) {
        try {
            const res = await fetch(`/api/v1/spots/${spotId}?lang=${lang || 'ko'}`);
            const json = await res.json();
            if (json.success && json.data) {
                await saveSpot(json.data);
            }
        } catch (e) {
            console.warn('OfflineStore: cacheSpotForFavorite failed', e);
        }
    }

    function initFavoritesSync() {
        window.addEventListener('favorites-changed', async (e) => {
            const { spotId, action } = e.detail || {};
            if (!spotId) return;
            const lang = (typeof I18n !== 'undefined') ? I18n.getLang() : 'ko';
            if (action === 'add') {
                await cacheSpotForFavorite(spotId, lang);
            } else if (action === 'remove') {
                await removeSpot(spotId);
            }
        });
    }

    return { saveSpot, getSpot, removeSpot, getAllSpots, cacheSpotForFavorite, initFavoritesSync };
})();
