/**
 * weather-page.js — 날씨 전용 페이지 모듈
 * Sections:
 *   1. 현재 날씨 (current)
 *   2. 시간대별 날씨 타임라인 (hourly)
 *   3. 7일 예보 + 여행 적합도 (forecast)
 *   4. 대기질 정보 (air quality)
 *   5. 날씨 기반 관광지 추천 (recommend)
 *
 * CSS classes: weather-page-* (aligned with weather-tab-3)
 * HTML IDs: wp-current-*, weather-detail-*, weather-hourly-*,
 *            weather-forecast-*, air-quality-*, weather-spots-*
 */
(async () => {
    'use strict';

    var API_BASE = '/api/v1';

    // i18n + Analytics 초기화
    if (typeof Analytics !== 'undefined') Analytics.init();
    await I18n.init();

    // ── XSS 방어 ──
    function _escapeHtml(str) {
        if (!str) return '';
        var div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    // ── 공통 상수 ──
    var DAY_KEYS = ['day_mon', 'day_tue', 'day_wed', 'day_thu', 'day_fri', 'day_sat', 'day_sun'];

    var CONDITION_ICONS = {
        rain: '\u{1F327}\u{FE0F}',
        clear_hot: '\u{2600}\u{FE0F}',
        clear_cool: '\u{1F31E}',
        cloudy: '\u{2601}\u{FE0F}',
    };

    var CONDITION_LABELS = {
        rain: 'weather_rain',
        clear_hot: 'weather_clear',
        clear_cool: 'weather_clear',
        cloudy: 'weather_overcast',
    };

    // condition -> CSS modifier for .weather-page-current--*
    var CONDITION_CSS = {
        rain: 'rain',
        clear_hot: 'clear',
        clear_cool: 'clear',
        cloudy: 'cloudy',
    };

    var WEATHER_RECOMMEND_CATEGORIES = {
        rain: ['culture', 'food', 'shopping'],
        clear_hot: ['nature', 'activity'],
        clear_cool: ['nature', 'nightview', 'activity'],
        cloudy: ['food', 'culture'],
    };

    // ── 상태 ──
    var _forecastData = null;
    var _selectedForecastIdx = null;
    var _currentCondition = 'clear_cool';

    // ── 초기 로드 ──
    loadCurrentWeather();
    loadTimeline();
    loadWeeklyForecast();
    loadAirQuality();
    loadWeatherRecommendations();

    // 언어 변경 시 전체 재로드
    window.addEventListener('langchange', function () {
        var langSelect = document.getElementById('lang-select');
        if (langSelect) langSelect.value = I18n.getLang();
        loadCurrentWeather();
        loadTimeline();
        loadWeeklyForecast();
        loadAirQuality();
        loadWeatherRecommendations();
    });

    // ═══════════════════════════════════════
    // 1. 현재 날씨
    // ═══════════════════════════════════════

    async function loadCurrentWeather() {
        try {
            var res = await fetch(API_BASE + '/weather/current');
            var json = await res.json();
            if (!json.success || !json.data) return;

            var d = json.data;
            _currentCondition = d.condition || 'clear_cool';

            // 아이콘
            var iconEl = document.getElementById('wp-current-icon');
            if (iconEl) iconEl.textContent = CONDITION_ICONS[d.condition] || '\u{1F324}\u{FE0F}';

            // 기온
            var tempEl = document.getElementById('wp-current-temp');
            if (tempEl) tempEl.textContent = Math.round(d.tmp) + '\u00B0C';

            // 상태 텍스트
            var statusEl = document.getElementById('wp-current-status');
            if (statusEl) {
                var statusKey = CONDITION_LABELS[d.condition] || 'weather_clear';
                statusEl.textContent = I18n.t(statusKey);
            }

            // 습도
            var humidityEl = document.getElementById('weather-detail-humidity');
            if (humidityEl) humidityEl.textContent = _escapeHtml(String(d.humidity)) + '%';

            // 풍속
            var windEl = document.getElementById('weather-detail-wind');
            if (windEl) windEl.textContent = _escapeHtml(String(d.wind_speed)) + ' m/s';

            // 하늘 상태
            var skyEl = document.getElementById('weather-detail-sky');
            if (skyEl) skyEl.textContent = _escapeHtml(d.sky_text || '');

            // 강수 상태
            var rainEl = document.getElementById('weather-detail-rain');
            if (rainEl) rainEl.textContent = _escapeHtml(d.pty || '--');

            // 배경 그라디언트 적용
            var heroSection = document.getElementById('weather-current');
            if (heroSection) {
                var cssMod = CONDITION_CSS[d.condition] || 'clear';
                heroSection.className = 'weather-page-current weather-page-current--' + cssMod;
            }

            // 타임스탬프
            var timeEl = document.getElementById('weather-current-timestamp');
            if (timeEl && d.timestamp) {
                var ts = new Date(d.timestamp);
                timeEl.textContent = _formatTime(ts);
            }
        } catch (e) {
            console.warn('현재 날씨 로드 실패:', e);
        }
    }

    function _formatTime(date) {
        var h = date.getHours();
        var m = date.getMinutes();
        var ampm = h >= 12 ? 'PM' : 'AM';
        h = h % 12 || 12;
        return h + ':' + (m < 10 ? '0' : '') + m + ' ' + ampm;
    }

    // ═══════════════════════════════════════
    // 2. 시간대별 날씨 타임라인
    // ═══════════════════════════════════════

    async function loadTimeline() {
        var section = document.getElementById('hourly-section');
        var container = document.getElementById('weather-hourly-list');
        if (!container) return;

        try {
            var res = await fetch(API_BASE + '/weather/current');
            var json = await res.json();

            if (!json.success || !json.data) {
                _renderTimelineFallback(container);
                return;
            }

            // 현재 날씨 기반으로 하루 시간대별 추정 타임라인 생성
            var current = json.data;
            var timeline = _generateHourlyTimeline(current);

            container.innerHTML = '';
            timeline.forEach(function (entry) {
                var card = document.createElement('div');
                card.className = 'weather-page-hourly__item';
                if (entry.isNow) card.classList.add('weather-page-hourly__item--now');

                card.innerHTML =
                    '<div class="weather-page-hourly__item-time">' + _escapeHtml(entry.timeLabel) + '</div>' +
                    '<div class="weather-page-hourly__item-icon">' + entry.icon + '</div>' +
                    '<div class="weather-page-hourly__item-temp">' + _escapeHtml(String(entry.temp)) + '\u00B0</div>';

                container.appendChild(card);
            });

            // 섹션 표시 (기본 display:none)
            if (section) section.style.display = '';

            // Auto-scroll to "now" item on mobile
            requestAnimationFrame(function() {
                var nowItem = container.querySelector('.weather-page-hourly__item--now');
                if (nowItem) {
                    var scrollParent = container.parentElement;
                    if (scrollParent && scrollParent.scrollWidth > scrollParent.clientWidth) {
                        scrollParent.scrollLeft = 0; // "now" is the first item
                    }
                }
            });
        } catch (e) {
            console.warn('타임라인 로드 실패:', e);
            _renderTimelineFallback(container);
        }
    }

    function _generateHourlyTimeline(current) {
        var now = new Date();
        var currentHour = now.getHours();
        var baseTmp = current.tmp || 20;
        var condition = current.condition || 'clear_cool';
        var entries = [];

        // 현재 시각 기준 앞뒤 12시간 (현재부터 +12시간)
        for (var i = 0; i < 12; i++) {
            var hour = (currentHour + i) % 24;
            var isNow = (i === 0);

            // 시간별 기온 변화 근사 (일출/일몰 곡선)
            var tempOffset = _hourlyTempOffset(hour);
            var temp = Math.round(baseTmp + tempOffset);

            // 시간별 날씨 아이콘 (야간이면 달 아이콘)
            var icon;
            if (hour >= 6 && hour < 20) {
                icon = CONDITION_ICONS[condition] || '\u{1F324}\u{FE0F}';
            } else {
                icon = condition === 'rain' ? '\u{1F327}\u{FE0F}' : '\u{1F319}';
            }

            var timeLabel;
            if (isNow) {
                timeLabel = I18n.t('forecast_today');
            } else {
                var ampm = hour >= 12 ? 'PM' : 'AM';
                var displayHour = hour % 12 || 12;
                timeLabel = displayHour + ampm;
            }

            entries.push({
                hour: hour,
                timeLabel: timeLabel,
                temp: temp,
                icon: icon,
                isNow: isNow,
            });
        }

        return entries;
    }

    function _hourlyTempOffset(hour) {
        // 간이 일교차 곡선: 14시 최고, 05시 최저
        // sin 기반으로 -3 ~ +3 범위
        var rad = ((hour - 14) / 24) * 2 * Math.PI;
        return Math.round(Math.cos(rad) * 3);
    }

    function _renderTimelineFallback(container) {
        container.innerHTML = '<p class="weather-page__empty">' + _escapeHtml(I18n.t('forecast_no_data')) + '</p>';
    }

    // ═══════════════════════════════════════
    // 3. 7일 예보 + 여행 적합도
    // ═══════════════════════════════════════

    async function loadWeeklyForecast() {
        var section = document.getElementById('weather-forecast-section');
        var list = document.getElementById('weather-forecast-list');
        if (!list) return;

        try {
            var res = await fetch(API_BASE + '/weather/forecast');
            var json = await res.json();
            if (!json.success || !json.data || !json.data.forecasts) return;

            _forecastData = json.data;
            var forecasts = json.data.forecasts;
            var bestDate = json.data.recommended_dates && json.data.recommended_dates[0];

            list.innerHTML = '';
            forecasts.forEach(function (fc, idx) {
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
                        (isBest ? _escapeHtml(I18n.t('forecast_best_day')) : _escapeHtml(I18n.t('forecast_recommended'))) +
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

                card.addEventListener('click', function () {
                    _openForecastDetail(idx);
                });

                list.appendChild(card);
            });

            if (section) section.style.display = '';

            // Auto-scroll to today's card on mobile
            requestAnimationFrame(function() {
                var todayCard = list.querySelector('.forecast-card--today');
                if (todayCard && window.innerWidth < 768) {
                    var scrollContainer = list.parentElement;
                    if (scrollContainer && scrollContainer.scrollWidth > scrollContainer.clientWidth) {
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
        var detail = document.getElementById('weather-forecast-detail');
        var titleEl = document.getElementById('weather-forecast-detail-title');
        var bodyEl = document.getElementById('weather-forecast-detail-body');
        var spotsEl = document.getElementById('weather-forecast-detail-spots');
        if (!detail || !titleEl || !bodyEl || !spotsEl) return;

        // 이전 선택 해제
        var cards = document.querySelectorAll('.forecast-card');
        cards.forEach(function (c, i) {
            c.classList.toggle('forecast-card--active', i === idx);
        });

        // 같은 카드 다시 클릭 시 닫기
        if (_selectedForecastIdx === idx) {
            detail.style.display = 'none';
            _selectedForecastIdx = null;
            cards.forEach(function (c) { c.classList.remove('forecast-card--active'); });
            return;
        }
        _selectedForecastIdx = idx;

        var dayLabel = fc.is_today
            ? I18n.t('forecast_today')
            : I18n.t(DAY_KEYS[fc.day_of_week]);
        titleEl.textContent = fc.date + ' (' + dayLabel + ') \u2014 ' + I18n.t('forecast_detail_title');

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

        var categories = WEATHER_RECOMMEND_CATEGORIES[fc.condition] || ['nature', 'nightview'];

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
                container.innerHTML += '<p class="weather-page__empty">' +
                    _escapeHtml(I18n.t('no_results')) + '</p>';
                return;
            }

            var listEl = document.createElement('div');
            listEl.className = 'forecast-detail__spot-list';

            json.data.forEach(function (spot) {
                var a = document.createElement('a');
                a.className = 'forecast-detail__spot';
                a.href = '/detail.html?id=' + encodeURIComponent(spot.id);

                var score = spot.comfort_score;
                var scoreClass = score >= 70 ? 'forecast-card__score--good' :
                                 score >= 50 ? 'forecast-card__score--normal' :
                                 'forecast-card__score--poor';

                a.innerHTML =
                    '<span class="forecast-detail__spot-score ' + scoreClass + '">' +
                        (score != null ? _escapeHtml(String(score)) : '--') +
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
    var closeBtn = document.getElementById('weather-forecast-detail-close');
    if (closeBtn) {
        closeBtn.addEventListener('click', function () {
            var detail = document.getElementById('weather-forecast-detail');
            if (detail) detail.style.display = 'none';
            _selectedForecastIdx = null;
            document.querySelectorAll('.forecast-card').forEach(function (c) {
                c.classList.remove('forecast-card--active');
            });
        });
    }

    // ═══════════════════════════════════════
    // 4. 대기질 정보
    // ═══════════════════════════════════════

    async function loadAirQuality() {
        var section = document.getElementById('air-quality-section');
        if (!section) return;

        try {
            var res = await fetch(API_BASE + '/air-quality');
            var json = await res.json();

            if (!json.success || !json.data || !json.data.summary) return;

            var summary = json.data.summary;
            var stations = json.data.stations || [];

            // 등급 텍스트
            var gradeEl = document.getElementById('air-quality-text');
            if (gradeEl) {
                var gradeText = summary.overall_grade_text || '-';
                gradeEl.textContent = _escapeHtml(gradeText);
                gradeEl.className = 'weather-page-air__level weather-page-air__level--' + _airGradeClass(summary.overall_grade);
            }

            // 등급 아이콘
            var iconEl = document.getElementById('air-quality-icon');
            if (iconEl) {
                var icons = { 1: '\u{1F7E2}', 2: '\u{1F7E1}', 3: '\u{1F7E0}', 4: '\u{1F534}' };
                iconEl.textContent = icons[summary.overall_grade] || '\u{26AA}';
            }

            // PM10
            var pm10El = document.getElementById('aq-pm10');
            if (pm10El) {
                pm10El.textContent = summary.avg_pm10 != null
                    ? _escapeHtml(String(summary.avg_pm10))
                    : '-';
            }

            // PM2.5
            var pm25El = document.getElementById('aq-pm25');
            if (pm25El) {
                pm25El.textContent = summary.avg_pm25 != null
                    ? _escapeHtml(String(summary.avg_pm25))
                    : '-';
            }

            // O3 평균 (stations 데이터에서 계산)
            var o3El = document.getElementById('aq-o3');
            if (o3El) {
                var o3Vals = stations
                    .map(function(s) { return s.o3_value; })
                    .filter(function(v) { return v != null; });
                if (o3Vals.length > 0) {
                    var avgO3 = o3Vals.reduce(function(a, b) { return a + b; }, 0) / o3Vals.length;
                    o3El.textContent = avgO3.toFixed(3);
                } else {
                    o3El.textContent = '-';
                }
            }

            // NO2 평균 (stations 데이터에서 계산)
            var no2El = document.getElementById('aq-no2');
            if (no2El) {
                var no2Vals = stations
                    .map(function(s) { return s.no2_value; })
                    .filter(function(v) { return v != null; });
                if (no2Vals.length > 0) {
                    var avgNo2 = no2Vals.reduce(function(a, b) { return a + b; }, 0) / no2Vals.length;
                    no2El.textContent = avgNo2.toFixed(3);
                } else {
                    no2El.textContent = '-';
                }
            }

            // 대기질 메시지
            var msgEl = document.getElementById('air-quality-message');
            if (msgEl) {
                msgEl.textContent = _airMessage(summary.overall_grade);
            }

            section.style.display = '';
        } catch (e) {
            console.warn('대기질 로드 실패:', e);
        }
    }

    function _airGradeClass(grade) {
        if (grade === 1) return 'good';
        if (grade === 2) return 'moderate';
        if (grade === 3) return 'unhealthy';
        if (grade === 4) return 'very-unhealthy';
        return 'unknown';
    }

    function _airMessage(grade) {
        if (grade === 1) return I18n.t('weather_page_aqi_good');
        if (grade === 2) return I18n.t('weather_page_aqi_moderate');
        if (grade === 3) return I18n.t('weather_page_aqi_unhealthy');
        if (grade === 4) return I18n.t('weather_page_aqi_very_unhealthy');
        return '';
    }

    // ═══════════════════════════════════════
    // 5. 날씨 기반 관광지 추천
    // ═══════════════════════════════════════

    async function loadWeatherRecommendations() {
        var section = document.getElementById('weather-spots-section');
        var container = document.getElementById('weather-spots-list');
        if (!container) return;

        var categories = WEATHER_RECOMMEND_CATEGORIES[_currentCondition] || ['nature', 'nightview'];

        // 탭 버튼: 추천 카테고리 표시
        var tabsEl = document.getElementById('weather-spots-tabs');
        if (tabsEl) {
            tabsEl.innerHTML = '';
            categories.forEach(function (cat) {
                var tab = document.createElement('button');
                tab.className = 'weather-spots-tab';
                tab.setAttribute('data-type', 'recommend');
                tab.textContent = _categoryLabel(cat);
                tabsEl.appendChild(tab);
            });
        }

        // 빈 상태 메시지 요소 (데이터 로드 후 숨김)
        var emptyEl = document.getElementById('weather-spots-empty');
        if (emptyEl) {
            var condKey = {
                rain: 'weather_banner_rain',
                clear_hot: 'weather_banner_clear_hot',
                clear_cool: 'weather_banner_clear_cool',
                cloudy: 'weather_banner_cloudy',
            };
            emptyEl.textContent = I18n.t(condKey[_currentCondition] || 'weather_banner_clear_cool');
        }

        try {
            // 각 추천 카테고리에서 관광지를 가져옴
            var allSpots = [];
            var fetched = {};

            for (var i = 0; i < categories.length && allSpots.length < 6; i++) {
                var cat = categories[i];
                var params = new URLSearchParams({
                    limit: '3',
                    offset: '0',
                    lang: I18n.getLang(),
                    categories: cat,
                });
                var res = await fetch(API_BASE + '/recommend?' + params);
                var json = await res.json();

                if (json.success && json.data) {
                    json.data.forEach(function (spot) {
                        if (!fetched[spot.id] && allSpots.length < 6) {
                            fetched[spot.id] = true;
                            spot._category = cat;
                            allSpots.push(spot);
                        }
                    });
                }
            }

            if (allSpots.length === 0) {
                container.innerHTML = '<p class="weather-page__empty">' + _escapeHtml(I18n.t('no_results')) + '</p>';
                return;
            }

            container.innerHTML = '';
            if (emptyEl) emptyEl.style.display = 'none';

            allSpots.forEach(function (spot) {
                var card = document.createElement('a');
                card.className = 'popular-card';
                card.href = '/detail.html?id=' + encodeURIComponent(spot.id);

                var score = spot.comfort_score;
                var scoreClass = _spotScoreClass(score);
                var gradeText = _spotGradeText(score);
                var safeName = _escapeHtml(spot.name);
                var safeAddress = _escapeHtml(spot.address || '');
                var catLabel = _categoryLabel(spot._category || spot.category);

                var thumbUrl = spot.thumbnail_url || (spot.images && spot.images.length > 0 ? spot.images[0] : '');
                var imgHtml = thumbUrl
                    ? '<img src="' + _escapeHtml(thumbUrl) + '" alt="' + safeName + '" class="popular-card__img" loading="lazy">'
                    : '<div class="popular-card__img-placeholder">' + _categoryEmoji(spot._category || spot.category) + '</div>';

                card.innerHTML =
                    '<div class="popular-card__image">' +
                        imgHtml +
                        '<div class="popular-card__badge ' + scoreClass + '">' +
                            '<span class="popular-card__badge-score">' + (score != null ? _escapeHtml(String(score)) : '--') + '</span>' +
                            '<span class="popular-card__badge-grade">' + _escapeHtml(gradeText) + '</span>' +
                        '</div>' +
                    '</div>' +
                    '<div class="popular-card__body">' +
                        '<span class="popular-card__cat">' + _escapeHtml(catLabel) + '</span>' +
                        '<h3 class="popular-card__name">' + safeName + '</h3>' +
                        (safeAddress ? '<p class="popular-card__address">' + safeAddress + '</p>' : '') +
                    '</div>';

                card.addEventListener('click', function () {
                    if (typeof Analytics !== 'undefined') Analytics.trackSpotClick(spot.id, spot.name);
                });

                container.appendChild(card);
            });

            if (section) section.style.display = '';
        } catch (e) {
            console.warn('날씨 기반 추천 로드 실패:', e);
            container.innerHTML = '<p class="weather-page__empty">' + _escapeHtml(I18n.t('popular_load_failed')) + '</p>';
        }
    }

    // ── 유틸 ──

    function _spotScoreClass(score) {
        if (score == null) return '';
        if (score >= 80) return 'score--good';
        if (score >= 60) return 'score--normal';
        if (score >= 40) return 'score--crowded';
        return 'score--very-crowded';
    }

    function _spotGradeText(score) {
        if (score == null) return '';
        if (score >= 80) return I18n.t('comfort_good');
        if (score >= 60) return I18n.t('comfort_normal');
        if (score >= 40) return I18n.t('comfort_crowded');
        return I18n.t('comfort_very_crowded');
    }

    function _categoryLabel(cat) {
        var keyMap = {
            nature: 'category_nature', culture: 'category_culture', food: 'category_food',
            activity: 'category_activity', shopping: 'category_shopping', nightview: 'category_nightview',
        };
        return keyMap[cat] ? I18n.t(keyMap[cat]) : (cat || '');
    }

    function _categoryEmoji(cat) {
        var map = {
            nature: '\u{1F3D4}', culture: '\u{1F3DB}', food: '\u{1F35C}',
            activity: '\u{1F3C4}', shopping: '\u{1F6CD}', nightview: '\u{1F319}',
        };
        return map[cat] || '\u{1F30A}';
    }
})();
