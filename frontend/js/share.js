/**
 * share.js — SNS 공유 모듈
 * Web Share API 우선, 폴백으로 카카오톡/LINE/Twitter/URL 복사
 */
const Share = (() => {
    let _spot = null;

    /**
     * 공유에 사용할 spot 데이터를 설정
     * @param {Object} spot - { name, comfort: { score, grade }, images, id }
     */
    function setSpot(spot) {
        _spot = spot;
    }

    /**
     * i18n 템플릿 문자열에서 {key}를 치환
     */
    function _template(str, vars) {
        return str.replace(/\{(\w+)\}/g, (_, key) => vars[key] != null ? vars[key] : '');
    }

    /**
     * 공유 텍스트 생성
     */
    function _getShareText() {
        if (!_spot) return '';
        const grade = _spot.comfort ? _spot.comfort.grade : '';
        const score = _spot.comfort ? _spot.comfort.score : '';
        return _template(I18n.t('share_text'), {
            name: _spot.name,
            grade: grade,
            score: score,
        });
    }

    /**
     * 공유 설명 생성
     */
    function _getShareDescription() {
        if (!_spot) return '';
        const grade = _spot.comfort ? _spot.comfort.grade : '';
        const score = _spot.comfort ? _spot.comfort.score : '';
        return _template(I18n.t('share_description'), {
            name: _spot.name,
            grade: grade,
            score: score,
        });
    }

    /**
     * 공유 URL 생성
     */
    function _getShareUrl() {
        if (!_spot) return window.location.href;
        return `${window.location.origin}/detail.html?id=${_spot.id}`;
    }

    /**
     * 공유 이미지 URL
     */
    function _getShareImage() {
        if (_spot && _spot.images && _spot.images.length > 0) {
            return _spot.images[0];
        }
        return `${window.location.origin}/images/og-home.png`;
    }

    /**
     * Web Share API (네이티브 공유)
     */
    async function shareNative() {
        if (!navigator.share) return false;
        try {
            await navigator.share({
                title: _getShareText(),
                text: _getShareDescription(),
                url: _getShareUrl(),
            });
            return true;
        } catch (e) {
            if (e.name !== 'AbortError') {
                console.warn('Native share failed:', e);
            }
            return false;
        }
    }

    /**
     * 카카오톡 공유 (카카오 SDK 없이 URL scheme 사용)
     */
    function shareKakao() {
        const text = _getShareText();
        const url = _getShareUrl();
        const kakaoUrl = `https://story.kakao.com/share?url=${encodeURIComponent(url)}&text=${encodeURIComponent(text)}`;
        window.open(kakaoUrl, '_blank', 'width=600,height=400,noopener,noreferrer');
    }

    /**
     * LINE 공유
     */
    function shareLine() {
        const text = _getShareText();
        const url = _getShareUrl();
        const lineUrl = `https://social-plugins.line.me/lineit/share?url=${encodeURIComponent(url)}&text=${encodeURIComponent(text)}`;
        window.open(lineUrl, '_blank', 'width=600,height=400,noopener,noreferrer');
    }

    /**
     * Twitter (X) 공유
     */
    function shareTwitter() {
        const text = _getShareText();
        const url = _getShareUrl();
        const twitterUrl = `https://twitter.com/intent/tweet?text=${encodeURIComponent(text)}&url=${encodeURIComponent(url)}`;
        window.open(twitterUrl, '_blank', 'width=600,height=400,noopener,noreferrer');
    }

    /**
     * URL 클립보드 복사
     */
    async function copyUrl() {
        const url = _getShareUrl();
        try {
            await navigator.clipboard.writeText(url);
            return true;
        } catch (e) {
            // Fallback for older browsers
            const textarea = document.createElement('textarea');
            textarea.value = url;
            textarea.style.position = 'fixed';
            textarea.style.opacity = '0';
            document.body.appendChild(textarea);
            textarea.select();
            try {
                document.execCommand('copy');
                return true;
            } catch (err) {
                console.warn('Copy failed:', err);
                return false;
            } finally {
                document.body.removeChild(textarea);
            }
        }
    }

    /**
     * 공유 버튼 그룹을 컨테이너에 렌더링
     * @param {string} containerId - 버튼을 삽입할 컨테이너 ID
     * @param {Function} showToast - 토스트 메시지 표시 함수
     */
    function render(containerId, showToast) {
        const container = document.getElementById(containerId);
        if (!container) return;

        const hasNativeShare = !!navigator.share;

        let buttonsHtml = '';

        if (hasNativeShare) {
            buttonsHtml += `
                <button class="share-btn share-btn--native" data-action="native" aria-label="${I18n.t('share_native')}">
                    <span class="share-btn__icon">&#x1F4E4;</span>
                    <span class="share-btn__label" data-i18n="share_native">${I18n.t('share_native')}</span>
                </button>
            `;
        }

        buttonsHtml += `
            <button class="share-btn share-btn--kakao" data-action="kakao" aria-label="${I18n.t('share_kakao')}">
                <span class="share-btn__icon">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M12 3C6.48 3 2 6.58 2 10.9c0 2.8 1.86 5.27 4.66 6.67l-1.2 4.43 5.14-3.38c.46.04.93.07 1.4.07 5.52 0 10-3.58 10-7.99S17.52 3 12 3z"/></svg>
                </span>
                <span class="share-btn__label" data-i18n="share_kakao">${I18n.t('share_kakao')}</span>
            </button>
            <button class="share-btn share-btn--line" data-action="line" aria-label="${I18n.t('share_line')}">
                <span class="share-btn__icon">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C6.48 2 2 5.82 2 10.5c0 4.21 3.74 7.74 8.78 8.4.34.07.8.23.92.52.1.27.07.68.03.95l-.15.89c-.04.27-.21 1.05.92.57s6.13-3.61 8.36-6.18C22.68 13.56 22 12.1 22 10.5 22 5.82 17.52 2 12 2z"/></svg>
                </span>
                <span class="share-btn__label" data-i18n="share_line">${I18n.t('share_line')}</span>
            </button>
            <button class="share-btn share-btn--twitter" data-action="twitter" aria-label="${I18n.t('share_twitter')}">
                <span class="share-btn__icon">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg>
                </span>
                <span class="share-btn__label" data-i18n="share_twitter">${I18n.t('share_twitter')}</span>
            </button>
            <button class="share-btn share-btn--copy" data-action="copy" aria-label="${I18n.t('share_copy_url')}">
                <span class="share-btn__icon">&#x1F517;</span>
                <span class="share-btn__label" data-i18n="share_copy_url">${I18n.t('share_copy_url')}</span>
            </button>
        `;

        container.innerHTML = `
            <h3 class="share-section__title" data-i18n="share_title">${I18n.t('share_title')}</h3>
            <div class="share-buttons">
                ${buttonsHtml}
            </div>
        `;

        // Event delegation
        container.addEventListener('click', async (e) => {
            const btn = e.target.closest('.share-btn');
            if (!btn) return;

            const action = btn.dataset.action;
            switch (action) {
                case 'native':
                    await shareNative();
                    break;
                case 'kakao':
                    shareKakao();
                    break;
                case 'line':
                    shareLine();
                    break;
                case 'twitter':
                    shareTwitter();
                    break;
                case 'copy': {
                    const ok = await copyUrl();
                    if (ok && showToast) {
                        showToast(I18n.t('share_copy_success'));
                    }
                    break;
                }
            }
        });
    }

    /**
     * OG 메타 태그 동적 업데이트
     */
    function updateOgMeta() {
        if (!_spot) return;

        const title = `${_spot.name} — Hello, Busan!`;
        const description = _getShareDescription();
        const url = _getShareUrl();
        const image = _getShareImage();

        _setMeta('property', 'og:title', title);
        _setMeta('property', 'og:description', description);
        _setMeta('property', 'og:url', url);
        _setMeta('property', 'og:image', image);
        _setMeta('name', 'twitter:title', title);
        _setMeta('name', 'twitter:description', description);
        _setMeta('name', 'twitter:image', image);
        _setMeta('name', 'description', description);

        // Update hreflang with spot ID
        const langs = ['ko', 'en', 'ja', 'zh', 'ru'];
        const canonical = document.querySelector('link[rel="canonical"]');
        if (canonical) canonical.href = url;

        langs.forEach(lang => {
            const link = document.querySelector(`link[hreflang="${lang}"]`);
            if (link) link.href = `${window.location.origin}/detail.html?id=${_spot.id}&lang=${lang}`;
        });

        const xDefault = document.querySelector('link[hreflang="x-default"]');
        if (xDefault) xDefault.href = url;
    }

    function _setMeta(attr, name, content) {
        let el = document.querySelector(`meta[${attr}="${name}"]`);
        if (el) {
            el.setAttribute('content', content);
        }
    }

    return { setSpot, render, updateOgMeta, shareNative, shareKakao, shareLine, shareTwitter, copyUrl };
})();
