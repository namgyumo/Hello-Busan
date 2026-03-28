/**
 * theme-page.js — 계절·테마 큐레이션 페이지
 */
(async () => {
    const API_BASE = '/api/v1';

    if (typeof Analytics !== 'undefined') Analytics.init();
    await I18n.init();

    // 계절별 설정
    const SEASON_CONFIG = {
        spring: {
            label: '봄',
            emoji: '\u{1F338}',
            gradient: 'linear-gradient(135deg, #FADADD 0%, #F8BBD0 40%, #F48FB1 100%)',
            heroGradient: 'linear-gradient(135deg, #F8BBD0 0%, #F48FB1 50%, #EC407A 100%)',
        },
        summer: {
            label: '여름',
            emoji: '\u{1F3D6}\u{FE0F}',
            gradient: 'linear-gradient(135deg, #B3E5FC 0%, #4FC3F7 40%, #0288D1 100%)',
            heroGradient: 'linear-gradient(135deg, #4FC3F7 0%, #0288D1 50%, #01579B 100%)',
        },
        fall: {
            label: '가을',
            emoji: '\u{1F341}',
            gradient: 'linear-gradient(135deg, #FFE0B2 0%, #FFB74D 40%, #FF9800 100%)',
            heroGradient: 'linear-gradient(135deg, #FFB74D 0%, #FF9800 50%, #E65100 100%)',
        },
        winter: {
            label: '겨울',
            emoji: '\u{2744}\u{FE0F}',
            gradient: 'linear-gradient(135deg, #E8EAF6 0%, #9FA8DA 40%, #5C6BC0 100%)',
            heroGradient: 'linear-gradient(135deg, #9FA8DA 0%, #5C6BC0 50%, #283593 100%)',
        },
    };

    let _currentThemeId = null;
    let _currentOffset = 0;
    const SPOTS_PER_PAGE = 12;

    // 초기 로드
    loadThemes();

    // 언어 변경 시 재로드
    window.addEventListener('langchange', () => {
        var langSelect = document.getElementById('lang-select');
        if (langSelect) langSelect.value = I18n.getLang();
        loadThemes();
        if (_currentThemeId) loadThemeDetail(_currentThemeId);
    });

    async function loadThemes() {
        try {
            var res = await fetch(API_BASE + '/themes?lang=' + I18n.getLang());
            var json = await res.json();
            if (!json.success || !json.data) return;

            var data = json.data;
            var current = data.current_season;
            var seasonConfig = SEASON_CONFIG[current] || SEASON_CONFIG.spring;

            // Hero banner
            var hero = document.getElementById('theme-hero');
            if (hero) {
                hero.style.background = seasonConfig.heroGradient;
            }
            var badge = document.getElementById('theme-season-badge');
            if (badge) {
                badge.textContent = seasonConfig.emoji + ' ' + seasonConfig.label;
            }

            var titleEl = document.getElementById('theme-hero-title');
            if (titleEl) {
                titleEl.textContent = seasonConfig.label + ' in Busan';
            }

            var subtitleEl = document.getElementById('theme-hero-subtitle');
            if (subtitleEl) {
                var subtitleMap = {
                    spring: '봄바람과 벚꽃이 어우러진 부산을 만나보세요',
                    summer: '시원한 바다와 함께하는 부산의 여름을 즐기세요',
                    fall: '형형색색 단풍으로 물든 부산의 가을을 걸어보세요',
                    winter: '따뜻한 온천과 겨울 바다의 매력을 느껴보세요',
                };
                subtitleEl.textContent = subtitleMap[current] || '부산의 계절에 맞는 최고의 여행 테마를 만나보세요';
            }

            // 계절 테마
            var seasonThemes = data.themes.filter(function(t) { return t.season === current; });
            renderSeasonThemes(seasonThemes);

            // 상시 테마
            var allThemes = data.themes.filter(function(t) { return t.season === 'all'; });
            renderAllThemes(allThemes);

        } catch (e) {
            console.warn('테마 로드 실패:', e);
            var seasonContainer = document.getElementById('theme-season-list');
            if (seasonContainer) seasonContainer.innerHTML = '<p class="theme-empty">테마를 불러올 수 없습니다</p>';
            var allContainer = document.getElementById('theme-all-list');
            if (allContainer) allContainer.innerHTML = '<p class="theme-empty">테마를 불러올 수 없습니다</p>';
        }
    }

    function _escapeHtml(str) {
        if (!str) return '';
        var div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    function renderSeasonThemes(themes) {
        var container = document.getElementById('theme-season-list');
        if (!container) return;

        if (!themes.length) {
            container.innerHTML = '<p class="theme-empty">현재 계절 테마가 없습니다</p>';
            return;
        }

        container.innerHTML = '';
        themes.forEach(function(t) {
            var card = document.createElement('div');
            card.className = 'theme-card theme-card--season';
            card.style.background = t.gradient;
            card.setAttribute('role', 'button');
            card.setAttribute('tabindex', '0');
            card.setAttribute('aria-label', t.name);

            card.innerHTML =
                '<div class="theme-card__overlay"></div>' +
                '<div class="theme-card__content">' +
                    '<span class="theme-card__icon">' + t.icon + '</span>' +
                    '<h3 class="theme-card__name">' + _escapeHtml(t.name) + '</h3>' +
                    '<p class="theme-card__desc">' + _escapeHtml(t.description) + '</p>' +
                    '<div class="theme-card__tags">' +
                        t.tags.map(function(tag) {
                            return '<span class="theme-card__tag">#' + _escapeHtml(tag) + '</span>';
                        }).join('') +
                    '</div>' +
                '</div>';

            card.addEventListener('click', function() {
                openThemeDetail(t.id);
            });
            card.addEventListener('keydown', function(e) {
                if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    openThemeDetail(t.id);
                }
            });

            container.appendChild(card);
        });
    }

    function renderAllThemes(themes) {
        var container = document.getElementById('theme-all-list');
        if (!container) return;

        if (!themes.length) {
            container.innerHTML = '<p class="theme-empty">상시 테마가 없습니다</p>';
            return;
        }

        container.innerHTML = '';
        themes.forEach(function(t) {
            var card = document.createElement('div');
            card.className = 'theme-card theme-card--compact';
            card.setAttribute('role', 'button');
            card.setAttribute('tabindex', '0');
            card.setAttribute('aria-label', t.name);

            card.innerHTML =
                '<div class="theme-card-compact__icon-wrap" style="background:' + t.gradient + '">' +
                    '<span class="theme-card-compact__icon">' + t.icon + '</span>' +
                '</div>' +
                '<div class="theme-card-compact__body">' +
                    '<h3 class="theme-card-compact__name">' + _escapeHtml(t.name) + '</h3>' +
                    '<p class="theme-card-compact__desc">' + _escapeHtml(t.description) + '</p>' +
                '</div>';

            card.addEventListener('click', function() {
                openThemeDetail(t.id);
            });
            card.addEventListener('keydown', function(e) {
                if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    openThemeDetail(t.id);
                }
            });

            container.appendChild(card);
        });
    }

    function openThemeDetail(themeId) {
        _currentThemeId = themeId;
        _currentOffset = 0;

        // 섹션 전환
        var seasonSection = document.getElementById('section-season-themes');
        var allSection = document.getElementById('section-all-themes');
        var detailSection = document.getElementById('theme-detail-section');

        if (seasonSection) seasonSection.closest('.home-section').style.display = 'none';
        if (allSection) allSection.closest('.home-section').style.display = 'none';
        if (detailSection) detailSection.style.display = '';

        loadThemeDetail(themeId);

        // 스크롤 위로
        window.scrollTo({ top: 0, behavior: 'smooth' });
    }

    async function loadThemeDetail(themeId) {
        var spotsContainer = document.getElementById('theme-detail-spots');
        if (_currentOffset === 0 && spotsContainer) {
            spotsContainer.innerHTML =
                '<div class="skeleton skeleton-popular"></div>' +
                '<div class="skeleton skeleton-popular"></div>';
        }

        try {
            var res = await fetch(
                API_BASE + '/themes/' + encodeURIComponent(themeId) +
                '?lang=' + I18n.getLang() +
                '&limit=' + SPOTS_PER_PAGE +
                '&offset=' + _currentOffset
            );
            var json = await res.json();
            if (!json.success || !json.data) return;

            var data = json.data;
            var theme = data.theme;

            // 헤더 업데이트
            var iconEl = document.getElementById('theme-detail-icon');
            if (iconEl) iconEl.textContent = theme.icon;

            var titleEl = document.getElementById('theme-detail-title');
            if (titleEl) titleEl.textContent = theme.name;

            var descEl = document.getElementById('theme-detail-desc');
            if (descEl) descEl.textContent = theme.description;

            // Hero gradient 업데이트
            var hero = document.getElementById('theme-hero');
            if (hero) hero.style.background = theme.gradient;

            // 태그
            var tagsEl = document.getElementById('theme-detail-tags');
            if (tagsEl) {
                tagsEl.innerHTML = theme.tags.map(function(tag) {
                    return '<span class="theme-detail-tag">#' + _escapeHtml(tag) + '</span>';
                }).join('');
            }

            // 관광지 리스트
            if (!spotsContainer) return;

            if (_currentOffset === 0) {
                spotsContainer.innerHTML = '';
            }

            var spots = data.spots;
            if (!spots || spots.length === 0) {
                if (_currentOffset === 0) {
                    spotsContainer.innerHTML = '<p class="theme-empty">이 테마에 맞는 관광지가 아직 없습니다</p>';
                }
                var moreBtn = document.getElementById('theme-detail-more');
                if (moreBtn) moreBtn.style.display = 'none';
                return;
            }

            spots.forEach(function(spot) {
                var card = document.createElement('a');
                card.className = 'theme-spot-card';
                card.href = '/detail.html?id=' + encodeURIComponent(spot.id);

                var imgHtml = spot.thumbnail_url
                    ? '<img src="' + _escapeHtml(spot.thumbnail_url) + '" alt="' + _escapeHtml(spot.name) + '" class="theme-spot-card__img" loading="lazy">'
                    : '<div class="theme-spot-card__img-placeholder">' + _categoryEmoji(spot.category) + '</div>';

                var catLabel = _categoryLabel(spot.category);

                card.innerHTML =
                    '<div class="theme-spot-card__image">' + imgHtml + '</div>' +
                    '<div class="theme-spot-card__body">' +
                        '<span class="theme-spot-card__cat">' + _escapeHtml(catLabel) + '</span>' +
                        '<h3 class="theme-spot-card__name">' + _escapeHtml(spot.name) + '</h3>' +
                        (spot.address ? '<p class="theme-spot-card__address">' + _escapeHtml(spot.address) + '</p>' : '') +
                    '</div>';

                spotsContainer.appendChild(card);
            });

            // 더 보기 버튼
            var total = json.meta && json.meta.total ? json.meta.total : 0;
            var moreBtn = document.getElementById('theme-detail-more');
            if (moreBtn) {
                if (_currentOffset + SPOTS_PER_PAGE < total) {
                    moreBtn.style.display = '';
                } else {
                    moreBtn.style.display = 'none';
                }
            }

        } catch (e) {
            console.warn('테마 상세 로드 실패:', e);
            if (spotsContainer) spotsContainer.innerHTML = '<p class="theme-empty">관광지 정보를 불러올 수 없습니다</p>';
        }
    }

    // 뒤로 가기 버튼
    var backBtn = document.getElementById('theme-detail-back');
    if (backBtn) {
        backBtn.addEventListener('click', function() {
            _currentThemeId = null;
            _currentOffset = 0;

            var seasonSection = document.getElementById('section-season-themes');
            var allSection = document.getElementById('section-all-themes');
            var detailSection = document.getElementById('theme-detail-section');

            if (seasonSection) seasonSection.closest('.home-section').style.display = '';
            if (allSection) allSection.closest('.home-section').style.display = '';
            if (detailSection) detailSection.style.display = 'none';

            // 히어로 원래 색 복구
            loadThemes();
        });
    }

    // 더 보기 버튼
    var moreBtn = document.getElementById('theme-detail-more');
    if (moreBtn) {
        moreBtn.addEventListener('click', function() {
            if (!_currentThemeId) return;
            _currentOffset += SPOTS_PER_PAGE;
            loadThemeDetail(_currentThemeId);
        });
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

    // URL 파라미터로 특정 테마 바로 열기
    var urlParams = new URLSearchParams(window.location.search);
    var themeParam = urlParams.get('id');
    if (themeParam) {
        // 약간 딜레이 후 열기 (로드 완료 대기)
        setTimeout(function() {
            openThemeDetail(themeParam);
        }, 300);
    }
})();
