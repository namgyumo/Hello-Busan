/**
 * home.js — 메인 랜딩 페이지
 */
(async () => {
    const API_BASE = '/api/v1';

    // 행동 로그 수집 초기화
    if (typeof Analytics !== 'undefined') Analytics.init();

    // i18n 초기화 (init이 lang-select 리스너도 등록)
    await I18n.init();

    // 카테고리 수 로드
    loadCategories();

    // 인기 관광지 로드
    loadPopularSpots();

    // 날씨 스마트 배너 로드
    loadWeatherBanner();

    // 언어 변경 시 재로드
    window.addEventListener('langchange', () => {
        if (langSelect) langSelect.value = I18n.getLang();
        loadCategories();
        loadPopularSpots();
        loadWeatherBanner();
    });

    async function loadCategories() {
        try {
            const res = await fetch(`${API_BASE}/spots/categories?lang=${I18n.getLang()}`);
            const json = await res.json();
            if (!json.success || !json.data) return;

            json.data.forEach(cat => {
                const el = document.getElementById(`count-${cat.id}`);
                if (el) {
                    const count = cat.spot_count || 0;
                    el.textContent = `${count}곳`;
                }
            });
        } catch (e) {
            console.warn('카테고리 로드 실패:', e);
        }
    }

    async function loadPopularSpots() {
        const container = document.getElementById('popular-list');
        if (!container) return;

        try {
            const params = new URLSearchParams({
                limit: '6',
                offset: '0',
                lang: I18n.getLang(),
            });
            const res = await fetch(`${API_BASE}/recommend?${params}`);
            const json = await res.json();

            if (!json.success || !json.data || json.data.length === 0) {
                container.innerHTML = '<p class="popular-empty">아직 관광지 데이터를 수집 중입니다</p>';
                return;
            }

            container.innerHTML = '';
            json.data.forEach(spot => {
                const card = document.createElement('a');
                card.className = 'popular-card';
                card.href = `/detail.html?id=${spot.id}`;

                const score = spot.comfort_score;
                const scoreClass = _scoreClass(score);
                const gradeText = _gradeText(score);
                const catLabel = _categoryLabel(spot.category);
                const imgHtml = spot.images && spot.images.length > 0
                    ? `<img src="${spot.images[0]}" alt="${spot.name}" class="popular-card__img" loading="lazy">`
                    : `<div class="popular-card__img-placeholder" data-category="${spot.category || ''}">${_categoryEmoji(spot.category)}</div>`;

                card.innerHTML = `
                    <div class="popular-card__image">
                        ${imgHtml}
                        <div class="popular-card__badge ${scoreClass}">
                            <span class="popular-card__badge-score">${score != null ? score : '--'}</span>
                            <span class="popular-card__badge-grade">${gradeText}</span>
                        </div>
                    </div>
                    <div class="popular-card__body">
                        <span class="popular-card__cat">${catLabel}</span>
                        <h3 class="popular-card__name">${spot.name}</h3>
                        ${spot.address ? `<p class="popular-card__address">${spot.address}</p>` : ''}
                    </div>
                `;
                card.addEventListener('click', () => {
                    if (typeof Analytics !== 'undefined') Analytics.trackSpotClick(spot.id, spot.name);
                });
                container.appendChild(card);
            });
        } catch (e) {
            console.warn('인기 관광지 로드 실패:', e);
            container.innerHTML = '<p class="popular-empty">데이터를 불러올 수 없습니다</p>';
        }
    }

    // ─── 날씨 스마트 배너 ───
    const WEATHER_CONFIG = {
        rain: {
            i18nKey: 'weather_banner_rain',
            icon: '\u{1F327}\u{FE0F}',
            categories: ['culture', 'food', 'shopping'],
            gradient: 'linear-gradient(135deg, #4B6CB7, #182848)',
        },
        clear_hot: {
            i18nKey: 'weather_banner_clear_hot',
            icon: '\u{1F3D6}\u{FE0F}',
            categories: ['nature', 'activity'],
            gradient: 'linear-gradient(135deg, #F2994A, #F2C94C)',
        },
        clear_cool: {
            i18nKey: 'weather_banner_clear_cool',
            icon: '\u{1F343}',
            categories: ['nature', 'nightview'],
            gradient: 'linear-gradient(135deg, #56AB2F, #A8E063)',
        },
        cloudy: {
            i18nKey: 'weather_banner_cloudy',
            icon: '\u{2615}',
            categories: ['food', 'culture'],
            gradient: 'linear-gradient(135deg, #bdc3c7, #6C7A89)',
        },
    };

    async function loadWeatherBanner() {
        const banner = document.getElementById('weather-banner');
        if (!banner) return;

        try {
            const res = await fetch(`${API_BASE}/weather/current`);
            const json = await res.json();
            if (!json.success || !json.data) return;

            const { condition, tmp } = json.data;
            const config = WEATHER_CONFIG[condition] || WEATHER_CONFIG.clear_cool;

            // 아이콘
            const iconEl = document.getElementById('weather-icon');
            if (iconEl) iconEl.textContent = config.icon;

            // 기온
            const tempEl = document.getElementById('weather-temp');
            if (tempEl) tempEl.textContent = `${Math.round(tmp)}\u00B0C`;

            // 메시지 (i18n)
            const msgEl = document.getElementById('weather-message');
            if (msgEl) {
                msgEl.setAttribute('data-i18n', config.i18nKey);
                msgEl.textContent = I18n.t(config.i18nKey);
            }

            // 배너 링크 → 첫 번째 추천 카테고리로 이동
            const linkEl = document.getElementById('weather-banner-link');
            if (linkEl) {
                linkEl.href = `/map.html?category=${config.categories[0]}`;
            }

            // 배경 그라디언트
            banner.style.background = config.gradient;

            // 조건별 클래스 추가 (다크모드 대응)
            banner.className = 'weather-banner weather-banner--' + condition;

            // 표시
            banner.style.display = '';
            requestAnimationFrame(() => {
                banner.classList.add('weather-banner--visible');
            });
        } catch (e) {
            console.warn('날씨 배너 로드 실패:', e);
        }
    }

    function _scoreClass(score) {
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

    function _categoryEmoji(cat) {
        const map = {
            nature: '\u{1F3D4}', culture: '\u{1F3DB}', food: '\u{1F35C}',
            activity: '\u{1F3C4}', shopping: '\u{1F6CD}', nightview: '\u{1F319}',
        };
        return map[cat] || '\u{1F30A}';
    }
})();
