/**
 * share-card.js — Canvas API 기반 SNS 공유 카드 이미지 생성기
 * 인스타 스토리(1080x1920) / 정사각형(1080x1080) 두 가지 사이즈
 */
const ShareCard = (() => {
    const SIZES = {
        story: { w: 1080, h: 1920 },
        square: { w: 1080, h: 1080 },
    };

    /**
     * 이미지를 로드하여 Promise<HTMLImageElement>로 반환
     */
    function _loadImage(src) {
        return new Promise((resolve, reject) => {
            const img = new Image();
            img.crossOrigin = 'anonymous';
            img.onload = () => resolve(img);
            img.onerror = () => reject(new Error('Image load failed: ' + src));
            img.src = src;
        });
    }

    /**
     * 이미지를 캔버스에 cover 방식으로 그리기 (object-fit: cover)
     */
    function _drawCover(ctx, img, x, y, w, h) {
        const ratio = Math.max(w / img.width, h / img.height);
        const sw = w / ratio;
        const sh = h / ratio;
        const sx = (img.width - sw) / 2;
        const sy = (img.height - sh) / 2;
        ctx.drawImage(img, sx, sy, sw, sh, x, y, w, h);
    }

    /**
     * 둥근 사각형 경로 생성
     */
    function _roundRect(ctx, x, y, w, h, r) {
        ctx.beginPath();
        ctx.moveTo(x + r, y);
        ctx.lineTo(x + w - r, y);
        ctx.quadraticCurveTo(x + w, y, x + w, y + r);
        ctx.lineTo(x + w, y + h - r);
        ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
        ctx.lineTo(x + r, y + h);
        ctx.quadraticCurveTo(x, y + h, x, y + h - r);
        ctx.lineTo(x, y + r);
        ctx.quadraticCurveTo(x, y, x + r, y);
        ctx.closePath();
    }

    /**
     * 텍스트를 최대 너비에 맞게 줄바꿈하여 배열로 반환
     */
    function _wrapText(ctx, text, maxWidth) {
        const words = text.split('');
        const lines = [];
        let line = '';
        for (const char of words) {
            const test = line + char;
            if (ctx.measureText(test).width > maxWidth && line.length > 0) {
                lines.push(line);
                line = char;
            } else {
                line = test;
            }
        }
        if (line) lines.push(line);
        return lines;
    }

    /**
     * 스토리 카드 생성 (1080 x 1920)
     */
    async function _drawStoryCard(ctx, W, H, img, spot) {
        // 1) 배경: 블러 처리된 이미지 + 어두운 오버레이
        ctx.filter = 'blur(30px) brightness(0.4)';
        _drawCover(ctx, img, -40, -40, W + 80, H + 80);
        ctx.filter = 'none';

        // 그라데이션 오버레이
        const grad = ctx.createLinearGradient(0, 0, 0, H);
        grad.addColorStop(0, 'rgba(0,40,80,0.3)');
        grad.addColorStop(0.5, 'rgba(0,20,60,0.15)');
        grad.addColorStop(1, 'rgba(0,20,40,0.5)');
        ctx.fillStyle = grad;
        ctx.fillRect(0, 0, W, H);

        // 2) 상단: Hello Busan 로고
        ctx.fillStyle = '#FFFFFF';
        ctx.font = 'bold 48px Pretendard, -apple-system, sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('Hello, Busan!', W / 2, 100);

        // 로고 하단 라인
        ctx.strokeStyle = 'rgba(255,255,255,0.4)';
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(W / 2 - 120, 120);
        ctx.lineTo(W / 2 + 120, 120);
        ctx.stroke();

        // 3) 중앙: 관광지 이미지 (둥근 사각형)
        const imgPadding = 60;
        const imgW = W - imgPadding * 2;
        const imgH = 900;
        const imgX = imgPadding;
        const imgY = 200;

        ctx.save();
        _roundRect(ctx, imgX, imgY, imgW, imgH, 24);
        ctx.clip();
        _drawCover(ctx, img, imgX, imgY, imgW, imgH);
        ctx.restore();

        // 이미지 위 카테고리 배지
        if (spot.category_label) {
            ctx.font = 'bold 28px Pretendard, sans-serif';
            const badgeText = spot.category_label;
            const badgeW = ctx.measureText(badgeText).width + 36;
            const badgeH = 48;
            const badgeX = imgX + 24;
            const badgeY = imgY + 24;

            ctx.fillStyle = 'rgba(0,102,204,0.85)';
            _roundRect(ctx, badgeX, badgeY, badgeW, badgeH, 24);
            ctx.fill();
            ctx.fillStyle = '#FFFFFF';
            ctx.textAlign = 'left';
            ctx.fillText(badgeText, badgeX + 18, badgeY + 34);
        }

        // 4) 하단 정보 영역
        const infoY = imgY + imgH + 60;

        // 관광지 이름
        ctx.fillStyle = '#FFFFFF';
        ctx.font = 'bold 56px Pretendard, sans-serif';
        ctx.textAlign = 'center';
        const nameLines = _wrapText(ctx, spot.name || '', W - 120);
        nameLines.slice(0, 2).forEach((line, i) => {
            ctx.fillText(line, W / 2, infoY + i * 68);
        });

        // 주소
        const addrY = infoY + nameLines.slice(0, 2).length * 68 + 20;
        if (spot.address) {
            ctx.font = '32px Pretendard, sans-serif';
            ctx.fillStyle = 'rgba(255,255,255,0.75)';
            const addrLines = _wrapText(ctx, spot.address, W - 120);
            addrLines.slice(0, 2).forEach((line, i) => {
                ctx.fillText(line, W / 2, addrY + i * 44);
            });
        }

        // 쾌적도 점수 (있는 경우)
        if (spot.comfort && spot.comfort.score != null) {
            const scoreY = addrY + 100;
            const scoreText = `${spot.comfort.grade} ${spot.comfort.score}`;

            ctx.font = 'bold 36px Pretendard, sans-serif';
            const sw = ctx.measureText(scoreText).width + 48;
            const sh = 56;
            const sx = (W - sw) / 2;

            ctx.fillStyle = spot.comfort.score >= 80 ? 'rgba(46,204,113,0.85)'
                : spot.comfort.score >= 60 ? 'rgba(243,156,18,0.85)'
                : 'rgba(231,76,60,0.85)';
            _roundRect(ctx, sx, scoreY - 38, sw, sh, 28);
            ctx.fill();

            ctx.fillStyle = '#FFFFFF';
            ctx.fillText(scoreText, W / 2, scoreY);
        }

        // 5) 하단 바
        const barH = 80;
        const barY = H - barH;
        ctx.fillStyle = 'rgba(0,102,204,0.9)';
        ctx.fillRect(0, barY, W, barH);

        ctx.fillStyle = '#FFFFFF';
        ctx.font = '30px Pretendard, sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('Hello, Busan! \u2014 \uBD80\uC0B0 \uAD00\uAD11 \uC2A4\uB9C8\uD2B8 \uCD94\uCC9C', W / 2, barY + 50);
    }

    /**
     * 정사각형 카드 생성 (1080 x 1080)
     */
    async function _drawSquareCard(ctx, W, H, img, spot) {
        // 1) 배경: 블러 처리
        ctx.filter = 'blur(25px) brightness(0.35)';
        _drawCover(ctx, img, -30, -30, W + 60, H + 60);
        ctx.filter = 'none';

        // 오버레이
        const grad = ctx.createLinearGradient(0, 0, 0, H);
        grad.addColorStop(0, 'rgba(0,30,60,0.2)');
        grad.addColorStop(1, 'rgba(0,20,40,0.5)');
        ctx.fillStyle = grad;
        ctx.fillRect(0, 0, W, H);

        // 2) 상단 로고
        ctx.fillStyle = '#FFFFFF';
        ctx.font = 'bold 36px Pretendard, -apple-system, sans-serif';
        ctx.textAlign = 'left';
        ctx.fillText('Hello, Busan!', 40, 60);

        // 카테고리 배지 (상단 우측)
        if (spot.category_label) {
            ctx.font = 'bold 24px Pretendard, sans-serif';
            ctx.textAlign = 'right';
            const badgeText = spot.category_label;
            const badgeW = ctx.measureText(badgeText).width + 30;
            const badgeX = W - 40 - badgeW;
            const badgeY = 35;
            ctx.fillStyle = 'rgba(0,102,204,0.85)';
            _roundRect(ctx, badgeX, badgeY, badgeW, 40, 20);
            ctx.fill();
            ctx.fillStyle = '#FFFFFF';
            ctx.fillText(badgeText, W - 40 - 15, 62);
        }

        // 3) 중앙 이미지
        const imgPad = 40;
        const imgW = W - imgPad * 2;
        const imgH = 600;
        const imgX = imgPad;
        const imgY = 100;

        ctx.save();
        _roundRect(ctx, imgX, imgY, imgW, imgH, 20);
        ctx.clip();
        _drawCover(ctx, img, imgX, imgY, imgW, imgH);
        ctx.restore();

        // 4) 하단 정보
        const infoY = imgY + imgH + 50;

        ctx.fillStyle = '#FFFFFF';
        ctx.font = 'bold 46px Pretendard, sans-serif';
        ctx.textAlign = 'center';
        const nameLines = _wrapText(ctx, spot.name || '', W - 100);
        nameLines.slice(0, 2).forEach((line, i) => {
            ctx.fillText(line, W / 2, infoY + i * 56);
        });

        // 주소 (간략)
        const addrY = infoY + nameLines.slice(0, 2).length * 56 + 16;
        if (spot.address) {
            ctx.font = '28px Pretendard, sans-serif';
            ctx.fillStyle = 'rgba(255,255,255,0.7)';
            const shortAddr = spot.address.length > 30 ? spot.address.slice(0, 30) + '...' : spot.address;
            ctx.fillText(shortAddr, W / 2, addrY);
        }

        // 5) 하단 바
        const barH = 60;
        const barY = H - barH;
        ctx.fillStyle = 'rgba(0,102,204,0.9)';
        ctx.fillRect(0, barY, W, barH);

        ctx.fillStyle = '#FFFFFF';
        ctx.font = '26px Pretendard, sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('Hello, Busan! \u2014 \uBD80\uC0B0 \uAD00\uAD11 \uC2A4\uB9C8\uD2B8 \uCD94\uCC9C', W / 2, barY + 40);
    }

    /**
     * 공유 카드 생성 메인 함수
     * @param {Object} spot - 관광지 데이터 { name, category, category_label, address, images, comfort }
     * @param {'story'|'square'} type - 카드 타입
     * @returns {Promise<Blob>} PNG 이미지 Blob
     */
    async function generate(spot, type) {
        const size = SIZES[type] || SIZES.square;
        const { w: W, h: H } = size;

        const canvas = document.createElement('canvas');
        canvas.width = W;
        canvas.height = H;
        const ctx = canvas.getContext('2d');

        // 카테고리 라벨 생성
        const categoryLabels = {
            nature: I18n.t('category_nature'),
            culture: I18n.t('category_culture'),
            food: I18n.t('category_food'),
            activity: I18n.t('category_activity'),
            shopping: I18n.t('category_shopping'),
            nightview: I18n.t('category_nightview'),
        };
        const spotData = {
            ...spot,
            category_label: categoryLabels[spot.category] || spot.category || '',
        };

        // 이미지 로드
        let img;
        try {
            const imgSrc = (spot.images && spot.images.length > 0)
                ? spot.images[0]
                : '/images/og-home.png';
            img = await _loadImage(imgSrc);
        } catch (e) {
            // 이미지 로드 실패 시 단색 배경으로 폴백
            ctx.fillStyle = '#1A3A5C';
            ctx.fillRect(0, 0, W, H);
            img = null;
        }

        if (img) {
            if (type === 'story') {
                await _drawStoryCard(ctx, W, H, img, spotData);
            } else {
                await _drawSquareCard(ctx, W, H, img, spotData);
            }
        } else {
            // 폴백: 단색 배경 + 텍스트
            _drawFallbackCard(ctx, W, H, spotData, type);
        }

        return new Promise((resolve) => {
            canvas.toBlob((blob) => resolve(blob), 'image/png', 1.0);
        });
    }

    /**
     * 이미지 없을 때 폴백 카드
     */
    function _drawFallbackCard(ctx, W, H, spot, type) {
        // 그라데이션 배경
        const grad = ctx.createLinearGradient(0, 0, W, H);
        grad.addColorStop(0, '#0066CC');
        grad.addColorStop(1, '#004C99');
        ctx.fillStyle = grad;
        ctx.fillRect(0, 0, W, H);

        // 로고
        ctx.fillStyle = '#FFFFFF';
        ctx.font = 'bold 48px Pretendard, sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('Hello, Busan!', W / 2, type === 'story' ? 200 : 120);

        // 이름
        ctx.font = 'bold 56px Pretendard, sans-serif';
        ctx.fillText(spot.name || '', W / 2, H / 2);

        // 카테고리
        if (spot.category_label) {
            ctx.font = '32px Pretendard, sans-serif';
            ctx.fillStyle = 'rgba(255,255,255,0.8)';
            ctx.fillText(spot.category_label, W / 2, H / 2 + 60);
        }

        // 하단 바
        const barH = type === 'story' ? 80 : 60;
        ctx.fillStyle = 'rgba(0,0,0,0.3)';
        ctx.fillRect(0, H - barH, W, barH);
        ctx.fillStyle = '#FFFFFF';
        ctx.font = '28px Pretendard, sans-serif';
        ctx.fillText('Hello, Busan! \u2014 \uBD80\uC0B0 \uAD00\uAD11 \uC2A4\uB9C8\uD2B8 \uCD94\uCC9C', W / 2, H - barH / 2 + 10);
    }

    /**
     * 생성된 카드 이미지 다운로드
     * @param {Blob} blob - PNG 이미지 Blob
     * @param {string} filename - 파일명
     */
    function download(blob, filename) {
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename || 'hello-busan-card.png';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        setTimeout(() => URL.revokeObjectURL(url), 5000);
    }

    /**
     * Web Share API로 이미지 공유 (지원 시)
     * @param {Blob} blob - PNG Blob
     * @param {string} title - 공유 제목
     * @returns {Promise<boolean>} 성공 여부
     */
    async function shareImage(blob, title) {
        if (!navigator.canShare) return false;
        const file = new File([blob], 'hello-busan-card.png', { type: 'image/png' });
        if (!navigator.canShare({ files: [file] })) return false;

        try {
            await navigator.share({
                title: title || 'Hello, Busan!',
                files: [file],
            });
            return true;
        } catch (e) {
            if (e.name !== 'AbortError') console.warn('Share image failed:', e);
            return false;
        }
    }

    return { generate, download, shareImage, SIZES };
})();
