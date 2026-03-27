/**
 * favorites-page.js — 저장한 관광지 페이지 로직
 */
(async () => {
    const API_BASE = '/api/v1';

    await I18n.init();
    loadFavorites();

    window.addEventListener('langchange', () => {
        loadFavorites();
    });

    window.addEventListener('favorites-changed', () => {
        loadFavorites();
    });

    async function loadFavorites() {
        const container = document.getElementById('favorites-list');
        if (!container) return;

        const ids = Favorites.getAll();

        if (ids.length === 0) {
            container.innerHTML = `<div class="favorites-empty">
                <span class="favorites-empty__icon" aria-hidden="true">&#x2764;</span>
                <span class="favorites-empty__text">${I18n.t('no_favorites')}</span>
            </div>`;
            return;
        }

        try {
            // Fetch all favorited spots in parallel
            const results = await Promise.allSettled(
                ids.map(id =>
                    fetch(`${API_BASE}/spots/${encodeURIComponent(id)}?lang=${I18n.getLang()}`)
                        .then(res => res.json())
                        .then(json => (json.success && json.data) ? json.data : null)
                )
            );
            const spots = results
                .filter(r => r.status === 'fulfilled' && r.value !== null)
                .map(r => r.value);
            const json = { success: spots.length > 0, data: spots };

            if (!json.success || !json.data) {
                renderFromIds(container, ids);
                return;
            }

            container.innerHTML = '';
            json.data.forEach(spot => {
                container.appendChild(createSpotCard(spot));
            });

            if (container.children.length === 0) {
                renderFromIds(container, ids);
            }
        } catch (e) {
            console.warn('즐겨찾기 로드 실패:', e);
            renderFromIds(container, ids);
        }
    }

    function renderFromIds(container, ids) {
        container.innerHTML = '';
        ids.forEach(id => {
            const card = document.createElement('a');
            card.className = 'spot-card';
            card.href = `/detail.html?id=${id}`;
            card.innerHTML = `
                <div class="spot-card__thumb"><div class="spot-card__thumb-placeholder">&#x1F30A;</div></div>
                <div class="spot-card__body">
                    <div class="spot-card__name">ID: ${id}</div>
                </div>
                <button class="favorite-btn favorite-btn--active" data-spot-id="${id}" aria-label="${I18n.t('favorite_remove')}" type="button">
                    <span class="favorite-btn__icon">&#x2764;</span>
                </button>
            `;
            card.querySelector('.favorite-btn').addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                handleToggle(id);
            });
            container.appendChild(card);
        });
    }

    function _escapeHtml(str) {
        if (!str) return '';
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    function createSpotCard(spot) {
        const card = document.createElement('a');
        card.className = 'spot-card';
        card.href = `/detail.html?id=${encodeURIComponent(spot.id)}`;

        const score = spot.comfort_score != null ? spot.comfort_score : (spot.comfort ? spot.comfort.score : null);
        const scoreClass = _scoreColorClass(score);
        const categoryText = _categoryLabel(spot.category);
        const safeName = _escapeHtml(spot.name);

        const thumbUrl = spot.thumbnail_url || (spot.images && spot.images.length > 0 ? spot.images[0] : '');
        const thumbHtml = thumbUrl
            ? `<div class="spot-card__thumb"><img src="${_escapeHtml(thumbUrl)}" alt="" loading="lazy"></div>`
            : `<div class="spot-card__thumb"><div class="spot-card__thumb-placeholder">${_categoryEmoji(spot.category)}</div></div>`;

        card.innerHTML = `
            ${thumbHtml}
            <div class="spot-card__score ${scoreClass}">
                <span class="spot-card__score-num">${score != null ? score : '--'}</span>
            </div>
            <div class="spot-card__body">
                <div class="spot-card__top">
                    ${categoryText ? `<span class="spot-card__cat">${categoryText}</span>` : ''}
                </div>
                <div class="spot-card__name">${safeName}</div>
            </div>
            <button class="favorite-btn favorite-btn--active" data-spot-id="${_escapeHtml(String(spot.id))}" aria-label="${I18n.t('favorite_remove')}" type="button">
                <span class="favorite-btn__icon">&#x2764;</span>
            </button>
        `;

        card.querySelector('.favorite-btn').addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            handleToggle(spot.id);
        });

        return card;
    }

    function handleToggle(spotId) {
        const added = Favorites.toggle(spotId);
        showToast(I18n.t(added ? 'favorite_added' : 'favorite_removed'));
    }

    function showToast(msg) {
        const el = document.getElementById('toast');
        if (!el) return;
        el.textContent = msg;
        el.classList.add('show');
        setTimeout(() => el.classList.remove('show'), 3000);
    }

    function _scoreColorClass(score) {
        if (score == null) return '';
        if (score >= 80) return 'score--good';
        if (score >= 60) return 'score--normal';
        if (score >= 40) return 'score--crowded';
        return 'score--very-crowded';
    }

    function _categoryLabel(cat) {
        const keyMap = {
            nature: 'category_nature', culture: 'category_culture', food: 'category_food',
            activity: 'category_activity', shopping: 'category_shopping', nightview: 'category_nightview',
        };
        return keyMap[cat] ? I18n.t(keyMap[cat]) : (cat || '');
    }

    function _categoryEmoji(cat) {
        const map = {
            nature: '\u{1F3D4}', culture: '\u{1F3DB}', food: '\u{1F35C}',
            activity: '\u{1F3C4}', shopping: '\u{1F6CD}', nightview: '\u{1F319}',
        };
        return map[cat] || '\u{1F30A}';
    }
})();
