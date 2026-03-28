/**
 * favorites-page.js — 저장한 관광지 + 내 코스 페이지 로직
 */
(async () => {
    const API_BASE = '/api/v1';
    const COURSE_STORAGE_KEY = 'hello_busan_courses';

    try { await I18n.init(); } catch(e) { console.warn('I18n init failed:', e); }

    // ===== Tab Management =====
    const tabFavorites = document.getElementById('fav-tab-favorites');
    const tabCourses = document.getElementById('fav-tab-courses');
    const contentFavorites = document.getElementById('fav-content-favorites');
    const contentCourses = document.getElementById('fav-content-courses');

    if (!tabFavorites || !tabCourses) {
        console.error('Tab elements not found');
        return;
    }

    let activeTab = 'favorites';

    // Check URL param for initial tab
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('tab') === 'courses') {
        activeTab = 'courses';
    }

    function switchTab(tab) {
        activeTab = tab;

        // Update tab buttons
        tabFavorites.classList.toggle('fav-tab--active', tab === 'favorites');
        tabCourses.classList.toggle('fav-tab--active', tab === 'courses');

        // Update content visibility
        contentFavorites.style.display = tab === 'favorites' ? '' : 'none';
        contentCourses.style.display = tab === 'courses' ? '' : 'none';

        // Update URL without reload
        const url = new URL(window.location);
        if (tab === 'courses') {
            url.searchParams.set('tab', 'courses');
        } else {
            url.searchParams.delete('tab');
        }
        history.replaceState(null, '', url.toString());

        // Load content
        if (tab === 'favorites') {
            loadFavorites();
        } else {
            renderCourseList();
        }
    }

    tabFavorites.addEventListener('click', () => switchTab('favorites'));
    tabCourses.addEventListener('click', () => switchTab('courses'));

    // Init
    switchTab(activeTab);

    window.addEventListener('langchange', () => {
        if (activeTab === 'favorites') {
            loadFavorites();
        } else {
            renderCourseList();
        }
    });

    window.addEventListener('favorites-changed', () => {
        if (activeTab === 'favorites') {
            loadFavorites();
        }
    });

    // ===== Favorites Tab =====
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
            card.href = `/detail.html?id=${encodeURIComponent(id)}`;
            card.innerHTML = `
                <div class="spot-card__thumb"><div class="spot-card__thumb-placeholder">&#x1F30A;</div></div>
                <div class="spot-card__body">
                    <div class="spot-card__name">ID: ${_escapeHtml(String(id))}</div>
                </div>
                <button class="favorite-btn favorite-btn--active" data-spot-id="${_escapeHtml(String(id))}" aria-label="${I18n.t('favorite_remove')}" type="button">
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

    // ===== Courses Tab =====
    function _loadCourses() {
        try {
            const raw = localStorage.getItem(COURSE_STORAGE_KEY);
            return raw ? JSON.parse(raw) : [];
        } catch (e) {
            return [];
        }
    }

    function _haversine(lat1, lng1, lat2, lng2) {
        const R = 6371;
        const dLat = (lat2 - lat1) * Math.PI / 180;
        const dLng = (lng2 - lng1) * Math.PI / 180;
        const a = Math.sin(dLat / 2) ** 2 +
                  Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
                  Math.sin(dLng / 2) ** 2;
        return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    }

    function _calcTotalDistance(course) {
        let total = 0;
        (course.days || []).forEach(day => {
            const spots = (day.spots || []).filter(s => s.lat != null && s.lng != null);
            for (let i = 1; i < spots.length; i++) {
                total += _haversine(spots[i - 1].lat, spots[i - 1].lng, spots[i].lat, spots[i].lng);
            }
        });
        return total;
    }

    function renderCourseList() {
        const container = document.getElementById('courses-list');
        if (!container) return;

        const courses = _loadCourses();

        if (courses.length === 0) {
            container.innerHTML = `
                <div class="courses-empty">
                    <div class="courses-empty__icon">&#x1F5FA;</div>
                    <div class="courses-empty__text">${_escapeHtml(I18n.t('courses_empty_text'))}</div>
                    <a href="/course.html" class="courses-new-btn">
                        <span aria-hidden="true">+</span>
                        <span>${_escapeHtml(I18n.t('courses_create_new'))}</span>
                    </a>
                </div>
            `;
            return;
        }

        // Sort by most recently updated
        const sorted = [...courses].sort((a, b) => (b.updatedAt || 0) - (a.updatedAt || 0));

        let html = `
            <div class="courses-list__header">
                <a href="/course.html" class="courses-new-btn">
                    <span aria-hidden="true">+</span>
                    <span>${_escapeHtml(I18n.t('courses_create_new'))}</span>
                </a>
            </div>
        `;

        sorted.forEach(course => {
            const totalSpots = (course.days || []).reduce((sum, d) => sum + (d.spots || []).length, 0);
            const dayCount = (course.days || []).length;
            const totalDist = _calcTotalDistance(course);
            const title = _escapeHtml(course.title || I18n.t('cb_untitled'));
            const distText = totalDist > 0 ? ` / ${totalDist.toFixed(1)}km` : '';

            html += `
                <a href="/course.html?edit=${encodeURIComponent(course.id)}" class="fav-course-card">
                    <div class="fav-course-card__icon">&#x1F4CB;</div>
                    <div class="fav-course-card__body">
                        <div class="fav-course-card__name">${title}</div>
                        <div class="fav-course-card__meta">
                            <span>${dayCount}${_escapeHtml(I18n.t('cb_day_unit'))}</span>
                            <span>${totalSpots}${_escapeHtml(I18n.t('cb_spot_unit'))}</span>
                            ${distText ? `<span>${distText}</span>` : ''}
                        </div>
                    </div>
                    <div class="fav-course-card__arrow">&#x276F;</div>
                </a>
            `;
        });

        container.innerHTML = html;
    }

    // ===== Helpers =====
    function _escapeHtml(str) {
        if (!str) return '';
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
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
