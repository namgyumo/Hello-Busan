/**
 * course-builder.js — 코스 빌더 (여행 일정 생성) 페이지
 * localStorage 기반 CRUD + 서버 동선 최적화
 */
(async () => {
    const API_BASE = '/api/v1';
    const STORAGE_KEY = 'hello_busan_courses';

    if (typeof Analytics !== 'undefined') Analytics.init();
    await I18n.init();

    // ===== State =====
    let courses = _loadCourses();
    let currentCourseId = null;
    let currentDay = 1;
    let searchDebounce = null;

    // Check if opened from detail page with spot to add
    const urlParams = new URLSearchParams(window.location.search);
    const addSpotId = urlParams.get('addSpot');

    // ===== DOM refs =====
    const listView = document.getElementById('cb-list-view');
    const editorView = document.getElementById('cb-editor-view');
    const courseListEl = document.getElementById('cb-course-list');
    const spotListEl = document.getElementById('cb-spot-list');
    const dayTabsEl = document.getElementById('cb-day-tabs');
    const titleInput = document.getElementById('cb-course-title');
    const distanceInfo = document.getElementById('cb-distance-info');
    const distanceValue = document.getElementById('cb-distance-value');
    const modalOverlay = document.getElementById('cb-modal-overlay');
    const searchInput = document.getElementById('cb-search-input');
    const searchResults = document.getElementById('cb-search-results');

    // ===== Event Listeners =====
    document.getElementById('cb-new-course-btn').addEventListener('click', _createNewCourse);
    document.getElementById('cb-back-btn').addEventListener('click', _backToList);
    document.getElementById('cb-add-day-btn').addEventListener('click', _addDay);
    document.getElementById('cb-add-spot-btn').addEventListener('click', _openModal);
    document.getElementById('cb-optimize-btn').addEventListener('click', _optimizeRoute);
    document.getElementById('cb-delete-day-btn').addEventListener('click', _deleteCurrentDay);
    document.getElementById('cb-modal-close').addEventListener('click', _closeModal);
    modalOverlay.addEventListener('click', (e) => {
        if (e.target === modalOverlay) _closeModal();
    });

    searchInput.addEventListener('input', () => {
        clearTimeout(searchDebounce);
        searchDebounce = setTimeout(() => _searchSpots(searchInput.value.trim()), 300);
    });

    titleInput.addEventListener('input', () => {
        if (!currentCourseId) return;
        const course = _getCourse(currentCourseId);
        if (course) {
            course.title = titleInput.value;
            course.updatedAt = Date.now();
            _saveCourses();
        }
    });

    // Language change
    window.addEventListener('langchange', () => {
        const langSelect = document.getElementById('lang-select');
        if (langSelect) langSelect.value = I18n.getLang();
        if (currentCourseId) {
            _renderEditor();
        } else {
            _renderCourseList();
        }
    });

    // ===== Init =====
    if (addSpotId) {
        _handleAddFromDetail(addSpotId);
    } else {
        _renderCourseList();
    }

    // ===== localStorage helpers =====
    function _loadCourses() {
        try {
            const raw = localStorage.getItem(STORAGE_KEY);
            return raw ? JSON.parse(raw) : [];
        } catch (e) {
            return [];
        }
    }

    function _saveCourses() {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(courses));
    }

    function _getCourse(id) {
        return courses.find(c => c.id === id) || null;
    }

    function _generateId() {
        return 'course_' + Date.now() + '_' + Math.random().toString(36).slice(2, 8);
    }

    // ===== Course List View =====
    function _renderCourseList() {
        listView.style.display = '';
        editorView.style.display = 'none';
        currentCourseId = null;

        if (courses.length === 0) {
            courseListEl.innerHTML = `
                <div class="cb-empty">
                    <div class="cb-empty__icon">&#x1F5FA;</div>
                    <div class="cb-empty__text" data-i18n="cb_empty_text">아직 만든 코스가 없습니다.<br>새 코스를 만들어보세요!</div>
                </div>
            `;
            I18n.applyTo(courseListEl);
            return;
        }

        courseListEl.innerHTML = '';
        // Sort by most recently updated
        const sorted = [...courses].sort((a, b) => (b.updatedAt || 0) - (a.updatedAt || 0));

        sorted.forEach(course => {
            const totalSpots = (course.days || []).reduce((sum, d) => sum + (d.spots || []).length, 0);
            const dayCount = (course.days || []).length;

            const card = document.createElement('div');
            card.className = 'cb-course-card';
            card.innerHTML = `
                <div class="cb-course-card__icon">&#x1F4CB;</div>
                <div class="cb-course-card__body">
                    <div class="cb-course-card__name">${_escapeHtml(course.title || I18n.t('cb_untitled'))}</div>
                    <div class="cb-course-card__meta">${dayCount}${I18n.t('cb_day_unit')} / ${totalSpots}${I18n.t('cb_spot_unit')}</div>
                </div>
                <button class="cb-course-card__delete" data-id="${course.id}" aria-label="${I18n.t('cb_delete')}" title="${I18n.t('cb_delete')}">&#x1F5D1;</button>
            `;
            card.addEventListener('click', (e) => {
                if (e.target.closest('.cb-course-card__delete')) return;
                _openCourse(course.id);
            });
            card.querySelector('.cb-course-card__delete').addEventListener('click', (e) => {
                e.stopPropagation();
                _deleteCourse(course.id);
            });
            courseListEl.appendChild(card);
        });
    }

    function _createNewCourse() {
        const course = {
            id: _generateId(),
            title: '',
            days: [{ day: 1, spots: [] }],
            createdAt: Date.now(),
            updatedAt: Date.now(),
        };
        courses.push(course);
        _saveCourses();
        _openCourse(course.id);
    }

    function _openCourse(id) {
        currentCourseId = id;
        currentDay = 1;
        listView.style.display = 'none';
        editorView.style.display = '';
        _renderEditor();
    }

    function _backToList() {
        // Clean up empty untitled courses
        const course = _getCourse(currentCourseId);
        if (course) {
            const totalSpots = course.days.reduce((sum, d) => sum + d.spots.length, 0);
            if (!course.title && totalSpots === 0) {
                courses = courses.filter(c => c.id !== currentCourseId);
                _saveCourses();
            }
        }
        _renderCourseList();
    }

    function _deleteCourse(id) {
        courses = courses.filter(c => c.id !== id);
        _saveCourses();
        if (currentCourseId === id) {
            _renderCourseList();
        } else {
            _renderCourseList();
        }
        _showToast(I18n.t('cb_course_deleted'));
    }

    // ===== Editor View =====
    function _renderEditor() {
        const course = _getCourse(currentCourseId);
        if (!course) return _renderCourseList();

        titleInput.value = course.title || '';
        _renderDayTabs(course);
        _renderSpotList(course);
        _updateDistance(course);
        _updateOptimizeBtn(course);
    }

    function _renderDayTabs(course) {
        const addBtn = document.getElementById('cb-add-day-btn');
        // Remove all day tabs (keep only the add button)
        dayTabsEl.innerHTML = '';

        course.days.forEach(d => {
            const tab = document.createElement('button');
            tab.className = 'cb-day-tab' + (d.day === currentDay ? ' cb-day-tab--active' : '');
            tab.dataset.day = d.day;
            tab.textContent = 'Day ' + d.day;
            tab.addEventListener('click', () => {
                currentDay = d.day;
                _renderEditor();
            });
            dayTabsEl.appendChild(tab);
        });

        // Re-add the + button
        const newAddBtn = document.createElement('button');
        newAddBtn.className = 'cb-day-tab cb-day-tab--add';
        newAddBtn.id = 'cb-add-day-btn';
        newAddBtn.setAttribute('aria-label', '일차 추가');
        newAddBtn.textContent = '+';
        newAddBtn.addEventListener('click', _addDay);
        dayTabsEl.appendChild(newAddBtn);
    }

    function _renderSpotList(course) {
        const dayData = course.days.find(d => d.day === currentDay);
        if (!dayData || dayData.spots.length === 0) {
            spotListEl.innerHTML = '';
            spotListEl.className = 'cb-spot-list--empty';
            spotListEl.textContent = I18n.t('cb_drag_hint');
            return;
        }

        spotListEl.className = 'cb-spot-list';
        spotListEl.innerHTML = '';

        dayData.spots.forEach((spot, idx) => {
            const el = document.createElement('div');
            el.className = 'cb-spot';
            el.draggable = true;
            el.dataset.index = idx;

            const thumbHtml = spot.thumbnail_url
                ? `<img class="cb-spot__thumb" src="${_escapeHtml(spot.thumbnail_url)}" alt="" loading="lazy">`
                : `<div class="cb-spot__thumb--empty">&#x1F30A;</div>`;

            el.innerHTML = `
                <div class="cb-spot__order">${idx + 1}</div>
                ${thumbHtml}
                <div class="cb-spot__info">
                    <div class="cb-spot__name">${_escapeHtml(spot.name)}</div>
                    <div class="cb-spot__cat">${_categoryLabel(spot.category)}</div>
                </div>
                <button class="cb-spot__remove" data-index="${idx}" aria-label="${I18n.t('cb_remove')}">&#x2715;</button>
            `;

            // Remove button
            el.querySelector('.cb-spot__remove').addEventListener('click', (e) => {
                e.stopPropagation();
                _removeSpot(idx);
            });

            // Drag & Drop
            el.addEventListener('dragstart', _onDragStart);
            el.addEventListener('dragover', _onDragOver);
            el.addEventListener('dragenter', _onDragEnter);
            el.addEventListener('dragleave', _onDragLeave);
            el.addEventListener('drop', _onDrop);
            el.addEventListener('dragend', _onDragEnd);

            // Touch drag support
            el.addEventListener('touchstart', _onTouchStart, { passive: false });
            el.addEventListener('touchmove', _onTouchMove, { passive: false });
            el.addEventListener('touchend', _onTouchEnd);

            spotListEl.appendChild(el);
        });
    }

    // ===== Drag & Drop =====
    let dragIndex = null;

    function _onDragStart(e) {
        dragIndex = parseInt(e.currentTarget.dataset.index);
        e.currentTarget.classList.add('dragging');
        e.dataTransfer.effectAllowed = 'move';
        e.dataTransfer.setData('text/plain', dragIndex);
    }

    function _onDragOver(e) {
        e.preventDefault();
        e.dataTransfer.dropEffect = 'move';
    }

    function _onDragEnter(e) {
        e.preventDefault();
        const el = e.currentTarget;
        if (parseInt(el.dataset.index) !== dragIndex) {
            el.classList.add('drag-over');
        }
    }

    function _onDragLeave(e) {
        e.currentTarget.classList.remove('drag-over');
    }

    function _onDrop(e) {
        e.preventDefault();
        const fromIdx = dragIndex;
        const toIdx = parseInt(e.currentTarget.dataset.index);
        e.currentTarget.classList.remove('drag-over');

        if (fromIdx !== null && fromIdx !== toIdx) {
            _reorderSpot(fromIdx, toIdx);
        }
    }

    function _onDragEnd(e) {
        e.currentTarget.classList.remove('dragging');
        spotListEl.querySelectorAll('.cb-spot').forEach(el => el.classList.remove('drag-over'));
        dragIndex = null;
    }

    // ===== Touch Drag (mobile) =====
    let touchStartY = 0;
    let touchCurrentEl = null;
    let touchDragIdx = null;
    let touchClone = null;

    function _onTouchStart(e) {
        const el = e.currentTarget;
        touchDragIdx = parseInt(el.dataset.index);
        touchStartY = e.touches[0].clientY;
        touchCurrentEl = el;

        // Long press detection - need to hold briefly
        el._touchTimeout = setTimeout(() => {
            el.classList.add('dragging');
            // Create visual clone
            touchClone = el.cloneNode(true);
            touchClone.style.position = 'fixed';
            touchClone.style.zIndex = '9999';
            touchClone.style.pointerEvents = 'none';
            touchClone.style.opacity = '0.8';
            touchClone.style.width = el.offsetWidth + 'px';
            touchClone.style.left = el.getBoundingClientRect().left + 'px';
            touchClone.style.top = e.touches[0].clientY - el.offsetHeight / 2 + 'px';
            document.body.appendChild(touchClone);
        }, 200);
    }

    function _onTouchMove(e) {
        if (touchDragIdx === null || !touchClone) return;
        e.preventDefault();

        const touch = e.touches[0];
        touchClone.style.top = touch.clientY - touchClone.offsetHeight / 2 + 'px';

        // Find element under touch
        const allSpots = spotListEl.querySelectorAll('.cb-spot');
        allSpots.forEach(spot => {
            spot.classList.remove('drag-over');
            const rect = spot.getBoundingClientRect();
            if (touch.clientY >= rect.top && touch.clientY <= rect.bottom) {
                if (parseInt(spot.dataset.index) !== touchDragIdx) {
                    spot.classList.add('drag-over');
                }
            }
        });
    }

    function _onTouchEnd(e) {
        if (touchCurrentEl) {
            clearTimeout(touchCurrentEl._touchTimeout);
            touchCurrentEl.classList.remove('dragging');
        }

        if (touchClone) {
            // Find drop target
            const touch = e.changedTouches[0];
            const allSpots = spotListEl.querySelectorAll('.cb-spot');
            let dropIdx = null;
            allSpots.forEach(spot => {
                spot.classList.remove('drag-over');
                const rect = spot.getBoundingClientRect();
                if (touch.clientY >= rect.top && touch.clientY <= rect.bottom) {
                    dropIdx = parseInt(spot.dataset.index);
                }
            });

            if (dropIdx !== null && touchDragIdx !== null && dropIdx !== touchDragIdx) {
                _reorderSpot(touchDragIdx, dropIdx);
            }

            document.body.removeChild(touchClone);
            touchClone = null;
        }

        touchDragIdx = null;
        touchCurrentEl = null;
    }

    // ===== Spot Operations =====
    function _removeSpot(idx) {
        const course = _getCourse(currentCourseId);
        if (!course) return;
        const dayData = course.days.find(d => d.day === currentDay);
        if (!dayData) return;

        dayData.spots.splice(idx, 1);
        course.updatedAt = Date.now();
        _saveCourses();
        _renderEditor();
    }

    function _reorderSpot(fromIdx, toIdx) {
        const course = _getCourse(currentCourseId);
        if (!course) return;
        const dayData = course.days.find(d => d.day === currentDay);
        if (!dayData) return;

        const [moved] = dayData.spots.splice(fromIdx, 1);
        dayData.spots.splice(toIdx, 0, moved);
        course.updatedAt = Date.now();
        _saveCourses();
        _renderEditor();
    }

    function _addSpotToCourse(spotData) {
        const course = _getCourse(currentCourseId);
        if (!course) return;
        let dayData = course.days.find(d => d.day === currentDay);
        if (!dayData) {
            dayData = { day: currentDay, spots: [] };
            course.days.push(dayData);
        }

        // Prevent duplicate
        if (dayData.spots.some(s => s.id === spotData.id)) {
            _showToast(I18n.t('cb_already_added'));
            return;
        }

        dayData.spots.push({
            id: spotData.id,
            name: spotData.name,
            category: spotData.category || spotData.category_id || '',
            lat: spotData.lat,
            lng: spotData.lng,
            thumbnail_url: spotData.thumbnail_url || _getFirstImage(spotData),
        });

        course.updatedAt = Date.now();
        _saveCourses();
        _renderEditor();
        _showToast(I18n.t('cb_spot_added'));
    }

    function _getFirstImage(spot) {
        if (spot.images && Array.isArray(spot.images) && spot.images.length > 0) {
            return spot.images[0];
        }
        return '';
    }

    // ===== Day Operations =====
    function _addDay() {
        const course = _getCourse(currentCourseId);
        if (!course) return;

        const maxDay = Math.max(...course.days.map(d => d.day), 0);
        const newDay = maxDay + 1;
        course.days.push({ day: newDay, spots: [] });
        course.updatedAt = Date.now();
        currentDay = newDay;
        _saveCourses();
        _renderEditor();
    }

    function _deleteCurrentDay() {
        const course = _getCourse(currentCourseId);
        if (!course || course.days.length <= 1) {
            _showToast(I18n.t('cb_cannot_delete_last_day'));
            return;
        }

        course.days = course.days.filter(d => d.day !== currentDay);
        // Renumber days
        course.days.sort((a, b) => a.day - b.day);
        course.days.forEach((d, i) => { d.day = i + 1; });
        course.updatedAt = Date.now();

        currentDay = 1;
        _saveCourses();
        _renderEditor();
        _showToast(I18n.t('cb_day_deleted'));
    }

    // ===== Route Optimization =====
    async function _optimizeRoute() {
        const course = _getCourse(currentCourseId);
        if (!course) return;
        const dayData = course.days.find(d => d.day === currentDay);
        if (!dayData || dayData.spots.length < 2) return;

        const optimizeBtn = document.getElementById('cb-optimize-btn');
        if (optimizeBtn) optimizeBtn.disabled = true;

        try {
            const spots = dayData.spots
                .filter(s => s.lat != null && s.lng != null)
                .map(s => ({ id: s.id, name: s.name, lat: s.lat, lng: s.lng }));

            if (spots.length < 2) {
                _showToast(I18n.t('cb_need_coords'));
                return;
            }

            const res = await fetch(`${API_BASE}/course/optimize`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ spots }),
            });

            const json = await res.json();
            if (!json.success || !json.data || !json.data.ordered_spots) {
                _showToast(I18n.t('cb_optimize_failed'));
                return;
            }

            // Re-order spots based on optimize result
            const orderedIds = json.data.ordered_spots.map(s => s.id);
            const spotMap = {};
            dayData.spots.forEach(s => { spotMap[s.id] = s; });

            const newOrder = [];
            orderedIds.forEach(id => {
                if (spotMap[id]) newOrder.push(spotMap[id]);
            });
            // Add any spots that weren't in the optimization (missing coords)
            dayData.spots.forEach(s => {
                if (!orderedIds.includes(s.id)) newOrder.push(s);
            });

            dayData.spots = newOrder;
            course.updatedAt = Date.now();
            _saveCourses();
            _renderEditor();
            _showToast(I18n.t('cb_optimized'));
        } catch (e) {
            console.error('Optimize failed:', e);
            _showToast(I18n.t('cb_optimize_failed'));
        } finally {
            if (optimizeBtn) optimizeBtn.disabled = false;
        }
    }

    function _updateOptimizeBtn(course) {
        const btn = document.getElementById('cb-optimize-btn');
        if (!btn) return;
        const dayData = course.days.find(d => d.day === currentDay);
        btn.disabled = !dayData || dayData.spots.length < 2;
    }

    // ===== Distance Calculation =====
    function _updateDistance(course) {
        const dayData = course.days.find(d => d.day === currentDay);
        if (!dayData || dayData.spots.length < 2) {
            distanceInfo.style.display = 'none';
            return;
        }

        let totalDist = 0;
        const spots = dayData.spots.filter(s => s.lat != null && s.lng != null);
        for (let i = 1; i < spots.length; i++) {
            totalDist += _haversine(spots[i - 1].lat, spots[i - 1].lng, spots[i].lat, spots[i].lng);
        }

        distanceInfo.style.display = '';
        distanceValue.textContent = totalDist.toFixed(1) + ' km';
    }

    function _haversine(lat1, lng1, lat2, lng2) {
        const R = 6371;
        const dLat = (lat2 - lat1) * Math.PI / 180;
        const dLng = (lng2 - lng1) * Math.PI / 180;
        const a = Math.sin(dLat / 2) * Math.sin(dLat / 2) +
                  Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
                  Math.sin(dLng / 2) * Math.sin(dLng / 2);
        return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    }

    // ===== Search Modal =====
    function _openModal() {
        modalOverlay.classList.add('open');
        searchInput.value = '';
        searchResults.innerHTML = `<div class="cb-modal__loading" data-i18n="cb_search_hint">${I18n.t('cb_search_hint')}</div>`;
        setTimeout(() => searchInput.focus(), 300);
    }

    function _closeModal() {
        modalOverlay.classList.remove('open');
    }

    async function _searchSpots(query) {
        if (!query || query.length < 1) {
            searchResults.innerHTML = `<div class="cb-modal__loading">${I18n.t('cb_search_hint')}</div>`;
            return;
        }

        searchResults.innerHTML = `<div class="cb-modal__loading">${I18n.t('cb_searching')}</div>`;

        try {
            const res = await fetch(`${API_BASE}/spots?search=${encodeURIComponent(query)}&limit=20&lang=${I18n.getLang()}`);
            const json = await res.json();

            if (!json.success || !json.data || json.data.length === 0) {
                searchResults.innerHTML = `<div class="cb-modal__empty">${I18n.t('cb_no_results')}</div>`;
                return;
            }

            _renderSearchResults(json.data);
        } catch (e) {
            console.error('Search failed:', e);
            searchResults.innerHTML = `<div class="cb-modal__empty">${I18n.t('cb_search_error')}</div>`;
        }
    }

    function _renderSearchResults(spots) {
        searchResults.innerHTML = '';
        const course = _getCourse(currentCourseId);
        const dayData = course ? course.days.find(d => d.day === currentDay) : null;
        const existingIds = dayData ? dayData.spots.map(s => s.id) : [];

        spots.forEach(spot => {
            const id = String(spot.id);
            const alreadyAdded = existingIds.includes(id);
            const thumbUrl = spot.thumbnail_url || '';

            const el = document.createElement('div');
            el.className = 'cb-modal__spot';

            const thumbHtml = thumbUrl
                ? `<img class="cb-modal__spot-thumb" src="${_escapeHtml(thumbUrl)}" alt="" loading="lazy">`
                : `<div class="cb-modal__spot-thumb--empty">&#x1F30A;</div>`;

            el.innerHTML = `
                ${thumbHtml}
                <div class="cb-modal__spot-info">
                    <div class="cb-modal__spot-name">${_escapeHtml(spot.name)}</div>
                    <div class="cb-modal__spot-cat">${_categoryLabel(spot.category || spot.category_id)}</div>
                </div>
                ${alreadyAdded
                    ? `<span class="cb-modal__spot-added">&#x2713; ${I18n.t('cb_added')}</span>`
                    : `<button class="cb-modal__spot-add">${I18n.t('cb_add')}</button>`
                }
            `;

            if (!alreadyAdded) {
                el.querySelector('.cb-modal__spot-add').addEventListener('click', (e) => {
                    e.stopPropagation();
                    _addSpotToCourse({
                        id: id,
                        name: spot.name,
                        category: spot.category || spot.category_id || '',
                        lat: spot.lat,
                        lng: spot.lng,
                        thumbnail_url: thumbUrl,
                    });
                    // Update button to "added"
                    const btn = e.target;
                    btn.outerHTML = `<span class="cb-modal__spot-added">&#x2713; ${I18n.t('cb_added')}</span>`;
                });
            }

            searchResults.appendChild(el);
        });
    }

    // ===== Add from Detail Page =====
    async function _handleAddFromDetail(spotId) {
        // If no courses exist, create one
        if (courses.length === 0) {
            _createNewCourse();
        } else {
            // Open the most recently updated course
            const sorted = [...courses].sort((a, b) => (b.updatedAt || 0) - (a.updatedAt || 0));
            _openCourse(sorted[0].id);
        }

        // Fetch spot data and add
        try {
            const res = await fetch(`${API_BASE}/spots/${encodeURIComponent(spotId)}?lang=${I18n.getLang()}`);
            const json = await res.json();
            if (json.success && json.data) {
                const spot = json.data;
                _addSpotToCourse({
                    id: String(spot.id),
                    name: spot.name,
                    category: spot.category || '',
                    lat: spot.lat,
                    lng: spot.lng,
                    thumbnail_url: spot.images && spot.images.length > 0 ? spot.images[0] : '',
                });
            }
        } catch (e) {
            console.error('Failed to fetch spot for course:', e);
        }

        // Clean URL
        const url = new URL(window.location);
        url.searchParams.delete('addSpot');
        history.replaceState(null, '', url.toString());
    }

    // ===== Helpers =====
    function _categoryLabel(cat) {
        const labels = {
            nature: I18n.t('category_nature'),
            culture: I18n.t('category_culture'),
            food: I18n.t('category_food'),
            activity: I18n.t('category_activity'),
            shopping: I18n.t('category_shopping'),
            nightview: I18n.t('category_nightview'),
        };
        return labels[cat] || cat || '';
    }

    function _escapeHtml(str) {
        if (!str) return '';
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    function _showToast(msg) {
        const toast = document.getElementById('cb-toast');
        if (!toast) return;
        toast.textContent = msg;
        toast.classList.add('visible');
        setTimeout(() => toast.classList.remove('visible'), 2500);
    }
})();
