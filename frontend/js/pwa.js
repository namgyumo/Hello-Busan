/**
 * pwa.js — PWA 설치 프롬프트 관리
 */
const PWA = (() => {
    let deferredPrompt = null;
    let installBtn = null;

    const VISIT_KEY = 'pwa_visit_count';
    const INSTALLED_KEY = 'pwa_installed';

    function _getStorage(key) {
        try { return localStorage.getItem(key); } catch (e) { return null; }
    }

    function _setStorage(key, value) {
        try { localStorage.setItem(key, value); } catch (e) { /* ignore */ }
    }

    function getVisitCount() {
        return parseInt(_getStorage(VISIT_KEY) || '0', 10);
    }

    function incrementVisit() {
        const count = getVisitCount() + 1;
        _setStorage(VISIT_KEY, String(count));
        return count;
    }

    function isInstalled() {
        return _getStorage(INSTALLED_KEY) === 'true' ||
            window.matchMedia('(display-mode: standalone)').matches ||
            navigator.standalone === true;
    }

    function createInstallBanner() {
        if (document.getElementById('pwa-install-banner')) return;

        const banner = document.createElement('div');
        banner.id = 'pwa-install-banner';
        banner.className = 'pwa-install-banner';
        banner.setAttribute('role', 'alert');

        const text = document.createElement('div');
        text.className = 'pwa-install-banner__text';

        const title = document.createElement('strong');
        title.setAttribute('data-i18n', 'pwa_install');
        title.textContent = typeof I18n !== 'undefined' ? I18n.t('pwa_install') : '홈 화면에 추가';

        const desc = document.createElement('p');
        desc.setAttribute('data-i18n', 'pwa_install_desc');
        desc.textContent = typeof I18n !== 'undefined' ? I18n.t('pwa_install_desc') : '앱처럼 빠르게 부산 관광 정보를 확인하세요';

        text.appendChild(title);
        text.appendChild(desc);

        installBtn = document.createElement('button');
        installBtn.className = 'pwa-install-banner__btn';
        installBtn.setAttribute('data-i18n', 'pwa_install');
        installBtn.textContent = typeof I18n !== 'undefined' ? I18n.t('pwa_install') : '설치';
        installBtn.addEventListener('click', promptInstall);

        const closeBtn = document.createElement('button');
        closeBtn.className = 'pwa-install-banner__close';
        closeBtn.setAttribute('aria-label', 'Close');
        closeBtn.textContent = '\u00D7';
        closeBtn.addEventListener('click', () => {
            banner.classList.remove('pwa-install-banner--visible');
            sessionStorage.setItem('pwa_banner_dismissed', 'true');
        });

        banner.appendChild(text);
        banner.appendChild(installBtn);
        banner.appendChild(closeBtn);
        document.body.appendChild(banner);

        requestAnimationFrame(() => {
            banner.classList.add('pwa-install-banner--visible');
        });
    }

    async function promptInstall() {
        if (!deferredPrompt) return;

        deferredPrompt.prompt();
        const { outcome } = await deferredPrompt.userChoice;

        if (outcome === 'accepted') {
            _setStorage(INSTALLED_KEY, 'true');
            showToast(typeof I18n !== 'undefined' ? I18n.t('pwa_installed') : '설치해 주셔서 감사합니다!');
        }

        deferredPrompt = null;
        const banner = document.getElementById('pwa-install-banner');
        if (banner) banner.classList.remove('pwa-install-banner--visible');
    }

    function showToast(message) {
        const toast = document.getElementById('toast');
        if (toast) {
            toast.textContent = message;
            toast.classList.add('show');
            setTimeout(() => toast.classList.remove('show'), 3000);
        }
    }

    function init() {
        if (isInstalled()) return;

        const visitCount = incrementVisit();

        window.addEventListener('beforeinstallprompt', (e) => {
            e.preventDefault();
            deferredPrompt = e;

            if (visitCount >= 2 && !sessionStorage.getItem('pwa_banner_dismissed')) {
                createInstallBanner();
            }
        });

        window.addEventListener('appinstalled', () => {
            _setStorage(INSTALLED_KEY, 'true');
            deferredPrompt = null;
            const banner = document.getElementById('pwa-install-banner');
            if (banner) banner.classList.remove('pwa-install-banner--visible');
        });
    }

    return { init };
})();

document.addEventListener('DOMContentLoaded', () => {
    PWA.init();
});
