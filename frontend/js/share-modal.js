/**
 * share-modal.js — 바텀시트 스타일 공유 모달
 * 카드 미리보기 + 공유 옵션 (카드 저장, 링크 공유, 카카오톡)
 */
const ShareModal = (() => {
    let _spot = null;
    let _isOpen = false;
    let _previewBlob = null;
    let _showToast = null;
    let _modalEl = null;

    /**
     * 모달 HTML 구조 생성 및 DOM에 삽입
     */
    function _ensureModal() {
        if (_modalEl) return _modalEl;

        const modal = document.createElement('div');
        modal.id = 'share-modal';
        modal.className = 'share-modal';
        modal.setAttribute('role', 'dialog');
        modal.setAttribute('aria-modal', 'true');
        modal.setAttribute('aria-label', I18n.t('share_modal_title') || '공유하기');
        modal.innerHTML = `
            <div class="share-modal__backdrop" data-action="close"></div>
            <div class="share-modal__sheet">
                <div class="share-modal__handle"></div>
                <div class="share-modal__header">
                    <h3 class="share-modal__title" data-i18n="share_modal_title">${I18n.t('share_modal_title') || '공유하기'}</h3>
                    <button class="share-modal__close" data-action="close" aria-label="닫기">&times;</button>
                </div>
                <div class="share-modal__preview">
                    <div class="share-modal__card-tabs">
                        <button class="share-modal__tab share-modal__tab--active" data-card-type="square" data-i18n="share_card_square">${I18n.t('share_card_square') || '정사각형'}</button>
                        <button class="share-modal__tab" data-card-type="story" data-i18n="share_card_story">${I18n.t('share_card_story') || '스토리'}</button>
                    </div>
                    <div class="share-modal__card-preview" id="share-card-preview">
                        <div class="share-modal__card-loading">
                            <div class="share-modal__spinner"></div>
                            <span data-i18n="share_card_generating">${I18n.t('share_card_generating') || '카드 생성 중...'}</span>
                        </div>
                    </div>
                </div>
                <div class="share-modal__options">
                    <button class="share-modal__option" data-action="save-card">
                        <span class="share-modal__option-icon">&#x1F4BE;</span>
                        <span class="share-modal__option-label" data-i18n="share_save_card">${I18n.t('share_save_card') || '카드 이미지 저장'}</span>
                    </button>
                    <button class="share-modal__option" data-action="share-image" id="share-modal-share-img" style="display:none">
                        <span class="share-modal__option-icon">&#x1F4F1;</span>
                        <span class="share-modal__option-label" data-i18n="share_send_image">${I18n.t('share_send_image') || '이미지 공유'}</span>
                    </button>
                    <button class="share-modal__option" data-action="link-share">
                        <span class="share-modal__option-icon">&#x1F517;</span>
                        <span class="share-modal__option-label" data-i18n="share_link">${I18n.t('share_link') || '링크 공유'}</span>
                    </button>
                    <button class="share-modal__option" data-action="kakao-share">
                        <span class="share-modal__option-icon">
                            <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path d="M12 3C6.48 3 2 6.58 2 10.9c0 2.8 1.86 5.27 4.66 6.67l-1.2 4.43 5.14-3.38c.46.04.93.07 1.4.07 5.52 0 10-3.58 10-7.99S17.52 3 12 3z"/></svg>
                        </span>
                        <span class="share-modal__option-label" data-i18n="share_kakao">${I18n.t('share_kakao')}</span>
                    </button>
                    <button class="share-modal__option" data-action="twitter-share">
                        <span class="share-modal__option-icon">
                            <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg>
                        </span>
                        <span class="share-modal__option-label" data-i18n="share_twitter">${I18n.t('share_twitter')}</span>
                    </button>
                    <button class="share-modal__option" data-action="copy-url">
                        <span class="share-modal__option-icon">&#x1F4CB;</span>
                        <span class="share-modal__option-label" data-i18n="share_copy_url">${I18n.t('share_copy_url')}</span>
                    </button>
                </div>
            </div>
        `;
        document.body.appendChild(modal);
        _modalEl = modal;

        // 이미지 공유 지원 여부 체크
        if (navigator.canShare) {
            const shareImgBtn = modal.querySelector('#share-modal-share-img');
            if (shareImgBtn) shareImgBtn.style.display = '';
        }

        // 이벤트 위임
        modal.addEventListener('click', _handleClick);

        // 탭 전환
        modal.querySelectorAll('.share-modal__tab').forEach(tab => {
            tab.addEventListener('click', () => {
                modal.querySelectorAll('.share-modal__tab').forEach(t => t.classList.remove('share-modal__tab--active'));
                tab.classList.add('share-modal__tab--active');
                _generatePreview(tab.dataset.cardType);
            });
        });

        // ESC 키로 닫기
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && _isOpen) close();
        });

        // 터치 스와이프 다운으로 닫기
        let touchStartY = 0;
        const sheet = modal.querySelector('.share-modal__sheet');
        sheet.addEventListener('touchstart', (e) => {
            touchStartY = e.touches[0].clientY;
        }, { passive: true });
        sheet.addEventListener('touchend', (e) => {
            const diff = e.changedTouches[0].clientY - touchStartY;
            if (diff > 80) close();
        }, { passive: true });

        return modal;
    }

    /**
     * 클릭 이벤트 핸들러
     */
    async function _handleClick(e) {
        const target = e.target.closest('[data-action]');
        if (!target) return;

        const action = target.dataset.action;
        switch (action) {
            case 'close':
                close();
                break;
            case 'save-card':
                if (_previewBlob) {
                    const filename = `hello-busan-${(_spot && _spot.name) || 'card'}.png`;
                    ShareCard.download(_previewBlob, filename);
                    if (_showToast) _showToast(I18n.t('share_card_saved') || '카드가 저장되었습니다');
                }
                break;
            case 'share-image':
                if (_previewBlob && _spot) {
                    const shared = await ShareCard.shareImage(_previewBlob, _spot.name);
                    if (!shared && _showToast) {
                        _showToast(I18n.t('share_image_fail') || '이미지 공유를 지원하지 않습니다');
                    }
                }
                break;
            case 'link-share':
                if (navigator.share && _spot) {
                    try {
                        await navigator.share({
                            title: `${_spot.name} — Hello, Busan!`,
                            text: Share._getShareDescription ? Share._getShareDescription() : '',
                            url: _getShareUrlWithUtm(),
                        });
                    } catch (err) {
                        if (err.name !== 'AbortError') {
                            // 네이티브 공유 실패 시 클립보드 복사
                            await _copyToClipboard();
                        }
                    }
                } else {
                    await _copyToClipboard();
                }
                break;
            case 'kakao-share':
                if (typeof Share !== 'undefined') Share.shareKakao();
                break;
            case 'twitter-share':
                if (typeof Share !== 'undefined') Share.shareTwitter();
                break;
            case 'copy-url':
                await _copyToClipboard();
                break;
        }
    }

    /**
     * UTM 파라미터가 포함된 공유 URL
     */
    function _getShareUrlWithUtm() {
        if (!_spot) return window.location.href;
        return `${window.location.origin}/detail.html?id=${_spot.id}&utm_source=share&utm_medium=sns&utm_campaign=spot_share`;
    }

    /**
     * 클립보드에 URL 복사
     */
    async function _copyToClipboard() {
        const url = _getShareUrlWithUtm();
        try {
            await navigator.clipboard.writeText(url);
            if (_showToast) _showToast(I18n.t('share_copy_success'));
        } catch (e) {
            const textarea = document.createElement('textarea');
            textarea.value = url;
            textarea.style.position = 'fixed';
            textarea.style.opacity = '0';
            document.body.appendChild(textarea);
            textarea.select();
            document.execCommand('copy');
            document.body.removeChild(textarea);
            if (_showToast) _showToast(I18n.t('share_copy_success'));
        }
    }

    /**
     * 카드 미리보기 생성
     */
    async function _generatePreview(type) {
        if (!_spot) return;

        const preview = document.getElementById('share-card-preview');
        if (!preview) return;

        // 로딩 표시
        preview.innerHTML = `
            <div class="share-modal__card-loading">
                <div class="share-modal__spinner"></div>
                <span>${I18n.t('share_card_generating') || '카드 생성 중...'}</span>
            </div>
        `;

        try {
            const blob = await ShareCard.generate(_spot, type || 'square');
            _previewBlob = blob;

            const url = URL.createObjectURL(blob);
            preview.innerHTML = `<img class="share-modal__card-img" src="${url}" alt="Share card preview">`;
        } catch (e) {
            console.warn('카드 미리보기 생성 실패:', e);
            preview.innerHTML = `<div class="share-modal__card-error">${I18n.t('share_card_error') || '카드 생성 실패'}</div>`;
        }
    }

    /**
     * 모달 열기
     * @param {Object} spot - 관광지 데이터
     * @param {Function} showToast - 토스트 함수
     */
    function open(spot, showToast) {
        _spot = spot;
        _showToast = showToast;
        _previewBlob = null;

        const modal = _ensureModal();

        // 활성 탭에 맞는 카드 생성
        const activeTab = modal.querySelector('.share-modal__tab--active');
        const type = activeTab ? activeTab.dataset.cardType : 'square';

        // 모달 열기 애니메이션
        modal.classList.add('share-modal--open');
        document.body.style.overflow = 'hidden';
        _isOpen = true;

        // 카드 미리보기 생성 (약간의 딜레이로 애니메이션 후)
        setTimeout(() => _generatePreview(type), 200);
    }

    /**
     * 모달 닫기
     */
    function close() {
        if (!_modalEl) return;
        _modalEl.classList.remove('share-modal--open');
        document.body.style.overflow = '';
        _isOpen = false;
        _previewBlob = null;
    }

    /**
     * 모달이 열려있는지 여부
     */
    function isOpen() {
        return _isOpen;
    }

    return { open, close, isOpen };
})();
