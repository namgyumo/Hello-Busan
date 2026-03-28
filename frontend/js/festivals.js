/**
 * festivals.js — Festival/Event Calendar Section
 */
(function () {
    const API_BASE = '/api/v1';

    let currentYear = new Date().getFullYear();
    let currentMonth = new Date().getMonth() + 1;
    let currentFilter = 'all';

    // DOM refs
    const listEl = document.getElementById('festival-list');
    const emptyEl = document.getElementById('festival-empty');
    const labelEl = document.getElementById('festival-month-label');
    const prevBtn = document.getElementById('festival-prev-month');
    const nextBtn = document.getElementById('festival-next-month');
    const filterBtns = document.querySelectorAll('.festival-filter-btn');
    const modal = document.getElementById('festival-modal');
    const modalBackdrop = document.getElementById('festival-modal-backdrop');
    const modalClose = document.getElementById('festival-modal-close');
    const modalBody = document.getElementById('festival-modal-body');

    if (!listEl) return;

    // Month navigation
    if (prevBtn) prevBtn.addEventListener('click', () => { changeMonth(-1); });
    if (nextBtn) nextBtn.addEventListener('click', () => { changeMonth(1); });

    // Status filter
    filterBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            filterBtns.forEach(b => b.classList.remove('festival-filter-btn--active'));
            btn.classList.add('festival-filter-btn--active');
            currentFilter = btn.dataset.status;
            loadFestivals();
        });
    });

    // Modal close
    if (modalClose) modalClose.addEventListener('click', closeFestivalModal);
    if (modalBackdrop) modalBackdrop.addEventListener('click', closeFestivalModal);
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && modal && modal.style.display !== 'none') {
            closeFestivalModal();
        }
    });

    // Language change re-render
    window.addEventListener('langchange', () => {
        updateMonthLabel();
        loadFestivals();
    });

    // Init
    updateMonthLabel();
    loadFestivals();

    function changeMonth(delta) {
        currentMonth += delta;
        if (currentMonth > 12) { currentMonth = 1; currentYear++; }
        if (currentMonth < 1) { currentMonth = 12; currentYear--; }
        updateMonthLabel();
        loadFestivals();
    }

    function updateMonthLabel() {
        if (!labelEl) return;
        var lang = (typeof I18n !== 'undefined') ? I18n.getLang() : 'ko';
        var monthNames = {
            ko: ['1월', '2월', '3월', '4월', '5월', '6월', '7월', '8월', '9월', '10월', '11월', '12월'],
            en: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'],
            ja: ['1月', '2月', '3月', '4月', '5月', '6月', '7月', '8月', '9月', '10月', '11月', '12月'],
            zh: ['1月', '2月', '3月', '4月', '5月', '6月', '7月', '8月', '9月', '10月', '11月', '12月'],
            ru: ['Янв', 'Фев', 'Мар', 'Апр', 'Май', 'Июн', 'Июл', 'Авг', 'Сен', 'Окт', 'Ноя', 'Дек'],
        };
        var names = monthNames[lang] || monthNames['en'];
        labelEl.textContent = currentYear + ' ' + names[currentMonth - 1];
    }

    function _escapeHtml(str) {
        if (!str) return '';
        var div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    function _t(key) {
        return (typeof I18n !== 'undefined') ? I18n.t(key) : key;
    }

    async function loadFestivals() {
        if (!listEl) return;
        listEl.innerHTML = '<div class="skeleton skeleton-popular"></div><div class="skeleton skeleton-popular"></div>';
        if (emptyEl) emptyEl.style.display = 'none';

        try {
            var params = new URLSearchParams({
                year: String(currentYear),
                month: String(currentMonth),
                limit: '50',
                offset: '0',
            });
            if (currentFilter === 'ongoing') {
                params.set('ongoing', 'true');
            }

            var res = await fetch(API_BASE + '/festivals?' + params);
            if (!res.ok) {
                throw new Error('HTTP ' + res.status);
            }
            var json = await res.json();

            var items = (json.success && Array.isArray(json.data)) ? json.data : [];

            // Client-side status filter for upcoming/ended (backend only supports ongoing)
            if (currentFilter === 'upcoming' || currentFilter === 'ended') {
                items = items.filter(function (f) { return f.status === currentFilter; });
            }

            if (items.length === 0) {
                listEl.innerHTML = '';
                if (emptyEl) emptyEl.style.display = '';
                return;
            }

            listEl.innerHTML = '';
            items.forEach(function (festival, idx) {
                var card = document.createElement('div');
                card.className = 'festival-card';
                card.style.animationDelay = (idx * 0.08) + 's';

                var safeName = _escapeHtml(festival.name);
                var safePlace = _escapeHtml(festival.location || festival.address || '');
                var thumb = (festival.images && festival.images.length > 0) ? festival.images[0] : '';
                var statusClass = 'festival-status--' + (festival.status || 'unknown');
                var statusText = _statusLabel(festival.status);

                var dateRange = _formatDateRange(festival.start_date, festival.end_date);

                var imgHtml = thumb
                    ? '<img src="' + _escapeHtml(thumb) + '" alt="' + safeName + '" class="festival-card__img" loading="lazy">'
                    : '<div class="festival-card__img-placeholder">&#x1F389;</div>';

                card.innerHTML =
                    '<div class="festival-card__image">' +
                        imgHtml +
                        '<span class="festival-card__status ' + statusClass + '">' + statusText + '</span>' +
                    '</div>' +
                    '<div class="festival-card__body">' +
                        '<h3 class="festival-card__name">' + safeName + '</h3>' +
                        '<p class="festival-card__date">&#x1F4C5; ' + _escapeHtml(dateRange) + '</p>' +
                        (safePlace ? '<p class="festival-card__place">&#x1F4CD; ' + safePlace + '</p>' : '') +
                    '</div>';

                card.addEventListener('click', function () {
                    openFestivalModal(festival);
                });
                card.setAttribute('role', 'button');
                card.setAttribute('tabindex', '0');
                card.addEventListener('keydown', function (e) {
                    if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault();
                        openFestivalModal(festival);
                    }
                });

                listEl.appendChild(card);
            });
        } catch (e) {
            console.warn('Festival load failed:', e);
            listEl.innerHTML = '';
            if (emptyEl) emptyEl.style.display = '';
        }
    }

    function openFestivalModal(festival) {
        if (!modal || !modalBody) return;

        var safeName = _escapeHtml(festival.name);
        var safeDesc = _escapeHtml(festival.description || '').replace(/\n/g, '<br>');
        var safePlace = _escapeHtml(festival.location || festival.address || '');
        var dateRange = _formatDateRange(festival.start_date, festival.end_date);
        var statusClass = 'festival-status--' + (festival.status || 'unknown');
        var statusText = _statusLabel(festival.status);

        var images = festival.images || [];
        var imgHtml = '';
        if (images.length > 0) {
            imgHtml = '<img src="' + _escapeHtml(images[0]) + '" alt="' + safeName + '" class="festival-modal__img">';
        }

        var html =
            imgHtml +
            '<h2 class="festival-modal__title" id="festival-modal-title">' + safeName + '</h2>' +
            '<span class="festival-card__status ' + statusClass + '" style="margin-bottom:.75rem;display:inline-block;">' + statusText + '</span>' +
            '<div class="festival-modal__info">' +
                '<p>&#x1F4C5; ' + _escapeHtml(dateRange) + '</p>' +
                (safePlace ? '<p>&#x1F4CD; ' + safePlace + '</p>' : '') +
            '</div>';

        if (safeDesc) {
            html += '<div class="festival-modal__desc">' + safeDesc + '</div>';
        }

        if (festival.lat != null && festival.lng != null) {
            html += '<a class="festival-modal__map-link" href="/map.html?lat=' + festival.lat + '&lng=' + festival.lng + '&zoom=15" target="_blank">' +
                '&#x1F5FA; ' + _t('detail_location') +
            '</a>';
        }

        modalBody.innerHTML = html;
        modal.style.display = '';
        document.body.style.overflow = 'hidden';
        // Prevent iOS background scroll-through when modal is open
        document.body.style.position = 'fixed';
        document.body.style.width = '100%';
        document.body.dataset.scrollY = String(window.scrollY);
        document.body.style.top = '-' + window.scrollY + 'px';

        // Focus trap
        if (modalClose) modalClose.focus();
    }

    function closeFestivalModal() {
        if (!modal) return;
        modal.style.display = 'none';
        // Restore iOS background scroll position
        var scrollY = parseInt(document.body.dataset.scrollY || '0', 10);
        document.body.style.overflow = '';
        document.body.style.position = '';
        document.body.style.width = '';
        document.body.style.top = '';
        window.scrollTo(0, scrollY);
    }

    function _statusLabel(status) {
        var map = {
            ongoing: _t('festival_status_ongoing'),
            upcoming: _t('festival_status_upcoming'),
            ended: _t('festival_status_ended'),
        };
        return map[status] || '';
    }

    function _formatDateRange(start, end) {
        if (!start && !end) return _t('info_none');
        var s = start ? _formatDate(start) : '?';
        var e = end ? _formatDate(end) : '?';
        if (s === e) return s;
        return s + ' ~ ' + e;
    }

    function _formatDate(dateStr) {
        if (!dateStr) return '';
        var parts = dateStr.split('-');
        if (parts.length >= 3) {
            return parts[0] + '.' + parts[1] + '.' + parts[2];
        }
        return dateStr;
    }
})();
