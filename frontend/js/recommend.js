/**
 * recommend.js — 추천 결과 렌더링
 */
const Recommend = (() => {
    const API_BASE = '/api/v1';
    const PAGE_SIZE = 20;

    async function fetchSpots(lat, lng, categories, offset, search) {
        const params = new URLSearchParams();
        if (lat != null) params.set('lat', lat);
        if (lng != null) params.set('lng', lng);
        if (categories && categories.length) params.set('categories', categories.join(','));
        if (search) params.set('search', search);
        params.set('limit', PAGE_SIZE);
        params.set('offset', offset || 0);
        params.set('lang', I18n.getLang());

        const res = await fetch(`${API_BASE}/recommend?${params}`);
        return res.json();
    }

    function renderList(items, append) {
        const container = document.getElementById('spot-list');
        if (!container) return;

        if (!append) container.innerHTML = '';

        if (!items || items.length === 0) {
            if (!append) {
                container.innerHTML = `<div class="spot-list__empty">
                    <span class="spot-list__empty-icon" aria-hidden="true">&#x1F50D;</span>
                    <span class="spot-list__empty-text">${I18n.t('no_results')}</span>
                </div>`;
            }
            return;
        }

        items.forEach(spot => {
            const card = document.createElement('a');
            card.className = 'spot-card';
            card.href = `/detail.html?id=${encodeURIComponent(spot.id)}`;

            const score = spot.comfort_score;
            const scoreClass = _scoreColorClass(score);
            const gradeText = _gradeText(score);
            const categoryText = _categoryLabel(spot.category);
            const distText = spot.distance_km != null ? `${spot.distance_km}km` : '';
            const safeName = _escapeHtml(spot.name);

            const thumbUrl = spot.thumbnail_url || (spot.images && spot.images.length > 0 ? spot.images[0] : '');
            const thumbHtml = thumbUrl
                ? `<div class="spot-card__thumb"><img src="${_escapeHtml(thumbUrl)}" alt="" loading="lazy"></div>`
                : `<div class="spot-card__thumb"><div class="spot-card__thumb-placeholder">${_categoryEmoji(spot.category)}</div></div>`;

            const isFav = typeof Favorites !== 'undefined' && Favorites.isFavorite(spot.id);
            const favIcon = isFav ? '&#x2764;' : '&#x2661;';
            const favClass = isFav ? ' favorite-btn--active' : '';
            const favLabel = isFav ? (typeof I18n !== 'undefined' ? I18n.t('favorite_remove') : '') : (typeof I18n !== 'undefined' ? I18n.t('favorite_add') : '');

            card.innerHTML = `
                ${thumbHtml}
                <div class="spot-card__score ${scoreClass}">
                    <span class="spot-card__score-num">${score != null ? score : '--'}</span>
                </div>
                <div class="spot-card__body">
                    <div class="spot-card__top">
                        ${categoryText ? `<span class="spot-card__cat">${categoryText}</span>` : ''}
                        ${gradeText ? `<span class="spot-card__grade ${scoreClass}">${gradeText}</span>` : ''}
                    </div>
                    <div class="spot-card__name">${safeName}</div>
                    <div class="spot-card__info">
                        ${distText ? `<span>${distText}</span>` : ''}
                    </div>
                </div>
                <button class="favorite-btn favorite-btn--sm${favClass}" data-spot-id="${_escapeHtml(String(spot.id))}" aria-label="${favLabel}" type="button">
                    <span class="favorite-btn__icon">${favIcon}</span>
                </button>
            `;

            // 관광지 카드 클릭 추적
            card.addEventListener('click', () => {
                if (typeof Analytics !== 'undefined') Analytics.trackSpotClick(spot.id, spot.name);
            });

            const favBtn = card.querySelector('.favorite-btn');
            if (favBtn) {
                favBtn.addEventListener('click', (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    if (typeof Favorites === 'undefined') return;
                    const added = Favorites.toggle(spot.id);
                    const icon = favBtn.querySelector('.favorite-btn__icon');
                    if (added) {
                        favBtn.classList.add('favorite-btn--active');
                        icon.innerHTML = '&#x2764;';
                    } else {
                        favBtn.classList.remove('favorite-btn--active');
                        icon.innerHTML = '&#x2661;';
                    }
                    if (typeof Analytics !== 'undefined') Analytics.trackFavorite(spot.id, added ? 'add' : 'remove');
                    _showToast(I18n.t(added ? 'favorite_added' : 'favorite_removed'));
                });
            }

            container.appendChild(card);
        });
    }

    function showSkeleton() {
        const container = document.getElementById('spot-list');
        if (!container) return;
        container.innerHTML = '';
        for (let i = 0; i < 4; i++) {
            const div = document.createElement('div');
            div.className = 'skeleton skeleton-card';
            container.appendChild(div);
        }
    }

    function _showToast(msg) {
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

    function _gradeText(score) {
        if (score == null) return '';
        if (score >= 80) return I18n.t('comfort_good');
        if (score >= 60) return I18n.t('comfort_normal');
        if (score >= 40) return I18n.t('comfort_crowded');
        return I18n.t('comfort_very_crowded');
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

    function _escapeHtml(str) {
        if (!str) return '';
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    return { fetchSpots, renderList, showSkeleton, PAGE_SIZE };
})();
