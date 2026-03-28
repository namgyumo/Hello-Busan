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

    // 날씨 스마트 추천 로드
    loadSmartRecommend();

    // 7일 예보 로드
    loadWeeklyForecast();

    // 대기질 정보 로드
    loadAirQuality();

    // 이번 주 축제 로드
    loadThisWeekFestivals();

    // 계절 테마 추천 로드
    loadSeasonThemes();

    // 히어로 배너 슬라이드 초기화
    initHeroSlider();

    // 언어 변경 시 재로드
    window.addEventListener('langchange', () => {
        const langSelect = document.getElementById('lang-select');
        if (langSelect) langSelect.value = I18n.getLang();
        loadCategories();
        loadPopularSpots();
        loadWeatherBanner();
        loadSmartRecommend();
        loadWeeklyForecast();
        loadAirQuality();
        loadThisWeekFestivals();
        loadSeasonThemes();
        _applySliderAltTexts();
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
                    el.textContent = `${count}${I18n.t('unit_places')}`;
                }
            });
        } catch (e) {
            console.warn('카테고리 로드 실패:', e);
        }
    }

    function _escapeHtml(str) {
        if (!str) return '';
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    async function loadPopularSpots() {
        const container = document.getElementById('popular-list');
        if (!container) return;

        try {
            const params = new URLSearchParams({
                limit: '6',
                offset: '0',
                lang: I18n.getLang(),
                diverse: 'true',
            });
            const res = await fetch(`${API_BASE}/recommend?${params}`);
            const json = await res.json();

            if (!json.success || !json.data || json.data.length === 0) {
                container.innerHTML = `<p class="popular-empty">${I18n.t('popular_empty')}</p>`;
                return;
            }

            container.innerHTML = '';
            json.data.forEach(spot => {
                const card = document.createElement('a');
                card.className = 'popular-card';
                card.href = `/detail.html?id=${encodeURIComponent(spot.id)}`;

                const score = spot.comfort_score;
                const scoreClass = _scoreClass(score);
                const gradeText = _gradeText(score);
                const catLabel = _categoryLabel(spot.category);
                const safeName = _escapeHtml(spot.name);
                const safeAddress = _escapeHtml(spot.address || '');
                const thumbUrl = spot.thumbnail_url || (spot.images && spot.images.length > 0 ? spot.images[0] : '');
                const imgHtml = thumbUrl
                    ? `<img src="${_escapeHtml(thumbUrl)}" alt="${safeName}" class="popular-card__img" loading="lazy">`
                    : `<div class="popular-card__img-placeholder" data-category="${_escapeHtml(spot.category)}">${_categoryEmoji(spot.category)}</div>`;

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
                        <h3 class="popular-card__name">${safeName}</h3>
                        ${safeAddress ? `<p class="popular-card__address">${safeAddress}</p>` : ''}
                    </div>
                `;
                card.addEventListener('click', () => {
                    if (typeof Analytics !== 'undefined') Analytics.trackSpotClick(spot.id, spot.name);
                });
                container.appendChild(card);
            });
        } catch (e) {
            console.warn('인기 관광지 로드 실패:', e);
            container.innerHTML = `<p class="popular-empty">${I18n.t('popular_load_failed')}</p>`;
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

            // 배너 링크 → 날씨 전용 페이지로 이동
            const linkEl = document.getElementById('weather-banner-link');
            if (linkEl) {
                linkEl.href = '/weather.html';
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

    // ─── 날씨 스마트 추천 ───

    const SMART_REC_ICONS = {
        rain: '\u{1F327}\u{FE0F}',
        clear_hot: '\u{2600}\u{FE0F}',
        clear_cool: '\u{1F31E}',
        cloudy: '\u{2601}\u{FE0F}',
        cold: '\u{2744}\u{FE0F}',
    };

    async function loadSmartRecommend() {
        const section = document.getElementById('smart-recommend-section');
        if (!section) return;

        try {
            const res = await fetch(`${API_BASE}/weather/smart-recommend?limit=5&lang=${I18n.getLang()}`);
            const json = await res.json();
            if (!json.success || !json.data || !json.data.recommendations || json.data.recommendations.length === 0) return;

            const d = json.data;
            const condition = d.weather_condition || 'clear_cool';

            // 섹션에 condition 클래스 적용
            section.className = 'smart-recommend smart-recommend--' + condition;

            // 아이콘
            const iconEl = document.getElementById('smart-rec-icon');
            if (iconEl) iconEl.textContent = SMART_REC_ICONS[condition] || '\u{1F31E}';

            // 메시지
            const msgEl = document.getElementById('smart-rec-message');
            if (msgEl) msgEl.textContent = d.message || '';

            // 온도
            const tempEl = document.getElementById('smart-rec-temp');
            if (tempEl) tempEl.textContent = `${Math.round(d.temperature)}\u00B0C \u00B7 ${d.sky_text || ''}`;

            // 카드 렌더링
            const listEl = document.getElementById('smart-rec-list');
            if (!listEl) return;

            listEl.innerHTML = '';
            d.recommendations.forEach(function(spot) {
                const card = document.createElement('a');
                card.className = 'smart-recommend-card';
                card.href = '/detail.html?id=' + encodeURIComponent(spot.id);

                const safeName = _escapeHtml(spot.name);
                const catLabel = _categoryLabel(spot.category);
                const reason = _escapeHtml(spot.reason || '');
                const thumbUrl = spot.thumbnail_url || '';

                const imgHtml = thumbUrl
                    ? '<img src="' + _escapeHtml(thumbUrl) + '" alt="' + safeName + '" class="smart-recommend-card__img" loading="lazy">'
                    : '<div class="smart-recommend-card__img-placeholder">' + _categoryEmoji(spot.category) + '</div>';

                card.innerHTML =
                    '<div class="smart-recommend-card__img-wrap">' +
                        imgHtml +
                        '<span class="smart-recommend-card__condition smart-recommend-card__condition--' + condition + '">' +
                            (SMART_REC_ICONS[condition] || '') + ' ' + _escapeHtml(d.sky_text || '') +
                        '</span>' +
                    '</div>' +
                    '<div class="smart-recommend-card__body">' +
                        '<span class="smart-recommend-card__cat">' + _escapeHtml(catLabel) + '</span>' +
                        '<h3 class="smart-recommend-card__name">' + safeName + '</h3>' +
                        (reason ? '<p class="smart-recommend-card__reason">' + reason + '</p>' : '') +
                    '</div>';

                card.addEventListener('click', function() {
                    if (typeof Analytics !== 'undefined') Analytics.trackSpotClick(spot.id, spot.name);
                });

                listEl.appendChild(card);
            });

            // 표시
            section.style.display = '';
        } catch (e) {
            console.warn('스마트 추천 로드 실패:', e);
        }
    }

    // ─── 대기질 정보 ───
    const AQ_GRADE_CONFIG = {
        1: { key: 'aq_good',     css: 'good',     icon: '\u{1F7E2}' },
        2: { key: 'aq_moderate', css: 'moderate', icon: '\u{1F7E1}' },
        3: { key: 'aq_bad',      css: 'bad',      icon: '\u{1F7E0}' },
        4: { key: 'aq_very_bad', css: 'very_bad', icon: '\u{1F534}' },
    };

    async function loadAirQuality() {
        var section = document.getElementById('air-quality-section');
        if (!section) return;

        try {
            var res = await fetch(API_BASE + '/air-quality');
            var json = await res.json();
            if (!json.success || !json.data || !json.data.summary) return;

            var summary = json.data.summary;
            var grade = summary.overall_grade;
            var config = AQ_GRADE_CONFIG[grade] || AQ_GRADE_CONFIG[2];

            // Icon
            var iconEl = document.getElementById('aq-icon');
            if (iconEl) iconEl.textContent = config.icon;

            // Grade bar
            var gradeBar = document.getElementById('aq-grade-bar');
            if (gradeBar) {
                gradeBar.className = 'air-quality__grade-bar air-quality__grade-bar--' + config.css;
                var gradeLabel = document.getElementById('aq-grade-label');
                if (gradeLabel) {
                    gradeLabel.textContent = I18n.t(config.key);
                }
            }

            // Metrics
            var pm25El = document.getElementById('aq-pm25');
            if (pm25El) {
                pm25El.textContent = summary.avg_pm25 != null
                    ? _escapeHtml(String(summary.avg_pm25)) + ' ' + I18n.t('aq_unit_ugm3')
                    : '--';
            }

            var pm10El = document.getElementById('aq-pm10');
            if (pm10El) {
                pm10El.textContent = summary.avg_pm10 != null
                    ? _escapeHtml(String(summary.avg_pm10)) + ' ' + I18n.t('aq_unit_ugm3')
                    : '--';
            }

            var caiEl = document.getElementById('aq-cai');
            if (caiEl) {
                caiEl.textContent = summary.avg_khai != null
                    ? String(summary.avg_khai)
                    : '--';
            }

            // Footer
            var stationEl = document.getElementById('aq-station');
            if (stationEl) {
                stationEl.textContent = _escapeHtml(summary.city || '') +
                    ' (' + (summary.station_count || 0) + ')';
            }

            var timeEl = document.getElementById('aq-time');
            if (timeEl && summary.timestamp) {
                var dt = new Date(summary.timestamp);
                var hh = String(dt.getHours()).padStart(2, '0');
                var mm = String(dt.getMinutes()).padStart(2, '0');
                timeEl.textContent = I18n.t('aq_updated') + ' ' + hh + ':' + mm;
            }

            // Show with animation
            section.style.display = '';
            requestAnimationFrame(function() {
                section.classList.add('air-quality--visible');
            });
        } catch (e) {
            console.warn('대기질 로드 실패:', e);
        }
    }

    // ─── 계절 테마 추천 ───
    async function loadSeasonThemes() {
        var section = document.getElementById('home-theme-section');
        var container = document.getElementById('home-theme-preview');
        if (!section || !container) return;

        try {
            var res = await fetch(API_BASE + '/themes/current?lang=' + I18n.getLang());
            var json = await res.json();
            if (!json.success || !json.data || !json.data.themes || json.data.themes.length === 0) return;

            var themes = json.data.themes;
            container.innerHTML = '';

            themes.forEach(function(t) {
                var card = document.createElement('a');
                card.className = 'home-theme-card';
                card.href = '/theme.html?id=' + encodeURIComponent(t.id);
                card.style.background = t.gradient;

                card.innerHTML =
                    '<div class="home-theme-card__overlay"></div>' +
                    '<div class="home-theme-card__content">' +
                        '<span class="home-theme-card__icon">' + t.icon + '</span>' +
                        '<span class="home-theme-card__name">' + _escapeHtml(t.name) + '</span>' +
                        '<span class="home-theme-card__desc">' + _escapeHtml(t.description) + '</span>' +
                    '</div>';

                container.appendChild(card);
            });

            section.style.display = '';
        } catch (e) {
            console.warn('계절 테마 로드 실패:', e);
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

    // ─── 7일 예보 & 여행일 추천 ───

    const DAY_KEYS = ['day_mon', 'day_tue', 'day_wed', 'day_thu', 'day_fri', 'day_sat', 'day_sun'];

    const CONDITION_ICONS = {
        rain: '\u{1F327}\u{FE0F}',
        clear_hot: '\u{2600}\u{FE0F}',
        clear_cool: '\u{1F31E}',
        cloudy: '\u{2601}\u{FE0F}',
    };

    let _forecastData = null;
    let _selectedForecastIdx = null;

    async function loadWeeklyForecast() {
        var section = document.getElementById('forecast-section');
        var list = document.getElementById('forecast-list');
        if (!section || !list) return;

        try {
            var res = await fetch(API_BASE + '/weather/forecast');
            var json = await res.json();
            if (!json.success || !json.data || !json.data.forecasts) return;

            _forecastData = json.data;
            var forecasts = json.data.forecasts;
            var bestDate = json.data.recommended_dates && json.data.recommended_dates[0];

            list.innerHTML = '';
            forecasts.forEach(function(fc, idx) {
                var card = document.createElement('div');
                card.className = 'forecast-card';
                if (fc.is_today) card.classList.add('forecast-card--today');

                var dayLabel = fc.is_today
                    ? I18n.t('forecast_today')
                    : I18n.t(DAY_KEYS[fc.day_of_week]);
                var dateShort = fc.date.substring(5); // MM-DD

                var scoreClass = _forecastScoreClass(fc.travel_score);
                var condIcon = CONDITION_ICONS[fc.condition] || '\u{1F324}\u{FE0F}';

                var badgeHtml = '';
                if (fc.recommended) {
                    var isBest = (fc.date === bestDate);
                    badgeHtml = '<span class="forecast-card__badge' +
                        (isBest ? ' forecast-card__badge--best' : '') + '">' +
                        (isBest ? I18n.t('forecast_best_day') : I18n.t('forecast_recommended')) +
                        '</span>';
                }

                var todayLabel = fc.is_today
                    ? '<div class="forecast-card__today-label">' + _escapeHtml(I18n.t('forecast_today')) + '</div>'
                    : '';

                card.innerHTML = badgeHtml +
                    todayLabel +
                    '<div class="forecast-card__day">' + _escapeHtml(dayLabel) + '</div>' +
                    '<div class="forecast-card__date">' + _escapeHtml(dateShort) + '</div>' +
                    '<div class="forecast-card__icon">' + condIcon + '</div>' +
                    '<div class="forecast-card__temp">' +
                        _escapeHtml(String(Math.round(fc.temp_max))) + '\u00B0' +
                        '<span class="forecast-card__temp-min"> / ' +
                            _escapeHtml(String(Math.round(fc.temp_min))) + '\u00B0</span>' +
                    '</div>' +
                    '<div class="forecast-card__rain">' +
                        '<span class="forecast-card__rain-icon">\u{1F4A7}</span>' +
                        _escapeHtml(String(fc.rain_probability)) + '%' +
                    '</div>' +
                    '<div class="forecast-card__score ' + scoreClass + '">' +
                        _escapeHtml(String(fc.travel_score)) + _escapeHtml(I18n.t('unit_score')) +
                    '</div>';

                card.addEventListener('click', function() {
                    _openForecastDetail(idx);
                });

                list.appendChild(card);
            });

            section.style.display = '';

            // Auto-scroll to today's card on mobile
            requestAnimationFrame(function() {
                var todayCard = list.querySelector('.forecast-card--today');
                if (todayCard && window.innerWidth < 768) {
                    var scrollContainer = document.getElementById('forecast-scroll');
                    if (scrollContainer) {
                        var cardLeft = todayCard.offsetLeft;
                        var containerWidth = scrollContainer.clientWidth;
                        var cardWidth = todayCard.offsetWidth;
                        scrollContainer.scrollLeft = cardLeft - (containerWidth - cardWidth) / 2;
                    }
                }
            });
        } catch (e) {
            console.warn('7일 예보 로드 실패:', e);
        }
    }

    function _forecastScoreClass(score) {
        if (score >= 70) return 'forecast-card__score--good';
        if (score >= 50) return 'forecast-card__score--normal';
        return 'forecast-card__score--poor';
    }

    function _openForecastDetail(idx) {
        if (!_forecastData || !_forecastData.forecasts[idx]) return;

        var fc = _forecastData.forecasts[idx];
        var detail = document.getElementById('forecast-detail');
        var titleEl = document.getElementById('forecast-detail-title');
        var bodyEl = document.getElementById('forecast-detail-body');
        var spotsEl = document.getElementById('forecast-detail-spots');
        if (!detail || !titleEl || !bodyEl || !spotsEl) return;

        // 이전 선택 해제
        var cards = document.querySelectorAll('.forecast-card');
        cards.forEach(function(c, i) {
            c.classList.toggle('forecast-card--active', i === idx);
        });

        // 같은 카드 다시 클릭 시 닫기
        if (_selectedForecastIdx === idx) {
            detail.style.display = 'none';
            _selectedForecastIdx = null;
            cards.forEach(function(c) { c.classList.remove('forecast-card--active'); });
            return;
        }
        _selectedForecastIdx = idx;

        var dayLabel = fc.is_today
            ? I18n.t('forecast_today')
            : I18n.t(DAY_KEYS[fc.day_of_week]);
        titleEl.textContent = fc.date + ' (' + dayLabel + ') — ' + I18n.t('forecast_detail_title');

        var condIcon = CONDITION_ICONS[fc.condition] || '\u{1F324}\u{FE0F}';
        var skyText = _weatherStatusText(fc.sky_code, fc.rain_type);

        bodyEl.innerHTML =
            '<div class="forecast-detail__item">' +
                '<span class="forecast-detail__item-icon">' + condIcon + '</span>' +
                '<span class="forecast-detail__item-label">' + _escapeHtml(skyText) + '</span>' +
            '</div>' +
            '<div class="forecast-detail__item">' +
                '<span class="forecast-detail__item-icon">\u{1F321}\u{FE0F}</span>' +
                '<span>' + _escapeHtml(String(Math.round(fc.temp_min))) + '\u00B0 ~ ' +
                    _escapeHtml(String(Math.round(fc.temp_max))) + '\u00B0C</span>' +
            '</div>' +
            '<div class="forecast-detail__item">' +
                '<span class="forecast-detail__item-icon">\u{1F4A7}</span>' +
                '<span>' + _escapeHtml(I18n.t('forecast_rain_prob')) + ' ' +
                    _escapeHtml(String(fc.rain_probability)) + '%</span>' +
            '</div>' +
            '<div class="forecast-detail__item">' +
                '<span class="forecast-detail__item-icon">\u{1F4A8}</span>' +
                '<span>' + _escapeHtml(I18n.t('forecast_humidity')) + ' ' +
                    _escapeHtml(String(fc.humidity)) + '%</span>' +
            '</div>' +
            '<div class="forecast-detail__item">' +
                '<span class="forecast-detail__item-icon">\u{1F3AF}</span>' +
                '<span>' + _escapeHtml(I18n.t('forecast_travel_score')) + ' ' +
                    '<strong>' + _escapeHtml(String(fc.travel_score)) + '</strong>' +
                    _escapeHtml(I18n.t('unit_score')) + '</span>' +
            '</div>';

        // 추천 관광지 로드
        _loadForecastSpots(fc, spotsEl);

        detail.style.display = '';
    }

    async function _loadForecastSpots(fc, container) {
        container.innerHTML = '<p class="forecast-detail__spots-title">' +
            _escapeHtml(I18n.t('forecast_recommended_spots')) + '</p>';

        // 날씨 조건에 따른 추천 카테고리
        var categories = [];
        if (fc.condition === 'rain') {
            categories = ['culture', 'food', 'shopping'];
        } else if (fc.condition === 'clear_hot') {
            categories = ['nature', 'activity'];
        } else if (fc.condition === 'cloudy') {
            categories = ['food', 'culture'];
        } else {
            categories = ['nature', 'nightview', 'activity'];
        }

        try {
            var params = new URLSearchParams({
                limit: '5',
                offset: '0',
                lang: I18n.getLang(),
                categories: categories[0],
            });
            var res = await fetch(API_BASE + '/recommend?' + params);
            var json = await res.json();

            if (!json.success || !json.data || json.data.length === 0) {
                container.innerHTML += '<p style="font-size:.8rem;color:var(--color-text-secondary)">' +
                    _escapeHtml(I18n.t('no_results')) + '</p>';
                return;
            }

            var listEl = document.createElement('div');
            listEl.className = 'forecast-detail__spot-list';

            json.data.forEach(function(spot) {
                var a = document.createElement('a');
                a.className = 'forecast-detail__spot';
                a.href = '/detail.html?id=' + encodeURIComponent(spot.id);

                var score = spot.comfort_score;
                var scoreClass = score >= 70 ? 'forecast-card__score--good' :
                                 score >= 50 ? 'forecast-card__score--normal' :
                                 'forecast-card__score--poor';

                a.innerHTML =
                    '<span class="forecast-detail__spot-score ' + scoreClass + '">' +
                        (score != null ? score : '--') +
                    '</span>' +
                    '<span>' + _escapeHtml(spot.name) + '</span>';

                listEl.appendChild(a);
            });

            container.appendChild(listEl);
        } catch (e) {
            console.warn('추천 관광지 로드 실패:', e);
        }
    }

    function _weatherStatusText(skyCode, rainType) {
        if (rainType && rainType !== '\uC5C6\uC74C' && rainType !== '0' && rainType !== 'None') {
            if (rainType === '\uBE44') return I18n.t('weather_rain');
            if (rainType === '\uB208') return I18n.t('weather_snow');
            if (rainType.indexOf('\uBE44') >= 0 && rainType.indexOf('\uB208') >= 0) return I18n.t('weather_rain_snow');
            return I18n.t('weather_rain');
        }
        var skyMap = {
            '1': 'weather_clear',
            '3': 'weather_mostly_cloudy',
            '4': 'weather_overcast',
        };
        return I18n.t(skyMap[skyCode] || 'weather_clear');
    }

    // 상세 패널 닫기 버튼
    var closeBtn = document.getElementById('forecast-detail-close');
    if (closeBtn) {
        closeBtn.addEventListener('click', function() {
            var detail = document.getElementById('forecast-detail');
            if (detail) detail.style.display = 'none';
            _selectedForecastIdx = null;
            document.querySelectorAll('.forecast-card').forEach(function(c) {
                c.classList.remove('forecast-card--active');
            });
        });
    }

    // ─── 이번 주 축제 ───

    async function loadThisWeekFestivals() {
        var section = document.getElementById('this-week-festivals-section');
        var list = document.getElementById('this-week-festivals-list');
        if (!section || !list) return;

        try {
            var res = await fetch(API_BASE + '/festivals/this-week');
            var json = await res.json();
            if (!json.success || !json.data || json.data.length === 0) {
                section.style.display = 'none';
                return;
            }

            list.innerHTML = '';
            json.data.forEach(function(fest) {
                var card = document.createElement('a');
                card.className = 'tw-festival-card';
                card.href = '/festival.html?id=' + encodeURIComponent(fest.id);

                var safeName = _escapeHtml(fest.name);
                var safeLocation = _escapeHtml(fest.location || '');
                var dateRange = _twFormatDate(fest.start_date, fest.end_date);

                var thumb = (fest.images && fest.images.length > 0) ? fest.images[0] : '';
                var imgHtml = thumb
                    ? '<img src="' + _escapeHtml(thumb) + '" alt="' + safeName + '" class="tw-festival-card__img" loading="lazy">'
                    : '<div class="tw-festival-card__img-placeholder">&#x1F389;</div>';

                // D-day badge
                var dDay = fest.d_day;
                var badgeClass = 'tw-festival-card__dday';
                var badgeText = '';
                if (dDay === 0 || dDay === null) {
                    badgeClass += ' tw-festival-card__dday--ongoing';
                    badgeText = I18n.t('festival_ongoing') || '진행 중';
                } else if (dDay != null && dDay > 0) {
                    badgeClass += ' tw-festival-card__dday--upcoming';
                    badgeText = 'D-' + dDay;
                }

                var catLabel = _twCategoryLabel(fest.category);

                card.innerHTML =
                    '<div class="tw-festival-card__image">' +
                        imgHtml +
                        (badgeText ? '<span class="' + badgeClass + '">' + badgeText + '</span>' : '') +
                    '</div>' +
                    '<div class="tw-festival-card__body">' +
                        '<span class="tw-festival-card__cat">' + _escapeHtml(catLabel) + '</span>' +
                        '<h3 class="tw-festival-card__name">' + safeName + '</h3>' +
                        '<p class="tw-festival-card__date">&#x1F4C5; ' + _escapeHtml(dateRange) + '</p>' +
                        (safeLocation ? '<p class="tw-festival-card__location">&#x1F4CD; ' + safeLocation + '</p>' : '') +
                    '</div>';

                list.appendChild(card);
            });

            section.style.display = '';
        } catch (e) {
            console.warn('이번 주 축제 로드 실패:', e);
            section.style.display = 'none';
        }
    }

    function _twFormatDate(start, end) {
        if (!start && !end) return '';
        var s = start ? start.substring(5).replace('-', '.') : '?';
        var e = end ? end.substring(5).replace('-', '.') : '?';
        if (s === e) return s;
        return s + ' ~ ' + e;
    }

    function _twCategoryLabel(cat) {
        var map = {
            '축제': I18n.t('festival_cat_festival') || '축제',
            '공연': I18n.t('festival_cat_performance') || '공연',
            '전시': I18n.t('festival_cat_exhibition') || '전시',
            '체험': I18n.t('festival_cat_experience') || '체험',
        };
        return map[cat] || cat || '';
    }

    // ─── 히어로 배너 이미지 슬라이더 ───

    function _applySliderAltTexts() {
        document.querySelectorAll('[data-i18n-alt]').forEach(function(el) {
            var key = el.getAttribute('data-i18n-alt');
            var val = I18n.t(key);
            if (val && val !== key) el.alt = val;
        });
    }

    function initHeroSlider() {
        var slides = document.querySelectorAll('.hero-slider__slide');
        var dotsContainer = document.getElementById('hero-slider-dots');
        var prevBtn = document.getElementById('hero-slider-prev');
        var nextBtn = document.getElementById('hero-slider-next');
        var slider = document.getElementById('hero-slider');
        if (!slides.length || !slider) return;

        var current = 0;
        var total = slides.length;
        var interval = null;
        var INTERVAL_MS = 5000;

        // 슬라이드 수에 맞춰 dot 동적 생성
        var dots = [];
        if (dotsContainer) {
            dotsContainer.innerHTML = '';
            for (var i = 0; i < total; i++) {
                var dot = document.createElement('button');
                dot.className = 'hero-slider__dot' + (i === 0 ? ' hero-slider__dot--active' : '');
                dot.setAttribute('role', 'tab');
                dot.setAttribute('aria-selected', i === 0 ? 'true' : 'false');
                dot.setAttribute('aria-label', 'Slide ' + (i + 1));
                dot.setAttribute('data-slide', String(i));
                dotsContainer.appendChild(dot);
                dots.push(dot);
            }
        }

        // Apply i18n alt texts on init
        _applySliderAltTexts();

        // alt 텍스트로 캡션 자동 생성
        slides.forEach(function(slide) {
            var img = slide.querySelector('.hero-slider__img');
            var altText = img ? img.alt : '';
            if (altText) {
                var caption = document.createElement('span');
                caption.className = 'hero-slider__caption';
                caption.textContent = altText;
                slide.appendChild(caption);
            }
        });

        function goTo(idx) {
            slides[current].classList.remove('hero-slider__slide--active');
            if (dots[current]) {
                dots[current].classList.remove('hero-slider__dot--active');
                dots[current].setAttribute('aria-selected', 'false');
            }
            current = ((idx % total) + total) % total;
            slides[current].classList.add('hero-slider__slide--active');
            if (dots[current]) {
                dots[current].classList.add('hero-slider__dot--active');
                dots[current].setAttribute('aria-selected', 'true');
            }
        }

        function next() { goTo(current + 1); }
        function prev() { goTo(current - 1); }

        function startAuto() {
            stopAuto();
            interval = setInterval(next, INTERVAL_MS);
        }
        function stopAuto() {
            if (interval) { clearInterval(interval); interval = null; }
        }

        // Arrow buttons
        if (nextBtn) nextBtn.addEventListener('click', function() { stopAuto(); next(); startAuto(); });
        if (prevBtn) prevBtn.addEventListener('click', function() { stopAuto(); prev(); startAuto(); });

        // Dot buttons
        dots.forEach(function(dot) {
            dot.addEventListener('click', function() {
                var idx = parseInt(dot.getAttribute('data-slide'), 10);
                if (idx !== current) { stopAuto(); goTo(idx); startAuto(); }
            });
        });

        // Touch swipe support (tracks both axes to avoid hijacking vertical scroll)
        var touchStartX = 0;
        var touchStartY = 0;
        var SWIPE_THRESHOLD = 50;

        slider.addEventListener('touchstart', function(e) {
            touchStartX = e.changedTouches[0].screenX;
            touchStartY = e.changedTouches[0].screenY;
        }, { passive: true });

        slider.addEventListener('touchend', function(e) {
            var touchEndX = e.changedTouches[0].screenX;
            var touchEndY = e.changedTouches[0].screenY;
            var diffX = touchStartX - touchEndX;
            var diffY = touchStartY - touchEndY;
            // Only trigger slide change if horizontal swipe is dominant
            if (Math.abs(diffX) > SWIPE_THRESHOLD && Math.abs(diffX) > Math.abs(diffY) * 1.5) {
                stopAuto();
                if (diffX > 0) next(); else prev();
                startAuto();
            }
        }, { passive: true });

        // Pause on hover / focus
        slider.addEventListener('mouseenter', stopAuto);
        slider.addEventListener('mouseleave', startAuto);
        slider.addEventListener('focusin', stopAuto);
        slider.addEventListener('focusout', startAuto);

        // Pause when page is not visible
        document.addEventListener('visibilitychange', function() {
            if (document.hidden) stopAuto(); else startAuto();
        });

        // Respect reduced motion
        if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

        startAuto();
    }
})();
