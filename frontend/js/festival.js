/**
 * festival.js — Festival Calendar Page
 * Calendar grid view + list view with category filtering
 */
(async function () {
    var API_BASE = '/api/v1';

    // i18n init
    if (typeof I18n !== 'undefined') await I18n.init();

    var now = new Date();
    var currentYear = now.getFullYear();
    var currentMonth = now.getMonth() + 1;
    var currentCategory = 'all';
    var currentView = 'calendar'; // 'calendar' | 'list'
    var allFestivals = [];

    // DOM refs
    var calendarEl = document.getElementById('festival-calendar');
    var listviewEl = document.getElementById('festival-listview');
    var gridEl = document.getElementById('fp-calendar-grid');
    var weekdaysEl = document.getElementById('fp-weekdays');
    var listItemsEl = document.getElementById('fp-list-items');
    var listEmptyEl = document.getElementById('fp-list-empty');
    var monthLabel = document.getElementById('fp-month-label');
    var prevBtn = document.getElementById('fp-prev-month');
    var nextBtn = document.getElementById('fp-next-month');
    var todayBtn = document.getElementById('fp-today-btn');
    var calendarViewBtn = document.getElementById('btn-calendar-view');
    var listViewBtn = document.getElementById('btn-list-view');
    var catBtns = document.querySelectorAll('.festival-cat-btn');
    var modal = document.getElementById('fp-modal');
    var modalBackdrop = document.getElementById('fp-modal-backdrop');
    var modalClose = document.getElementById('fp-modal-close');
    var modalBody = document.getElementById('fp-modal-body');

    // URL param: open detail for specific festival
    var urlParams = new URLSearchParams(window.location.search);
    var openFestivalId = urlParams.get('id');

    // ─── Event Listeners ───

    if (prevBtn) prevBtn.addEventListener('click', function () { changeMonth(-1); });
    if (nextBtn) nextBtn.addEventListener('click', function () { changeMonth(1); });
    if (todayBtn) todayBtn.addEventListener('click', function () {
        currentYear = now.getFullYear();
        currentMonth = now.getMonth() + 1;
        refresh();
    });

    if (calendarViewBtn) calendarViewBtn.addEventListener('click', function () {
        if (currentView === 'calendar') return;
        currentView = 'calendar';
        calendarViewBtn.classList.add('festival-view-btn--active');
        listViewBtn.classList.remove('festival-view-btn--active');
        calendarEl.style.display = '';
        listviewEl.style.display = 'none';
    });

    if (listViewBtn) listViewBtn.addEventListener('click', function () {
        if (currentView === 'list') return;
        currentView = 'list';
        listViewBtn.classList.add('festival-view-btn--active');
        calendarViewBtn.classList.remove('festival-view-btn--active');
        calendarEl.style.display = 'none';
        listviewEl.style.display = '';
        renderListView();
    });

    catBtns.forEach(function (btn) {
        btn.addEventListener('click', function () {
            catBtns.forEach(function (b) { b.classList.remove('festival-cat-btn--active'); });
            btn.classList.add('festival-cat-btn--active');
            currentCategory = btn.dataset.category;
            renderCalendar();
            if (currentView === 'list') renderListView();
        });
    });

    // Modal
    if (modalClose) modalClose.addEventListener('click', closeModal);
    if (modalBackdrop) modalBackdrop.addEventListener('click', closeModal);
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && modal && modal.style.display !== 'none') {
            closeModal();
        }
    });

    // Lang change
    window.addEventListener('langchange', function () {
        renderWeekdays();
        updateMonthLabel();
        renderCalendar();
        if (currentView === 'list') renderListView();
    });

    // ─── Init ───
    renderWeekdays();
    updateMonthLabel();
    await loadFestivals();

    if (openFestivalId) {
        var fest = allFestivals.find(function (f) { return f.id === openFestivalId; });
        if (fest) openModal(fest);
    }

    // ─── Functions ───

    function changeMonth(delta) {
        currentMonth += delta;
        if (currentMonth > 12) { currentMonth = 1; currentYear++; }
        if (currentMonth < 1) { currentMonth = 12; currentYear--; }
        refresh();
    }

    function refresh() {
        updateMonthLabel();
        loadFestivals();
    }

    function _t(key) {
        return (typeof I18n !== 'undefined') ? I18n.t(key) : key;
    }

    function _escapeHtml(str) {
        if (!str) return '';
        var div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    function updateMonthLabel() {
        if (!monthLabel) return;
        var lang = (typeof I18n !== 'undefined') ? I18n.getLang() : 'ko';
        var monthNames = {
            ko: ['1월', '2월', '3월', '4월', '5월', '6월', '7월', '8월', '9월', '10월', '11월', '12월'],
            en: ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'],
            ja: ['1月', '2月', '3月', '4月', '5月', '6月', '7月', '8月', '9月', '10月', '11月', '12月'],
            zh: ['1月', '2月', '3月', '4月', '5月', '6月', '7月', '8月', '9月', '10月', '11月', '12月'],
            ru: ['Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь', 'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь'],
        };
        var names = monthNames[lang] || monthNames['ko'];
        monthLabel.textContent = currentYear + ' ' + names[currentMonth - 1];
    }

    function renderWeekdays() {
        if (!weekdaysEl) return;
        var lang = (typeof I18n !== 'undefined') ? I18n.getLang() : 'ko';
        var weekdays = {
            ko: ['일', '월', '화', '수', '목', '금', '토'],
            en: ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'],
            ja: ['日', '月', '火', '水', '木', '金', '土'],
            zh: ['日', '一', '二', '三', '四', '五', '六'],
            ru: ['Вс', 'Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб'],
        };
        var days = weekdays[lang] || weekdays['ko'];
        weekdaysEl.innerHTML = '';
        days.forEach(function (d, i) {
            var el = document.createElement('div');
            el.className = 'festival-calendar__weekday';
            if (i === 0) el.classList.add('festival-calendar__weekday--sun');
            if (i === 6) el.classList.add('festival-calendar__weekday--sat');
            el.textContent = d;
            weekdaysEl.appendChild(el);
        });
    }

    async function loadFestivals() {
        try {
            var params = new URLSearchParams({
                year: String(currentYear),
                month: String(currentMonth),
                limit: '100',
            });
            var res = await fetch(API_BASE + '/festivals?' + params);
            var json = await res.json();
            if (json.success && Array.isArray(json.data)) {
                allFestivals = json.data;
            } else {
                allFestivals = [];
            }
        } catch (e) {
            console.warn('Festival load failed:', e);
            allFestivals = [];
        }
        renderCalendar();
        if (currentView === 'list') renderListView();
    }

    function getFilteredFestivals() {
        if (currentCategory === 'all') return allFestivals;
        return allFestivals.filter(function (f) { return f.category === currentCategory; });
    }

    function renderCalendar() {
        if (!gridEl) return;
        gridEl.innerHTML = '';

        var firstDay = new Date(currentYear, currentMonth - 1, 1).getDay();
        var daysInMonth = new Date(currentYear, currentMonth, 0).getDate();
        var todayStr = new Date().toISOString().split('T')[0];
        var festivals = getFilteredFestivals();

        // Empty cells before first day
        for (var i = 0; i < firstDay; i++) {
            var emptyCell = document.createElement('div');
            emptyCell.className = 'festival-calendar__cell festival-calendar__cell--empty';
            gridEl.appendChild(emptyCell);
        }

        // Day cells
        for (var day = 1; day <= daysInMonth; day++) {
            var dateStr = currentYear + '-' + String(currentMonth).padStart(2, '0') + '-' + String(day).padStart(2, '0');
            var cell = document.createElement('div');
            cell.className = 'festival-calendar__cell';

            var dayOfWeek = (firstDay + day - 1) % 7;
            if (dayOfWeek === 0) cell.classList.add('festival-calendar__cell--sun');
            if (dayOfWeek === 6) cell.classList.add('festival-calendar__cell--sat');
            if (dateStr === todayStr) cell.classList.add('festival-calendar__cell--today');

            var dayNum = document.createElement('span');
            dayNum.className = 'festival-calendar__day';
            dayNum.textContent = day;
            cell.appendChild(dayNum);

            // Find festivals that span this date
            var dayFestivals = festivals.filter(function (f) {
                return f.start_date <= dateStr && f.end_date >= dateStr;
            });

            if (dayFestivals.length > 0) {
                cell.classList.add('festival-calendar__cell--has-event');
                var dotsContainer = document.createElement('div');
                dotsContainer.className = 'festival-calendar__dots';

                var maxDots = 3;
                dayFestivals.slice(0, maxDots).forEach(function (f) {
                    var dot = document.createElement('span');
                    dot.className = 'festival-calendar__dot festival-calendar__dot--' + _categoryClass(f.category);
                    dot.title = f.name;
                    dotsContainer.appendChild(dot);
                });

                if (dayFestivals.length > maxDots) {
                    var more = document.createElement('span');
                    more.className = 'festival-calendar__dot-more';
                    more.textContent = '+' + (dayFestivals.length - maxDots);
                    dotsContainer.appendChild(more);
                }

                cell.appendChild(dotsContainer);

                // Click to show day's festivals
                (function (df, ds) {
                    cell.addEventListener('click', function () {
                        if (df.length === 1) {
                            openModal(df[0]);
                        } else {
                            _showDayFestivals(ds, df);
                        }
                    });
                })(dayFestivals, dateStr);
            }

            gridEl.appendChild(cell);
        }
    }

    function _showDayFestivals(dateStr, festivals) {
        if (!modal || !modalBody) return;
        var html = '<h2 class="fp-modal__title" id="fp-modal-title">' + _escapeHtml(dateStr.replace(/-/g, '.')) + '</h2>';
        html += '<div class="fp-modal__day-list">';
        festivals.forEach(function (f) {
            var catClass = _categoryClass(f.category);
            html += '<div class="fp-modal__day-item fp-modal__day-item--' + catClass + '" data-id="' + _escapeHtml(f.id) + '">' +
                '<span class="fp-modal__day-cat">' + _escapeHtml(f.category) + '</span>' +
                '<span class="fp-modal__day-name">' + _escapeHtml(f.name) + '</span>' +
            '</div>';
        });
        html += '</div>';

        modalBody.innerHTML = html;
        modal.style.display = '';
        document.body.style.overflow = 'hidden';

        // Click individual festival from day list
        modalBody.querySelectorAll('.fp-modal__day-item').forEach(function (item) {
            item.addEventListener('click', function () {
                var fId = item.dataset.id;
                var fest = festivals.find(function (f) { return f.id === fId; });
                if (fest) openModal(fest);
            });
        });
    }

    function renderListView() {
        if (!listItemsEl) return;
        var festivals = getFilteredFestivals();

        if (festivals.length === 0) {
            listItemsEl.innerHTML = '';
            if (listEmptyEl) listEmptyEl.style.display = '';
            return;
        }
        if (listEmptyEl) listEmptyEl.style.display = 'none';

        var todayStr = new Date().toISOString().split('T')[0];

        // Sort: ongoing first, then upcoming, then ended
        var sorted = festivals.slice().sort(function (a, b) {
            var order = { ongoing: 0, upcoming: 1, ended: 2, unknown: 3 };
            var diff = (order[a.status] || 3) - (order[b.status] || 3);
            if (diff !== 0) return diff;
            return (a.start_date || '').localeCompare(b.start_date || '');
        });

        listItemsEl.innerHTML = '';
        sorted.forEach(function (f, idx) {
            var card = document.createElement('div');
            card.className = 'fp-list-card';
            card.style.animationDelay = (idx * 0.06) + 's';

            var catClass = _categoryClass(f.category);
            var statusClass = 'fp-list-card__status--' + (f.status || 'unknown');
            var statusText = _statusLabel(f.status);
            var dateRange = _formatDateRange(f.start_date, f.end_date);
            var safeName = _escapeHtml(f.name);
            var safeLocation = _escapeHtml(f.location || '');

            var thumb = (f.images && f.images.length > 0) ? f.images[0] : '';
            var imgHtml = thumb
                ? '<img src="' + _escapeHtml(thumb) + '" alt="' + safeName + '" class="fp-list-card__img" loading="lazy">'
                : '<div class="fp-list-card__img-placeholder">&#x1F389;</div>';

            // D-day
            var dDay = f.d_day;
            var ddayHtml = '';
            if (dDay === 0 || (dDay === null && f.status === 'ongoing')) {
                ddayHtml = '<span class="fp-list-card__dday fp-list-card__dday--ongoing">' + (_t('festival_ongoing') || '진행 중') + '</span>';
            } else if (dDay != null && dDay > 0) {
                ddayHtml = '<span class="fp-list-card__dday fp-list-card__dday--upcoming">D-' + dDay + '</span>';
            }

            card.innerHTML =
                '<div class="fp-list-card__image">' +
                    imgHtml +
                    '<span class="fp-list-card__cat-badge fp-list-card__cat-badge--' + catClass + '">' + _escapeHtml(f.category) + '</span>' +
                '</div>' +
                '<div class="fp-list-card__body">' +
                    '<div class="fp-list-card__top">' +
                        '<h3 class="fp-list-card__name">' + safeName + '</h3>' +
                        ddayHtml +
                    '</div>' +
                    '<p class="fp-list-card__date">&#x1F4C5; ' + _escapeHtml(dateRange) + '</p>' +
                    (safeLocation ? '<p class="fp-list-card__location">&#x1F4CD; ' + safeLocation + '</p>' : '') +
                '</div>';

            card.addEventListener('click', function () { openModal(f); });
            card.setAttribute('role', 'button');
            card.setAttribute('tabindex', '0');
            card.addEventListener('keydown', function (e) {
                if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    openModal(f);
                }
            });

            listItemsEl.appendChild(card);
        });
    }

    function openModal(festival) {
        if (!modal || !modalBody) return;

        var safeName = _escapeHtml(festival.name);
        var safeDesc = _escapeHtml(festival.description || '').replace(/\n/g, '<br>');
        var safeLocation = _escapeHtml(festival.location || '');
        var safeAddress = _escapeHtml(festival.address || '');
        var dateRange = _formatDateRange(festival.start_date, festival.end_date);
        var catClass = _categoryClass(festival.category);

        var images = festival.images || [];
        var imgHtml = '';
        if (images.length > 0) {
            imgHtml = '<img src="' + _escapeHtml(images[0]) + '" alt="' + safeName + '" class="fp-modal__img">';
        }

        // D-day badge
        var dDay = festival.d_day;
        var ddayHtml = '';
        if (dDay === 0 || (dDay === null && festival.status === 'ongoing')) {
            ddayHtml = '<span class="fp-modal__dday fp-modal__dday--ongoing">' + (_t('festival_ongoing') || '진행 중') + '</span>';
        } else if (dDay != null && dDay > 0) {
            ddayHtml = '<span class="fp-modal__dday fp-modal__dday--upcoming">D-' + dDay + '</span>';
        } else if (festival.status === 'ended') {
            ddayHtml = '<span class="fp-modal__dday fp-modal__dday--ended">' + (_t('festival_ended') || '종료') + '</span>';
        }

        var tagsHtml = '';
        if (festival.tags && festival.tags.length > 0) {
            tagsHtml = '<div class="fp-modal__tags">';
            festival.tags.forEach(function (tag) {
                tagsHtml += '<span class="fp-modal__tag">#' + _escapeHtml(tag) + '</span>';
            });
            tagsHtml += '</div>';
        }

        var html = imgHtml +
            '<div class="fp-modal__header-row">' +
                '<h2 class="fp-modal__title" id="fp-modal-title">' + safeName + '</h2>' +
                ddayHtml +
            '</div>' +
            '<span class="fp-modal__cat fp-modal__cat--' + catClass + '">' + _escapeHtml(festival.category) + '</span>' +
            '<div class="fp-modal__info">' +
                '<p>&#x1F4C5; ' + _escapeHtml(dateRange) + '</p>' +
                (safeLocation ? '<p>&#x1F4CD; ' + safeLocation + '</p>' : '') +
                (safeAddress ? '<p>&#x1F3E0; ' + safeAddress + '</p>' : '') +
            '</div>';

        if (safeDesc) {
            html += '<div class="fp-modal__desc">' + safeDesc + '</div>';
        }

        html += tagsHtml;

        if (festival.lat != null && festival.lng != null) {
            html += '<a class="fp-modal__map-link" href="/map.html?lat=' + festival.lat + '&lng=' + festival.lng + '&zoom=15" target="_blank">' +
                '&#x1F5FA; ' + (_t('detail_location') || '지도에서 보기') +
            '</a>';
        }

        modalBody.innerHTML = html;
        modal.style.display = '';
        document.body.style.overflow = 'hidden';
        document.body.style.position = 'fixed';
        document.body.style.width = '100%';
        document.body.dataset.scrollY = String(window.scrollY);
        document.body.style.top = '-' + window.scrollY + 'px';

        if (modalClose) modalClose.focus();
    }

    function closeModal() {
        if (!modal) return;
        modal.style.display = 'none';
        var scrollY = parseInt(document.body.dataset.scrollY || '0', 10);
        document.body.style.overflow = '';
        document.body.style.position = '';
        document.body.style.width = '';
        document.body.style.top = '';
        window.scrollTo(0, scrollY);
    }

    // ─── Helpers ───

    function _categoryClass(cat) {
        var map = { '축제': 'festival', '공연': 'performance', '전시': 'exhibition', '체험': 'experience' };
        return map[cat] || 'festival';
    }

    function _statusLabel(status) {
        var map = {
            ongoing: _t('festival_status_ongoing') || '진행 중',
            upcoming: _t('festival_status_upcoming') || '예정',
            ended: _t('festival_status_ended') || '종료',
        };
        return map[status] || '';
    }

    function _formatDateRange(start, end) {
        if (!start && !end) return '';
        var s = start ? start.replace(/-/g, '.') : '?';
        var e = end ? end.replace(/-/g, '.') : '?';
        if (s === e) return s;
        return s + ' ~ ' + e;
    }
})();
