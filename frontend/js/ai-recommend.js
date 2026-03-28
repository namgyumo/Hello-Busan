/**
 * ai-recommend.js — 대화형 AI 관광지 추���
 */
(async () => {
    const API_BASE = '/api/v1';

    if (typeof Analytics !== 'undefined') Analytics.init();
    await I18n.init();

    // DOM
    const chatArea = document.getElementById('ai-chat');
    const input = document.getElementById('ai-input');
    const sendBtn = document.getElementById('ai-send-btn');
    const chipsContainer = document.getElementById('ai-chips');
    const welcomeEl = document.getElementById('ai-welcome');

    if (!chatArea || !input) return;

    // 대화 히스토리 (맥락 유지)
    const chatHistory = [];

    // 입력 활성화
    input.addEventListener('input', () => {
        sendBtn.disabled = !input.value.trim();
    });

    // Enter 전송
    input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            const query = input.value.trim();
            if (query) _submitMessage(query);
        }
    });

    // 전��� 버튼
    sendBtn.addEventListener('click', () => {
        const query = input.value.trim();
        if (query) _submitMessage(query);
    });

    // 예시 칩
    if (chipsContainer) {
        chipsContainer.addEventListener('click', (e) => {
            const chip = e.target.closest('.ai-chip');
            if (!chip) return;
            const query = chip.dataset.query || chip.textContent.trim();
            input.value = query;
            _submitMessage(query);
        });
    }

    async function _submitMessage(text) {
        // 환영 & 칩 숨기기
        if (welcomeEl) welcomeEl.style.display = 'none';
        if (chipsContainer) chipsContainer.style.display = 'none';

        // 사용자 메시지 표시
        _appendUserMessage(text);
        chatHistory.push({ role: 'user', content: text });

        // 입력 초기화 & 비활성화
        input.value = '';
        sendBtn.disabled = true;
        _setInputDisabled(true);

        const loadingEl = _appendLoading();

        if (typeof Analytics !== 'undefined') Analytics.trackSearch(text);

        try {
            const data = await _fetchChat(chatHistory);
            loadingEl.remove();

            if (data.type === 'recommendation') {
                // AI 메시지 + 추천 카드
                if (data.message) {
                    _appendAIMessage(data.message);
                    chatHistory.push({ role: 'assistant', content: data.message });
                }
                if (data.recommendations && data.recommendations.length > 0) {
                    _appendResults(data.recommendations);
                } else {
                    _appendAIMessage('조건에 맞는 관광지를 찾지 못했어요. 다른 키워드로 다시 시도해 보세요!');
                }
            } else {
                // AI 질문/대화 메시지
                const msg = data.message || '죄송합니다, 다시 말씀해 주세요.';
                _appendAIMessage(msg);
                chatHistory.push({ role: 'assistant', content: msg });
            }
        } catch (e) {
            console.warn('AI 대화 실패:', e);
            loadingEl.remove();
            _appendError();
        }

        _setInputDisabled(false);
        input.focus();
    }

    async function _fetchChat(messages) {
        const res = await fetch(`${API_BASE}/ai/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ messages }),
        });
        if (!res.ok) throw new Error('AI API 오류: ' + res.status);
        return res.json();
    }

    // ─── 채팅 UI 렌더링 ───

    function _appendUserMessage(text) {
        const el = document.createElement('div');
        el.className = 'ai-message ai-message--user';
        el.textContent = text;
        chatArea.appendChild(el);
        _scrollToBottom();
    }

    function _appendAIMessage(text) {
        const el = document.createElement('div');
        el.className = 'ai-message ai-message--ai';
        el.innerHTML = `
            <div class="ai-message__label">\u2728 AI \uCD94\uCC9C</div>
            <div>${_escapeHtml(text)}</div>
        `;
        chatArea.appendChild(el);
        _scrollToBottom();
    }

    function _appendLoading() {
        const el = document.createElement('div');
        el.className = 'ai-loading';
        el.innerHTML = `
            <div class="ai-loading__dots">
                <div class="ai-loading__dot"></div>
                <div class="ai-loading__dot"></div>
                <div class="ai-loading__dot"></div>
            </div>
            <span class="ai-loading__text">AI\uAC00 \uC0DD\uAC01 \uC911\uC785\uB2C8\uB2E4...</span>
        `;
        chatArea.appendChild(el);
        _scrollToBottom();
        return el;
    }

    function _appendError() {
        const el = document.createElement('div');
        el.className = 'ai-error';
        el.innerHTML = `
            <span>\u26A0\uFE0F \uC624\uB958\uAC00 \uBC1C\uC0DD\uD588\uC5B4\uC694. \uB2E4\uC2DC \uC2DC\uB3C4\uD574 \uC8FC\uC138\uC694.</span>
        `;
        chatArea.appendChild(el);
        _scrollToBottom();
    }

    function _appendResults(recommendations) {
        const wrapper = document.createElement('div');
        wrapper.className = 'ai-results';
        wrapper.innerHTML = `<div class="ai-results__title">\u2728 \uCD94\uCC9C \uACB0\uACFC ${recommendations.length}\uAC74</div>`;

        recommendations.forEach((spot, idx) => {
            const safeName = _escapeHtml(spot.name);
            const reason = _escapeHtml(spot.reason || '');
            const catLabel = _categoryLabel(spot.category_id);
            const catEmoji = _categoryEmoji(spot.category_id);
            const imgUrl = spot.images && spot.images.length > 0 ? spot.images[0] : '';

            const card = document.createElement('a');
            card.className = 'ai-card';
            card.href = `/detail.html?id=${encodeURIComponent(spot.id)}`;

            const imgHtml = imgUrl
                ? `<img src="${_escapeHtml(imgUrl)}" alt="${safeName}" class="ai-card__img" loading="lazy">`
                : `<div class="ai-card__img-placeholder">${catEmoji}</div>`;

            card.innerHTML = `
                ${imgHtml}
                <div class="ai-card__body">
                    <div class="ai-card__top">
                        <span class="ai-card__rank">#${idx + 1}</span>
                        <span class="ai-card__name">${safeName}</span>
                    </div>
                    <span class="ai-card__cat">${catEmoji} ${catLabel}</span>
                    ${reason ? `<div class="ai-card__reason">${reason}</div>` : ''}
                </div>
            `;

            card.addEventListener('click', () => {
                if (typeof Analytics !== 'undefined') Analytics.trackSpotClick(spot.id, spot.name);
            });

            wrapper.appendChild(card);
        });

        chatArea.appendChild(wrapper);
        _scrollToBottom();
    }

    // ─── 유틸리티 ───

    function _setInputDisabled(disabled) {
        input.disabled = disabled;
        sendBtn.disabled = disabled;
    }

    function _scrollToBottom() {
        chatArea.scrollTop = chatArea.scrollHeight;
    }

    function _escapeHtml(str) {
        if (!str) return '';
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    function _categoryLabel(cat) {
        const keyMap = {
            nature: 'category_nature', culture: 'category_culture', food: 'category_food',
            activity: 'category_activity', shopping: 'category_shopping', nightview: 'category_nightview',
            heritage: 'category_heritage',
        };
        return keyMap[cat] ? I18n.t(keyMap[cat]) : (cat || '');
    }

    function _categoryEmoji(cat) {
        const map = {
            nature: '\u{1F3D4}', culture: '\u{1F3DB}', food: '\u{1F35C}',
            activity: '\u{1F3C4}', shopping: '\u{1F6CD}', nightview: '\u{1F319}',
            heritage: '\u{1F3FA}',
        };
        return map[cat] || '\u{1F30A}';
    }
})();
