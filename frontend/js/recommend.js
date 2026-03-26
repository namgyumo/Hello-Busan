/**
 * recommend.js — 추천 결과 렌더링
 */
const Recommend = (() => {
    const API_BASE = '/api/v1';
    const PAGE_SIZE = 20;

    async function fetchSpots(lat, lng, categories, offset) {
        const params = new URLSearchParams();
        if (lat) params.set('lat', lat);
        if (lng) params.set('lng', lng);
        if (categories && categories.length) params.set('categories', categories.join(','));
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
                container.innerHTML = '<p class="spot-list__empty">조건에 맞는 관광지가 없습니다</p>';
            }
            return;
        }

        items.forEach(spot => {
            const card = document.createElement('a');
            card.className = 'spot-card';
            card.href = `/detail.html?id=${spot.id}`;

            const score = spot.comfort_score;
            const scoreClass = _scoreColorClass(score);
            const gradeText = _gradeText(score);
            const categoryText = _categoryLabel(spot.category);
            const distText = spot.distance_km != null ? `${spot.distance_km}km` : '';

            card.innerHTML = `
                <div class="spot-card__score ${scoreClass}">
                    <span class="spot-card__score-num">${score != null ? score : '--'}</span>
                </div>
                <div class="spot-card__body">
                    <div class="spot-card__top">
                        ${categoryText ? `<span class="spot-card__cat">${categoryText}</span>` : ''}
                        ${gradeText ? `<span class="spot-card__grade ${scoreClass}">${gradeText}</span>` : ''}
                    </div>
                    <div class="spot-card__name">${spot.name}</div>
                    <div class="spot-card__info">
                        ${distText ? `<span>${distText}</span>` : ''}
                    </div>
                </div>
            `;
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

    function _scoreColorClass(score) {
        if (score == null) return '';
        if (score >= 80) return 'score--good';
        if (score >= 60) return 'score--normal';
        if (score >= 40) return 'score--crowded';
        return 'score--very-crowded';
    }

    function _gradeText(score) {
        if (score == null) return '';
        if (score >= 80) return '쾌적';
        if (score >= 60) return '보통';
        if (score >= 40) return '혼잡';
        return '매우혼잡';
    }

    function _categoryLabel(cat) {
        const map = {
            nature: '자연', culture: '문화', food: '맛집',
            activity: '액티비티', shopping: '쇼핑', nightview: '야경',
        };
        return map[cat] || cat || '';
    }

    return { fetchSpots, renderList, showSkeleton, PAGE_SIZE };
})();
