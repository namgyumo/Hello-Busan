/**
 * category.js — 카테고리 필터 UI
 */
const Category = (() => {
    let selectedCategories = [];
    let onChange = null;

    function init(callback) {
        onChange = callback;
        const bar = document.getElementById('category-bar');
        if (!bar) return;

        bar.addEventListener('click', (e) => {
            const chip = e.target.closest('.category-chip');
            if (!chip) return;

            const cat = chip.dataset.category;

            if (cat === '') {
                // "전체" 클릭 — 모두 해제
                selectedCategories = [];
                bar.querySelectorAll('.category-chip').forEach(c => c.classList.remove('active'));
                chip.classList.add('active');
            } else {
                // 개별 카테고리 토글
                const allChip = bar.querySelector('[data-category=""]');
                if (allChip) allChip.classList.remove('active');

                if (selectedCategories.includes(cat)) {
                    selectedCategories = selectedCategories.filter(c => c !== cat);
                    chip.classList.remove('active');
                } else {
                    selectedCategories.push(cat);
                    chip.classList.add('active');
                }

                // 아무것도 선택 안 되면 "전체" 활성화
                if (selectedCategories.length === 0 && allChip) {
                    allChip.classList.add('active');
                }
            }

            if (onChange) onChange(selectedCategories);
        });
    }

    function getSelected() {
        return selectedCategories;
    }

    return { init, getSelected };
})();
